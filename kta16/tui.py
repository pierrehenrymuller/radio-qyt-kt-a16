"""Textual interface: same screens as the vendor CPS, on a 16 KiB image."""

import argparse
import contextlib
import dataclasses
import functools
import threading
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Input,
    Label,
    OptionList,
    ProgressBar,
    Select,
    SelectionList,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from kta16 import (
    aero,
    calibration,
    changes,
    channels,
    cpsfile,
    defaults,
    dtmf,
    fivetone,
    fm,
    i18n,
    image,
    ports,
    settings,
    twotone,
)
from kta16.channels import Channel
from kta16.i18n import t
from kta16.link import PORT_ERRORS, Radio, open_port
from kta16.protocol import ProtocolError
from kta16.themes import THEMES
from kta16.widgets import Segmented

DTMF_TIMES = (
    ("on", "DTMF Speed On (ms)"),
    ("off", "DTMF Speed Off (ms)"),
    ("reset", "Reset Time (ms)"),
    ("delay", "Delay processing time (ms)"),
)
BACKUP_DIR = Path.home() / ".local/share/kta16/backups"
CALIBRATION_WORD = "CALIBRATION"


def mhz(hz):
    return "" if hz is None else f"{hz / 1e6:.5f}"


def parse_mhz(text):
    text = text.strip()
    if not text:
        return None
    try:
        return round(float(text) * 100_000) * 10
    except ValueError as exc:
        raise ValueError(t("not_a_frequency", text=text)) from exc


KEEPALIVE_S = 1.0  # measured 2026-11-15: 30 reads one second apart keep the session


def holding_session(method):
    """Run a worker with the port to itself (one exchange at a time)."""

    @functools.wraps(method)
    def wrapper(self, *args):
        with self.session_lock:
            return method(self, *args)

    return wrapper


class ChannelTable(DataTable):
    """Channel list. Shift+arrows or Shift+click select a block of channels; Space picks
    the selection (or the current channel) up, arrows move it, Space or Enter drops it,
    Escape puts it back where it was (or clears the selection)."""

    BINDINGS: ClassVar = [
        Binding("space", "toggle_move", show=False),
        Binding("escape", "cancel_move", show=False),
        Binding("shift+up", "extend(-1)", show=False),
        Binding("shift+down", "extend(1)", show=False),
    ]
    block = None  # (first, last) channel numbers selected, or None
    anchor = None  # channel where the selection started
    moving = False  # the block is picked up
    start = None  # first channel of the block when it was picked up

    def check_action(self, action, parameters):
        if action == "cancel_move":
            return (
                self.moving or self.block is not None
            )  # else Escape goes on to the app
        return True

    def _show(self, cursor=None):
        """Redraw the rows (the selection is drawn by the app) and put the cursor back."""
        row = self.cursor_row if cursor is None else cursor
        self.app.refresh_channels()
        self.move_cursor(row=row)

    def _clear(self):
        had = self.block is not None
        self.block = self.anchor = None
        return had

    def _select_to(self, n):
        self.anchor = self.anchor or self.cursor_row + 1
        self.block = (min(self.anchor, n), max(self.anchor, n))
        self._show(n - 1)

    def action_extend(self, step):
        if not self.moving:
            n = min(max(self.cursor_row + 1 + step, 1), self.row_count)
            self._select_to(n)

    def on_click(self, event):
        row = event.style.meta.get("row")
        if row is None or row < 0 or self.moving:
            return
        if event.shift:
            event.prevent_default()  # no channel form on a Shift+click
            self._select_to(row + 1)
        elif self._clear():
            self._show()

    def action_toggle_move(self):
        if self.moving:
            self.moving = False
            self._clear()
            self._show()
            self.app.status("")
        elif self.row_count:
            if self.block is None:
                self.block = self.anchor = (self.cursor_row + 1,) * 2
            self.moving = True
            self.start = self.block[0]
            self.app.status(t("moving"))

    def _step(self, step):
        if self.moving:
            self.app.move_block(self, step)
        else:
            if self._clear():
                self._show()
            (super().action_cursor_down if step > 0 else super().action_cursor_up)()

    def action_cursor_up(self):
        self._step(-1)

    def action_cursor_down(self):
        self._step(1)

    def action_select_cursor(self):
        if self.moving:  # Enter drops instead of opening the form
            self.action_toggle_move()
        else:
            super().action_select_cursor()

    def action_cancel_move(self):
        if self.moving:
            self.app.move_block(self, self.start - self.block[0])
            self.action_toggle_move()
        elif self._clear():
            self._show()


class ConfirmScreen(ModalScreen):
    """Yes/no, or a word to type for dangerous operations."""

    def __init__(self, message, word=None):
        super().__init__()
        self.message, self.word = message, word

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.message)
            if self.word:
                yield Input(placeholder=t("confirm_type", word=self.word), id="word")
            with Horizontal():
                yield Button(t("btn_confirm"), variant="error", id="yes")
                yield Button(t("btn_cancel"), id="no")

    def on_button_pressed(self, event):
        if (
            event.button.id == "yes"
            and self.word
            and self.query_one("#word", Input).value != self.word
        ):
            self.notify(t("confirm_wrong"), severity="error")
            return
        self.dismiss(event.button.id == "yes")


class RestartScreen(ModalScreen):
    """Opening the port restarts the radio: wait until the user has passed its warning screen."""

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(t("restart_wait"))
            with Horizontal():
                yield Button("OK", variant="primary", id="ok")
                yield Button(t("btn_cancel"), id="cancel")

    def on_button_pressed(self, event):
        self.dismiss(event.button.id == "ok")


class PortScreen(ModalScreen):
    """Pick the USB-serial adapter; the recommended cable is the first line."""

    BINDINGS: ClassVar = [Binding("escape", "dismiss(None)", show=False)]

    def __init__(self, adapters):
        super().__init__()
        self.adapters = adapters

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(t("port_title"))
            # Content(): the label comes from the USB device, never parsed as markup.
            yield OptionList(
                *(
                    Option(
                        Content(
                            a.label
                            + (f"  ({t('port_recommended')})" if a.recommended else "")
                        ),
                        id=a.device,
                    )
                    for a in self.adapters
                )
            )

    def on_option_list_option_selected(self, event):
        self.dismiss(event.option.id)


class PathScreen(ModalScreen):
    def __init__(self, title, default):
        super().__init__()
        self.title_text, self.default = title, default

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.title_text)
            yield Input(value=self.default, id="path")
            with Horizontal():
                yield Button("OK", variant="primary", id="ok")
                yield Button(t("btn_cancel"), id="cancel")

    def on_button_pressed(self, event):
        value = self.query_one("#path", Input).value.strip()
        self.dismiss(value if event.button.id == "ok" and value else None)


class ChannelScreen(ModalScreen):
    """Edit one channel; empty RX frequency deletes it. TX outside the radio bands only warns."""

    def __init__(self, number, ch):
        super().__init__()
        self.number, self.ch = number, ch
        self.hits = []  # aero.search results shown in #aero_pick
        self.first_pick = None  # index of the hit that filled the form

    def compose(self) -> ComposeResult:
        ch = self.ch or Channel(
            None, None, "OFF", "OFF", "HIGH", False, "OFF", False, True, None, "OFF", "QT", False, ""
        )  # fmt: skip
        tones = [(x, x) for x in channels.TONE_TABLE]
        with Vertical(id="dialog"):
            with VerticalScroll(id="fields"):
                yield Label(t("ch_title", n=self.number - 1), classes="title")
                with Horizontal(classes="cols"):
                    with Vertical(classes="col"):
                        yield Label(t("ch_aero"))
                        yield Input(id="aero", max_length=40)
                        yield Label(t("ch_aero_pick"))
                        yield SelectionList(id="aero_pick")
                        yield Label("", id="aero_count")
                        yield Label(t("ch_name"))
                        yield Input(ch.name, id="name", max_length=channels.NAME_LEN)
                        yield Label(t("ch_rx"))
                        yield Input(mhz(ch.rx_hz), id="rx")
                        yield Label(t("ch_tx"), id="tx-label")
                        with Horizontal(classes="switch-row", id="tx_row"):
                            # Off when the saved channel has no usable TX (empty or 200 MHz).
                            yield Switch(
                                self.ch is None
                                or ch.tx_hz not in (None, channels.TX_OFF_HZ),
                                id="tx_on",
                            )
                            yield Label(t("ch_tx_on"))
                        yield Input(
                            "" if ch.tx_hz == channels.TX_OFF_HZ else mhz(ch.tx_hz),
                            id="tx",
                        )
                        yield Label("", id="tx-warn")
                        yield Label("", id="tx-ok")
                        yield Label(t("ch_rxtone"))
                        yield Select(
                            tones, value=ch.rx_tone, id="rx_tone", allow_blank=False
                        )
                        yield Label(t("ch_txtone"))
                        yield Select(
                            tones, value=ch.tx_tone, id="tx_tone", allow_blank=False
                        )
                        yield Label(t("ch_sig"))
                        yield Input(
                            "" if ch.sig_code is None else str(ch.sig_code), id="sig"
                        )
                    with Vertical(classes="col"):
                        yield Label(t("ch_power"))
                        yield Segmented(
                            channels.POWERS, channels.POWERS.index(ch.power), id="power"
                        )
                        yield Label(t("ch_mod"))
                        yield Segmented(
                            [t("mod_wide"), t("mod_narrow")],
                            int(ch.narrow),
                            id="narrow",
                        )
                        for field, label in (
                            ("busy_lock", t("ch_bcl")),
                            ("scan_add", t("ch_scan")),
                            ("scrambler", t("ch_scr")),
                        ):
                            with Horizontal(classes="switch-row"):
                                yield Switch(getattr(ch, field), id=field)
                                yield Label(label)
                        for field, label, choices in (
                            ("ptt_id", t("ch_ptt"), channels.PTT_IDS),
                            ("opt_signal", t("col_optsig"), channels.OPT_SIGNALS),
                            ("sp_mute", t("col_mute"), channels.SP_MUTES),
                        ):
                            yield Label(label)
                            yield Select(
                                [(c, c) for c in choices],
                                value=getattr(ch, field),
                                id=field,
                                allow_blank=False,
                            )
            with Horizontal(id="buttons"):
                yield Button(t("btn_ok"), variant="primary", id="ok")
                yield Button(t("btn_cancel"), id="cancel")

    def on_mount(self):
        self._sync_tx()

    def _sync_tx(self):
        """The TX box is hidden while the TX switch is Off."""
        on = self.query_one("#tx_on", Switch).value
        for widget in ("#tx-label", "#tx", "#tx-warn", "#tx-ok"):
            self.query_one(widget).display = on

    def on_switch_changed(self, event):
        if event.switch.id != "tx_on":
            return
        tx = self.query_one("#tx", Input)
        if event.value and not tx.value.strip():  # switched on: same frequency as RX
            tx.value = self.query_one("#rx", Input).value
        self._sync_tx()

    def on_input_changed(self, event):
        if event.input.id == "tx":
            self._check_tx(event.value)
        elif event.input.id == "aero":
            self.hits = aero.search(aero.load(), event.value)
            pick = self.query_one("#aero_pick", SelectionList)
            pick.clear_options()
            # Content(): SIA text, never parsed as markup.
            pick.add_options(
                (
                    Content(
                        f"{h['name']:<7} {h['mhz']:.3f}  {i18n.aero_desc(h['desc'])}"
                    ),
                    i,
                )
                for i, h in enumerate(self.hits)
            )
            self.first_pick = None
            self.query_one("#aero_count", Label).update("")

    def _picked(self):
        """Hits ticked in the aero list, in list order."""
        return [self.hits[i] for i in sorted(self.query_one("#aero_pick").selected)]

    def on_selection_list_selected_changed(self, event):
        """The first ticked line fills the form; with several, one channel per line."""
        selected = sorted(event.selection_list.selected)
        n = len(selected)
        self.query_one("#aero_count", Label).update(
            t("ch_aero_count", n=n, a=self.number - 1, b=self.number + n - 2)
            if n > 1
            else ""
        )
        if selected and selected[0] != self.first_pick:
            self.first_pick = selected[0]
            self._fill_from(self.hits[selected[0]])

    def _fill_from(self, hit):
        """Fill name and RX from an aeronautical frequency. TX = RX, except ATIS and
        beacons (VOR, ILS): their TX switch starts Off and the TX box is hidden."""
        self.query_one("#name", Input).value = hit["name"]
        freq = f"{hit['mhz']:.5f}"
        self.query_one("#rx", Input).value = freq
        receive_only = aero.is_beacon(hit) or aero.is_atis(hit)
        self.query_one("#tx", Input).value = "" if receive_only else freq
        self.query_one("#tx_on", Switch).value = not receive_only
        self._sync_tx()

    def _check_tx(self, text):
        """Warn, without blocking, when TX is outside the bands the radio reports."""
        warn = self.query_one("#tx-warn", Label)
        try:
            hz = parse_mhz(text)
        except ValueError:
            warn.update("")  # the format error is reported when applying
            return
        ok = self.query_one("#tx-ok", Label)
        if not self._limits_known():  # image never read: the limits are blank bytes
            warn.update("")
            ok.update("")
            return
        band = None if hz is None else self._band_of(hz / 1e6)
        warn.update("" if hz is None or band else t("ch_bandwarn"))
        ok.update(t("ch_bandok", low=band[0], high=band[1]) if band else "")

    def _limits_known(self):
        """True when at least one band limit of the image is a plausible range (not 0xFF fill)."""
        data = self.app.image.data
        limits = (
            calibration.band_limits(data, row)
            for row in range(len(calibration.BAND_LIMIT_NAMES))
        )
        return any(0 < low < high <= 999 for low, high, _ in limits)

    def _band_of(self, mhz_value):
        """(low, high) of the enabled radio band holding mhz_value, else None."""
        data = self.app.image.data
        for row in range(len(calibration.BAND_LIMIT_NAMES)):
            low, high, enabled = calibration.band_limits(data, row)
            if enabled and low <= mhz_value <= high:
                return low, high
        return None

    def on_button_pressed(self, event):
        if event.button.id != "ok":
            self.dismiss(None)
            return
        q = self.query_one
        try:
            rx = parse_mhz(q("#rx", Input).value)
            if rx is None:
                self.dismiss(("delete", None))
                return
            sig = q("#sig", Input).value.strip()
            name = q("#name", Input).value.strip().upper()
            tx = parse_mhz(q("#tx", Input).value) if q("#tx_on", Switch).value else None
            if tx is None and not aero.is_beacon({"name": name, "mhz": rx / 1e6}):
                # An empty TX does not stop the radio (measured): 200 MHz does.
                # Beacon band: the radio never transmits there, TX stays empty.
                tx = channels.TX_OFF_HZ
            ch = Channel(
                rx_hz=rx,
                tx_hz=tx,
                rx_tone=q("#rx_tone", Select).value,
                tx_tone=q("#tx_tone", Select).value,
                power=q("#power", Segmented).value,
                narrow=q("#narrow", Segmented).index == 1,
                ptt_id=q("#ptt_id", Select).value,
                busy_lock=q("#busy_lock", Switch).value,
                scan_add=q("#scan_add", Switch).value,
                sig_code=int(sig) if sig else None,
                opt_signal=q("#opt_signal", Select).value,
                sp_mute=q("#sp_mute", Select).value,
                scrambler=q("#scrambler", Switch).value,
                name=name,
            )
            channels.encode_channel(ch, b"\xff" * 16, b"\xff" * 8)  # validation
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        picked = self._picked()
        if len(picked) > 1:  # the form gives the settings, each line its frequency
            self.dismiss(("insert", [ch, *(self._like(ch, h) for h in picked[1:])]))
            return
        self.dismiss(("set", ch))

    @staticmethod
    def _like(ch, hit):
        """A copy of `ch` for another aeronautical line, with the TX rule of that line."""
        rx = round(hit["mhz"] * 1e6)
        if aero.is_beacon(hit):
            tx = None  # the radio never transmits in the beacon band
        elif aero.is_atis(hit):
            tx = channels.TX_OFF_HZ
        else:
            tx = rx
        return dataclasses.replace(ch, name=hit["name"], rx_hz=rx, tx_hz=tx)


def bindings():
    """Footer shortcuts, in the language chosen at start."""
    return [
        Binding("r", "read", t("b_read")),
        Binding("w", "write", t("b_write")),
        Binding("a", "write_changes", t("b_write_changes")),
        Binding("d", "default", t("b_default")),
        Binding("c", "clear", t("b_clear")),
        Binding("u", "aero_update", t("b_aero")),
        Binding("o", "open", t("b_open")),
        Binding("s", "save", t("b_save")),
        Binding("l", "release", t("b_release")),
        Binding("t", "toggle_theme", t("b_theme")),
        Binding("q", "quit", t("b_quit")),
    ]


NAV = (
    ("nav_memories", (("tab-channels", "tab_channels"),)),
    (
        "nav_settings",
        (("tab-options", "tab_options"), ("tab-password", "tab_password")),
    ),
    (
        "nav_signal",
        (
            ("tab-dtmf", "tab_dtmf"),
            ("tab-2tone", "tab_2tone"),
            ("tab-5tone", "tab_5tone"),
        ),
    ),
    (
        "nav_advanced",
        (
            ("tab-fm", "tab_fm"),
            ("tab-calibration", "tab_calibration"),
            ("tab-memory", "tab_memory"),
        ),
    ),
)
NAV_ZONES = {
    "tab-channels": "channels", "tab-options": "options", "tab-dtmf": "dtmf",
    "tab-2tone": "2-tone", "tab-5tone": "5-tone", "tab-fm": "fm",
}  # fmt: skip
CHANNEL_FIELD_KEYS = {
    "name": "col_name", "rx_hz": "col_rx", "tx_hz": "col_tx", "rx_tone": "col_rxtone",
    "tx_tone": "col_txtone", "power": "col_power", "narrow": "col_mod", "ptt_id": "col_ptt",
    "busy_lock": "col_bcl", "scan_add": "col_scan", "sig_code": "col_sig",
    "opt_signal": "col_optsig", "sp_mute": "col_mute", "scrambler": "col_scr",
}  # fmt: skip


def format_change(c):
    """One line of the « To write » panel: field, then old in red, new in green."""
    if c.field == changes.NEVER_READ:
        return Content(t("pending_never_read", zone=zone_name(c.zone))).markup
    if c.field == changes.COUNT_FIELD:
        return Content(t("pending_bytes", zone=zone_name(c.zone), n=c.new)).markup
    if c.zone == "channels":
        item = t("pending_channel", n=c.item)
        field = (
            item
            if c.field == changes.CHANNEL_ITEM
            else f"{item}, {t(CHANNEL_FIELD_KEYS[c.field])}"
        )
    else:
        field = c.field
    old, new = Content(c.old).markup, Content(c.new).markup
    return f"{Content(field).markup} : [$error]{old}[/] -> [$success]{new}[/]"


def zone_name(region_name):
    """Label of an image zone, as shown to the user."""
    key = {
        "channels": "zone_channels", "options": "zone_options", "5-tone": "zone_fivetone",
        "dtmf": "zone_dtmf", "2-tone": "zone_twotone", "fm": "zone_fm",
        "calibration": "zone_calibration", "password": "zone_password", "all": "zone_all",
    }  # fmt: skip
    return t(key.get(region_name, "zone_all"))


class NavItem(Static):
    """One entry of the sidebar: label on the left, number of changes on the right."""

    def __init__(self, pane_id, label):
        super().__init__(label, id=f"nav-{pane_id}", classes="nav-item")
        self.pane_id, self.label_text, self.count = pane_id, label, 0

    def set_count(self, count):
        if count != self.count:
            self.count = count
            width = max(self.size.width, 1)
            right = str(count) if count else ""
            gap = max(1, width - len(self.label_text) - len(right))
            self.update(Content(self.label_text + " " * gap + right))

    def on_click(self):
        self.app.query_one("#tabs", TabbedContent).active = self.pane_id


class KTA16App(App):
    TITLE = "QYT KT-A16"
    CSS = """
    #dialog { width: 70; height: auto; max-height: 90%; border: round $accent;
              background: $surface; padding: 1 2; }
    ConfirmScreen, PathScreen, PortScreen, RestartScreen, ChannelScreen { align: center middle; }
    ChannelScreen #dialog { width: 100; height: 90%; }
    ChannelScreen #fields { height: 1fr; }
    ChannelScreen #aero_pick { height: auto; max-height: 10; }
    ChannelScreen #aero_count { width: 100%; height: auto; }
    ChannelScreen .title { text-style: bold; color: $accent; margin-bottom: 1; }
    ChannelScreen .cols { height: auto; }
    ChannelScreen .col { width: 1fr; height: auto; padding: 0 1; }
    ChannelScreen .switch-row { height: 1; margin-bottom: 1; }
    ChannelScreen .switch-row Switch { border: none; height: 1; padding: 0; width: 6; margin-right: 1; }
    ChannelScreen .switch-row Label { height: 1; }
    ChannelScreen #tx-warn { color: $warning; height: auto; }
    ChannelScreen #tx-ok { color: $success; height: auto; }
    ChannelScreen .col > Label { color: $text-muted; }
    ChannelScreen #buttons { height: auto; }
    .field { height: 3; }
    .field Label { width: 32; padding-top: 1; }
    #hex { height: 1fr; }
    #statusbar { height: 1; padding: 0 1; background: $surface; }
    #shell { height: 1fr; }
    #sidebar { width: 24; border-right: solid $panel; padding: 0 1; }
    .nav-group { color: $text-muted; margin-top: 1; }
    .nav-item { width: 100%; height: 1; padding: 0 1; border-left: wide transparent; }
    .nav-item:hover { background: $panel; }
    .nav-item.-active { background: $panel; border-left: wide $accent; color: $accent; text-style: bold; }
    .pane-title { height: 1; padding: 0 1; }
    .vfo-title { margin-top: 1; padding: 0 1; text-style: bold; color: $accent; }
    #tabs { width: 1fr; height: 1fr; }
    #tabs TabPane { height: 1fr; }
    #channels, #tt-table, #ft-table, #fm-table, #cal-table { height: 1fr; }
    #tabs > Tabs { display: none; }
    #pending-panel { width: 40; border-left: solid $panel; padding: 0 1; }
    .panel-title { text-style: bold; color: $accent; }
    """
    BINDINGS: ClassVar = bindings()

    def __init__(self, port=None, serial_factory=None, ask_port=False):
        super().__init__()
        self.ask_port = ask_port  # main(): no --port, offer the adapters at startup
        self.image = image.Image()
        self.port = port
        self.serial_factory = serial_factory
        self.ser = None  # kept open: every open reboots the radio
        self.radio = None
        # After a session ended the radio restarts: wait for the user before the next handshake.
        self.restart_prompt = serial_factory is None
        self.had_session = False  # a session was open: its end restarted the radio
        self.session_lock = threading.Lock()  # one exchange at a time on the port
        self._ka_stop = threading.Event()  # stops the keep-alive thread
        self.file_path = "kta16.img"
        # One try: repeated handshakes make the real radio reboot in a loop.
        self.handshake_attempts = 1
        # What the radio holds, as far as this session read or wrote it.
        self.radio_data = bytearray(len(self.image.data))
        self.radio_known = set()  # names of DATA_REGIONS read or written
        self.clean = bytearray(self.image.data)  # last read, written or saved
        self.last_read = None  # time of the last read of this session
        self.last_read_what = ""  # what it covered: the whole radio or one zone

    def action_toggle_theme(self):
        names = [th.name for th in THEMES]
        self.theme = names[(names.index(self.theme) + 1) % len(names)]

    def compose(self) -> ComposeResult:
        yield Static("", id="statusbar")
        with Horizontal(id="shell"):
            with Vertical(id="sidebar"):
                for group, items in NAV:
                    yield Static(t(group), classes="nav-group")
                    for pane_id, label in items:
                        yield NavItem(pane_id, t(label))
            with TabbedContent(id="tabs"):
                with TabPane(t("tab_channels"), id="tab-channels"):
                    yield Static("", id="channels-title", classes="pane-title")
                    yield ChannelTable(id="channels", cursor_type="row")
                with TabPane(t("tab_options"), id="tab-options"), VerticalScroll():
                    vfo_prefixes = tuple(f"vfo_{v.lower()}_" for v in settings.VFOS)
                    general = [
                        f for f in settings.FIELDS if not f.key.startswith(vfo_prefixes)
                    ]
                    yield from self._option_selects(general)
                    for i, v in enumerate(settings.VFOS):
                        yield Static(
                            t("line_title", name=v),
                            id=f"vfo-title-{v}",
                            classes="vfo-title",
                        )
                        for kind, text in (
                            ("freq", t("vfo_freq")),
                            ("offset", t("vfo_offset")),
                            ("rx", t("vfo_rx")),
                            ("tx", t("vfo_tx")),
                        ):
                            with Horizontal(classes="field"):
                                yield Label(text)
                                yield Input(
                                    id=f"vfo-{kind}-{i}", placeholder=t("not_read")
                                )
                        own = [
                            f
                            for f in settings.FIELDS
                            if f.key.startswith(vfo_prefixes[i])
                        ]
                        yield from self._option_selects(own, strip=f"{v} ")
                with TabPane(t("tab_dtmf"), id="tab-dtmf"), VerticalScroll():
                    for n in range(1, dtmf.CODE_COUNT + 1):
                        with Horizontal(classes="field"):
                            yield Label(f"Code {n}")
                            yield Input(id=f"dtmf-code-{n}", max_length=dtmf.CODE_LEN)
                    for name in dtmf.FUNCTIONS:
                        with Horizontal(classes="field"):
                            yield Label(name)
                            yield Input(id=f"dtmf-fn-{name}", max_length=dtmf.CODE_LEN)
                    for key, label in (
                        ("group", "Group Code"),
                        ("space", "Space Code"),
                    ):
                        with Horizontal(classes="field"):
                            yield Label(label)
                            yield Input(id=f"dtmf-{key}", max_length=1)
                    for key, label in DTMF_TIMES:
                        with Horizontal(classes="field"):
                            yield Label(label)
                            yield Input(id=f"dtmf-t-{key}", type="integer")
                    yield Checkbox("master and vice ID", id="dtmf-mv")
                    for who in dtmf.RIGHTS:
                        with Horizontal(classes="field"):
                            yield Label(f"{t('rights')} {who}")
                            for right in dtmf.RIGHT_BITS:
                                yield Checkbox(right, id=f"dtmf-r-{who}-{right}")
                    with Horizontal(classes="field"):
                        yield Label("State")
                        for flag in dtmf.STATE_BITS:
                            yield Checkbox(flag, id=f"dtmf-s-{flag}")
                    yield Button(t("btn_apply_image"), id="dtmf-apply")
                with TabPane(t("tab_2tone"), id="tab-2tone"):
                    yield Label(t("help_2tone"))
                    yield Input(id="tt-edit")
                    yield DataTable(id="tt-table")
                with TabPane(t("tab_5tone"), id="tab-5tone"):
                    yield Label(t("help_5tone"))
                    yield Input(id="ft-edit")
                    yield Button(t("btn_cal_tables"), id="ft-defaults")
                    yield DataTable(id="ft-table")
                with TabPane(t("tab_fm"), id="tab-fm"):
                    yield Label(t("help_fm"))
                    yield Input(id="fm-edit")
                    yield DataTable(id="fm-table")
                with TabPane(t("tab_calibration"), id="tab-calibration"):
                    yield Label(t("help_cal"))
                    yield Input(id="cal-edit")
                    yield DataTable(id="cal-table")
                with TabPane(t("tab_password"), id="tab-password"):
                    yield Label(t("pw1_label"))
                    yield Input(id="pw1", max_length=6)
                    yield Label(t("pw2_label"))
                    yield Input(id="pw2", max_length=6)
                    yield Button(t("btn_apply_image"), id="pw-apply")
                with TabPane(t("tab_memory"), id="tab-memory"):
                    yield Select(
                        [(r.name, r.name) for r in image.REGIONS],
                        value="dtmf",
                        id="region",
                        allow_blank=False,
                    )
                    yield DataTable(id="hex")
                    yield Input(placeholder=t("poke_placeholder"), id="poke")
            with VerticalScroll(id="pending-panel"):
                yield Static(t("pending_title"), classes="panel-title")
                yield Static("", id="pending")
                yield ProgressBar(id="progress", show_eta=False)
        yield Static("", id="status")
        yield Footer()

    @staticmethod
    def _option_selects(fields, strip=""):
        """One labelled list per option field; `strip` drops the "A " of VFO labels."""
        for f in fields:
            with Horizontal(classes="field"):
                label = (
                    f.label[len(strip) :]
                    if strip and f.label.startswith(strip)
                    else f.label
                )
                yield Label(label)
                yield Select(
                    [(text, i) for i, text in f.options()],
                    id=f"opt-{f.key}",
                    allow_blank=True,
                    prompt=t("not_read"),
                )

    def on_mount(self):
        for theme in THEMES:
            self.register_theme(theme)
        self.theme = THEMES[0].name  # dark at every start, `t` toggles
        table = self.query_one("#channels", DataTable)
        table.add_columns(
            t("col_n"), t("col_changed"), t("col_name"), t("col_rx"), t("col_tx"),
            t("col_rxtone"), t("col_txtone"), t("col_power"), t("col_mod"), t("col_ptt"),
            t("col_bcl"), t("col_scan"), t("col_sig"), t("col_optsig"), t("col_mute"),
            t("col_scr"),
        )  # fmt: skip
        self.clean = bytearray(self.image.data)  # main() may set the image
        self.refresh_all()
        self.refresh_nav("tab-channels")
        self.refresh_chrome()
        self.refresh_pending()
        self.set_interval(1.0, self.refresh_pending)
        self.set_interval(1.0, self.refresh_chrome)
        if self.ask_port:
            self.choose_port()

    # display -------------------------------------------------------------

    def refresh_all(self):
        pw1, pw2 = self.image.passwords()
        self.query_one("#pw1", Input).value = pw1
        self.query_one("#pw2", Input).value = pw2
        self.refresh_channels()
        self.refresh_options()
        self.refresh_dtmf()
        self.refresh_calibration()
        self.refresh_fm()
        self.refresh_twotone()
        self.refresh_fivetone()
        self.refresh_hex()

    def move_block(self, table, step):
        """Move the picked-up block of channels; the cursor follows it."""
        lo, hi = table.block
        try:
            self.image.move_block(lo, hi, step)
        except ValueError:  # at the first or last channel: nothing to do
            return
        table.block = (lo + step, hi + step)
        table.anchor = table.block[0]
        row = table.cursor_row + step
        self.refresh_channels()
        table.move_cursor(row=row)

    def refresh_channels(self):
        table = self.query_one("#channels", DataTable)
        table.clear()
        programmed = sum(
            self.image.channel(n) is not None
            for n in range(1, channels.CHANNEL_COUNT + 1)
        )
        self.query_one("#channels-title", Static).update(
            Content.from_markup(f"[b]{Content(t('tab_channels')).markup}[/]  ")
            + Content.styled(
                t("channels_count", n=programmed, total=channels.CHANNEL_COUNT),
                "$text-muted",
            )
        )
        radio = image.Image(self.radio_data)
        known = "channels" in self.radio_known
        picked = table.block
        for n in range(1, channels.CHANNEL_COUNT + 1):
            ch = self.image.channel(n)
            changed = known and ch != radio.channel(n)
            mark = t("col_changed") if changed else ""
            if ch is None:
                cells = [str(n - 1), mark, *[""] * 14]
            else:
                cells = [
                    str(n - 1),  # the radio and the CPS count from 0
                    mark,
                    ch.name,
                    mhz(ch.rx_hz),
                    "" if ch.tx_hz == channels.TX_OFF_HZ else mhz(ch.tx_hz),
                    ch.rx_tone,
                    ch.tx_tone,
                    ch.power,
                    t("mod_narrow") if ch.narrow else t("mod_wide"),
                    ch.ptt_id,
                    "ON" if ch.busy_lock else "OFF",
                    "ON" if ch.scan_add else "OFF",
                    "" if ch.sig_code is None else str(ch.sig_code),
                    ch.opt_signal,
                    ch.sp_mute,
                    "ON" if ch.scrambler else "OFF",
                ]
            if picked and picked[0] <= n <= picked[1]:  # selected block
                cells = [Content.styled(c, "reverse") for c in cells]
            table.add_row(*cells, key=str(n))

    def refresh_options(self):
        def shown(text):  # blank bytes (0xff) decode as "?": the zone is empty
            return "" if "?" in text else text

        for i, line in enumerate(settings.VFOS):
            freq = shown(settings.vfo_frequency(self.image.data, i))
            self.query_one(f"#vfo-title-{line}", Static).update(
                t(
                    "line_title_freq",
                    name=line,
                    freq=freq.lstrip("0").rstrip("0").rstrip(".") or "0",
                )
                if freq
                else t("line_title", name=line)
            )
            self.query_one(f"#vfo-freq-{i}", Input).value = freq
            self.query_one(f"#vfo-offset-{i}", Input).value = shown(
                settings.vfo_offset(self.image.data, i)
            )
            for which in ("rx", "tx"):
                self.query_one(f"#vfo-{which}-{i}", Input).value = settings.vfo_tone(
                    self.image.data, i, which
                )
        self._loading_options = True
        for f in settings.FIELDS:
            value = f.get(self.image.data)
            sel = self.query_one(f"#opt-{f.key}", Select)
            known = {i for i, _ in f.options()}
            if value in known:
                sel.value = value
            else:
                sel.clear()
        self._loading_options = False

    def refresh_hex(self):
        name = self.query_one("#region", Select).value
        region = next(r for r in image.REGIONS if r.name == name)
        table = self.query_one("#hex", DataTable)
        table.clear(columns=True)
        table.add_columns(t("col_address"), *[f"{i:X}" for i in range(16)])
        for start, end in region.ranges:
            for a in range(start, end, 16):
                table.add_row(
                    f"{a:04X}", *[f"{b:02X}" for b in self.image.data[a : a + 16]]
                )

    def refresh_dtmf(self):
        d = self.image.data
        for n in range(1, dtmf.CODE_COUNT + 1):
            self.query_one(f"#dtmf-code-{n}", Input).value = dtmf.get_code(d, n)
        for name in dtmf.FUNCTIONS:
            self.query_one(f"#dtmf-fn-{name}", Input).value = dtmf.get_function(d, name)
        self.query_one("#dtmf-group", Input).value = dtmf.decode_digits(
            d[dtmf.GROUP_CODE : dtmf.GROUP_CODE + 1]
        )
        self.query_one("#dtmf-space", Input).value = dtmf.decode_digits(
            d[dtmf.SPACE_CODE : dtmf.SPACE_CODE + 1]
        )
        for (key, _), ms in zip(DTMF_TIMES, dtmf.times_ms(d), strict=True):
            self.query_one(f"#dtmf-t-{key}", Input).value = str(ms)
        self.query_one("#dtmf-mv", Checkbox).value = d[dtmf.MASTER_AND_VICE] == 1
        for who in dtmf.RIGHTS:
            rights = dtmf.get_rights(d, who)
            for right in dtmf.RIGHT_BITS:
                box = self.query_one(f"#dtmf-r-{who}-{right}", Checkbox)
                box.value = right in rights
        state = dtmf.get_state(d)
        for flag in dtmf.STATE_BITS:
            self.query_one(f"#dtmf-s-{flag}", Checkbox).value = flag in state

    def apply_dtmf(self):
        new = bytearray(self.image.data)
        for n in range(1, dtmf.CODE_COUNT + 1):
            dtmf.set_code(new, n, self.query_one(f"#dtmf-code-{n}", Input).value)
        for name in dtmf.FUNCTIONS:
            dtmf.set_function(
                new, name, self.query_one(f"#dtmf-fn-{name}", Input).value
            )
        for key, addr in (("group", dtmf.GROUP_CODE), ("space", dtmf.SPACE_CODE)):
            value = self.query_one(f"#dtmf-{key}", Input).value
            if len(value) != 1:
                raise ValueError(t("dtmf_one_char", key=key))
            new[addr] = dtmf.encode_digits(value, size=1)[0]
        times = []
        for key, label in DTMF_TIMES:
            text = self.query_one(f"#dtmf-t-{key}", Input).value
            if not text.isdigit():
                raise ValueError(t("dtmf_ms", label=label))
            times.append(int(text))
        dtmf.set_times(new, *times)
        new[dtmf.MASTER_AND_VICE] = int(self.query_one("#dtmf-mv", Checkbox).value)
        for who in dtmf.RIGHTS:
            dtmf.set_rights(
                new,
                who,
                {
                    r
                    for r in dtmf.RIGHT_BITS
                    if self.query_one(f"#dtmf-r-{who}-{r}", Checkbox).value
                },
            )
        dtmf.set_state(
            new,
            {
                f
                for f in dtmf.STATE_BITS
                if self.query_one(f"#dtmf-s-{f}", Checkbox).value
            },
        )
        self.image.data[:] = new

    def refresh_twotone(self):
        d = self.image.data
        table = self.query_one("#tt-table", DataTable)
        table.clear(columns=True)
        table.add_columns("code", "encode F1/F2", t("tt_decode"), t("tt_tones"))
        for n in range(1, twotone.COUNT + 1):
            enc = twotone.get_encode(d, n)
            dec = " | ".join(
                "" if e is None else f"{e[0]} {e[1]} {e[2]}"
                for e in twotone.get_decode(d, n)
            )
            tones = " ".join(
                "-" if t is None else str(t) for t in twotone.get_tones(d, n)
            )
            table.add_row(
                str(n), "" if enc is None else f"{enc[0]}/{enc[1]}", dec, tones
            )
        first, second, gap = twotone.durations_ms(d)
        table.add_row(t("durations"), f"{first} / {second} / {gap} ms", "", "")
        raw = twotone.reset_raw(d)
        table.add_row(
            "reset", t("reset_octet", ms=twotone.reset_ms(raw), raw=raw), "", ""
        )

    def refresh_fivetone(self):
        d = self.image.data
        table = self.query_one("#ft-table", DataTable)
        table.clear(columns=True)
        table.add_columns(t("col_row"), t("col_content"))
        for s, name in enumerate(fivetone.STANDARDS):
            period, group, repeat = fivetone.get_standard_params(d, s)
            tones = " ".join(
                "-" if t is None else str(t) for t in fivetone.get_tones(d, s)
            )
            table.add_row(f"{s} {name}", f"{period} ms G={group} R={repeat} : {tones}")
        for n in range(1, fivetone.CODE_COUNT + 1):
            table.add_row(
                f"code {n}", " ".join(x or "-" for x in fivetone.get_encode(d, n))
            )
        std, call, disp = fivetone.decode_settings(d)
        delays = fivetone.delays_ms(d)
        reset = twotone.reset_ms(d[fivetone.DECODE_RESET])
        table.add_row(
            t("decoding"),
            t(
                "fivetone_decode",
                std=std,
                call=sorted(call),
                disp=sorted(disp),
                reset=reset,
            ),
        )
        table.add_row(t("delays_ms"), " ".join(str(x) for x in delays))

    def _fivetone_command(self, text):
        d = self.image.data
        w = text.split()
        if w[0] == "tone":
            fivetone.set_tone(d, int(w[1]), int(w[2]), int(w[3]))
        elif w[0] == "std":
            fivetone.set_standard_params(
                d, int(w[1]), int(w[2]), w[3].upper(), w[4].upper()
            )
        elif w[0] == "delays":
            fivetone.set_delays_ms(d, *(int(x) for x in w[1:5]))
        elif w[0] == "dec":
            frames = lambda chars: {int(c) for c in chars if c != "-"}
            fivetone.set_decode_settings(
                d,
                w[1].upper(),
                frames(w[2]),
                frames(w[3]),
                twotone.reset_value(int(w[4])),
            )
        elif w[0] == "enc":
            frames = ["" if x == "-" else x for x in w[2:5]]
            fivetone.set_encode(d, int(w[1]), (*frames, w[5].upper()))
        else:
            raise ValueError(t("unknown_command"))

    def _twotone_command(self, text):
        d = self.image.data
        words = text.split()
        hz = lambda w: None if w == "-" else int(w)
        if words[0] == "enc":
            pair = None if words[2:] == ["-"] else (hz(words[2]), hz(words[3]))
            twotone.set_encode(d, int(words[1]), pair)
        elif words[0] == "tones":
            twotone.set_tones(d, int(words[1]), tuple(hz(w) for w in words[2:6]))
        elif words[0] == "reset":
            twotone.set_reset_raw(d, twotone.reset_value(int(words[1])))
        elif words[0] == "dur":
            twotone.set_durations_ms(d, *(int(w) for w in words[1:4]))
        elif words[0] == "dec":
            rest = words[2:]
            entries = [
                (rest[i], twotone.RESPONSES[int(rest[i + 1])], int(rest[i + 2]))
                for i in range(0, 12, 3)
            ]
            twotone.set_decode(d, int(words[1]), entries)
        else:
            raise ValueError(t("unknown_command"))

    def refresh_fm(self):
        table = self.query_one("#fm-table", DataTable)
        table.clear(columns=True)
        table.add_columns("FM", "MHz", "nom")
        for n in range(1, fm.COUNT + 1):
            entry = fm.get(self.image.data, n)
            table.add_row(
                str(n), *(("", "") if entry is None else (mhz(entry[0]), entry[1]))
            )

    def refresh_calibration(self):
        table = self.query_one("#cal-table", DataTable)
        table.clear(columns=True)
        table.add_columns(t("col_key"), "table", *[str(i) for i in range(16)])
        for tab in calibration.TABLES:
            table.add_row(
                tab.key, tab.label, *[str(v) for v in tab.get(self.image.data)]
            )
        for row, name in enumerate(calibration.BAND_LIMIT_NAMES):
            low, high, on = calibration.band_limits(self.image.data, row)
            table.add_row(
                "", f"{t('limits')} {name}", str(low), str(high), "ON" if on else "OFF"
            )

    def status(self, text):
        self.query_one("#status", Static).update(text)

    def _main(self):
        """The main screen: its panels stay reachable while a dialog is open."""
        return self.screen_stack[0]

    def refresh_chrome(self):
        """Top status bar: where the radio is, and when it was last read."""
        if self.serial_factory:
            where = t("status_emulator")
        else:
            where = (
                t("status_port", port=self.port) if self.port else t("status_no_port")
            )
        if self.last_read:
            last = t(
                "status_last_read",
                what=self.last_read_what,
                time=self.last_read.strftime("%H:%M"),
            )
        else:
            last = t("status_never_read")
        try:
            bar = self._main().query_one("#statusbar", Static)
        except NoMatches:  # timer firing while the application closes
            return
        busy = any(w.is_running for w in self.workers)
        alive = self.radio is not None and self.radio.session_alive
        light, state = (
            ("$warning", t("status_busy"))
            if busy
            else ("$accent", t("status_session"))
            if alive
            else ("$success", t("status_ready"))
        )
        sep = Content.from_markup("  [$text-muted]|[/]  ")
        bar.update(
            Content.from_markup("[b $accent]KT-A16[/]")
            + sep
            + Content(where)
            + sep
            + Content.from_markup(f"[{light}]\u25cf[/] ")
            + Content(state)
            + sep
            + Content.styled(last, "$text-muted")
        )

    def refresh_nav(self, active):
        for item in self._main().query(NavItem):
            item.set_class(item.pane_id == active, "-active")

    def pending_changes(self):
        return changes.diff(self.image, image.Image(self.radio_data), self.radio_known)

    def refresh_pending(self):
        found = self.pending_changes()
        try:
            panel = self._main().query_one("#pending", Static)
        except NoMatches:  # timer firing while the application closes
            return
        zones = sorted(
            {c.zone for c in found}, key=[r.name for r in image.DATA_REGIONS].index
        )
        self._refresh_write_all_binding(len(zones))
        per_zone = {}
        for c in found:
            per_zone[c.zone] = per_zone.get(c.zone, 0) + (
                0 if c.field == changes.NEVER_READ else 1
            )
        for item in self._main().query(NavItem):
            item.set_count(per_zone.get(NAV_ZONES.get(item.pane_id), 0))
        if not found:
            panel.update(t("pending_none"))
            return
        unread = [c.zone for c in found if c.field == changes.NEVER_READ]
        lines = [
            f"[b $accent]{len(zones)}[/]",
            f"[$text-muted]{Content(t('pending_count', n=len(zones))).markup}[/]",
            "",
        ]
        for zone in zones:
            if zone in unread:
                continue
            lines.append(f"[b $accent]{Content(zone_name(zone)).markup}[/]")
            lines += ["  " + format_change(c) for c in found if c.zone == zone]
        if unread:
            names = ", ".join(zone_name(z) for z in unread)
            lines.append(Content(t("pending_unread", zones=names)).markup)
        lines += ["", Content(t("pending_hint")).markup]
        panel.update(Content.from_markup("\n".join(lines)))

    def _refresh_write_all_binding(self, count):
        """Footer: « a Tout écrire (n) » follows the number of zones to write."""
        if getattr(self, "_write_all_count", None) == count:
            return
        self._write_all_count = count
        label = t("b_write_changes_n", n=count) if count else t("b_write_changes")
        self._bindings.key_to_bindings["a"] = [Binding("a", "write_changes", label)]
        self.refresh_bindings()

    # editing -------------------------------------------------------------

    def on_tabbed_content_tab_activated(self, event):
        self.refresh_nav(self.query_one("#tabs", TabbedContent).active)

    def on_button_pressed(self, event):
        if (event.button.id or "").startswith("nav-"):
            self.query_one("#tabs", TabbedContent).active = event.button.id[4:]
            return
        if event.button.id == "ft-defaults":
            fivetone.install_default_tables(self.image.data)
            self.refresh_fivetone()
            self.refresh_hex()
            self.notify(t("tables_copied"))
            return
        if event.button.id == "dtmf-apply":
            try:
                self.apply_dtmf()
            except (TypeError, ValueError) as exc:
                self.notify(str(exc), severity="error")
                return
            self.refresh_hex()
            self.notify(t("dtmf_applied"))
            return
        if event.button.id != "pw-apply":
            return
        try:
            self.image.set_passwords(
                self.query_one("#pw1", Input).value, self.query_one("#pw2", Input).value
            )
        except (TypeError, ValueError) as exc:
            self.notify(str(exc), severity="error")
            return
        self.notify(t("pw_applied"))

    def on_data_table_row_selected(self, event):
        if event.data_table.id != "channels":
            return
        n = int(event.row_key.value)

        self.push_screen(
            ChannelScreen(n, self.image.channel(n)),
            lambda result: self.apply_channel_result(n, result),
        )

    def apply_channel_result(self, n, result):
        """What the channel form returned: set, delete, or several channels from n on."""
        if result is None:
            return
        action, value = result
        if action == "insert":
            try:
                work = image.Image(bytearray(self.image.data))
                work.set_channel(n, value[0])
                work.insert_channels(n + 1, value[1:])
            except ValueError as exc:
                self.notify(t("insert_failed", exc=exc), severity="error")
                return
            self.image.data[:] = work.data
        else:
            self.image.set_channel(n, None if action == "delete" else value)
        self.refresh_channels()

    def on_select_changed(self, event):
        sid = event.select.id or ""
        if sid == "region":
            self.refresh_hex()
        elif (
            sid.startswith("opt-")
            and not getattr(self, "_loading_options", True)
            and isinstance(event.value, int)
            and not isinstance(event.value, bool)
        ):
            field = settings.FIELD_BY_KEY[sid[4:]]
            field.set(self.image.data, event.value)

    def on_input_submitted(self, event):
        if (event.input.id or "").startswith("vfo-"):
            _, kind, index = event.input.id.split("-")
            setters = {
                "freq": settings.set_vfo_frequency,
                "offset": settings.set_vfo_offset,
                "rx": lambda d, i, t: settings.set_vfo_tone(d, i, "rx", t),
                "tx": lambda d, i, t: settings.set_vfo_tone(d, i, "tx", t),
            }
            try:
                setters[kind](self.image.data, int(index), event.value.strip())
            except ValueError as exc:
                self.notify(t("invalid_input", exc=exc), severity="error")
            self.refresh_options()
            return
        if event.input.id == "ft-edit":
            try:
                self._fivetone_command(event.value)
            except (IndexError, TypeError, ValueError) as exc:
                self.notify(t("invalid_input", exc=exc), severity="error")
                return
            event.input.value = ""
            self.refresh_fivetone()
            return
        if event.input.id == "tt-edit":
            try:
                self._twotone_command(event.value)
            except (IndexError, TypeError, ValueError) as exc:
                self.notify(t("invalid_input", exc=exc), severity="error")
                return
            event.input.value = ""
            self.refresh_twotone()
            return
        if event.input.id == "fm-edit":
            try:
                parts = event.value.split(maxsplit=2)
                n = int(parts[0])
                if parts[1:] == ["-"]:
                    fm.set(self.image.data, n, None, "")
                else:
                    name = parts[2] if len(parts) > 2 else ""
                    fm.set(self.image.data, n, parse_mhz(parts[1]), name)
            except (IndexError, TypeError, ValueError) as exc:
                self.notify(t("invalid_input", exc=exc), severity="error")
                return
            event.input.value = ""
            self.refresh_fm()
            return
        if event.input.id == "cal-edit":
            try:
                key, index, value = event.value.split()
                calibration.TABLE_BY_KEY[key].set(
                    self.image.data, int(index), int(value)
                )
            except (KeyError, IndexError, ValueError) as exc:
                self.notify(t("invalid_input", exc=exc), severity="error")
                return
            event.input.value = ""
            self.refresh_calibration()
            return
        if event.input.id != "poke":
            return
        try:
            addr_text, data_text = event.value.split("=", 1)
            addr, data = int(addr_text, 16), bytes.fromhex(data_text)
            if not 0 <= addr <= len(self.image.data) - len(data) or not data:
                raise ValueError(t("poke_out"))
        except ValueError as exc:
            self.notify(t("invalid_input", exc=exc), severity="error")
            return
        end = addr + len(data)
        guarded = image.CALIBRATION.ranges + image.PASSWORD.ranges
        if any(addr < e and s < end for s, e in guarded):
            self.notify(
                t("cal_refused"),
                severity="error",
            )
            return
        self.image.data[addr : addr + len(data)] = data
        event.input.value = ""
        self.refresh_all()

    def action_default(self):
        name = self.current_region().name
        if name not in defaults.ZONES:
            self.notify(t("default_none", zone=zone_name(name)))
            return

        def done(ok):
            if ok:
                defaults.apply(self.image.data, name)
                self.refresh_all()
                self.notify(t("default_done", zone=zone_name(name)))

        msg = t("default_confirm", zone=zone_name(name))
        self.push_screen(ConfirmScreen(msg), done)

    def action_clear(self):
        region = self.current_region()
        clears = {
            image.CHANNELS.name: self.image.clear_channels,
            image.FM.name: lambda: fm.clear(self.image.data),
        }
        if region.name not in clears:
            self.notify(t("clear_only"))
            return

        def done(ok):
            if ok:
                clears[region.name]()
                self.refresh_all()
                self.notify(t("clear_done", zone=zone_name(region.name)))

        self.push_screen(
            ConfirmScreen(t("clear_confirm", zone=zone_name(region.name))), done
        )

    def action_aero_update(self):
        """Channels named like an aero entry (BD APP2) take its current frequency."""
        if self.current_region().name != image.CHANNELS.name:
            self.notify(t("aero_update_only"))
            return
        entries = aero.load()
        if not entries:
            self.notify(t("aero_update_nodata"), severity="error")
            return
        chans = {n: self.image.channel(n) for n in range(1, channels.CHANNEL_COUNT + 1)}
        found = aero.refresh(chans, entries)
        if not found:
            self.notify(t("aero_update_none"))
            return
        lines = [
            f"{n - 1:>3} {old.name:<7} -> {new.name:<7} "
            f"{old.rx_hz / 1e6:.5f} -> {new.rx_hz / 1e6:.5f}"
            for n, old, new in found
        ]
        if len(lines) > 12:
            lines[12:] = ["..."]
        msg = "\n".join([t("aero_update_confirm", n=len(found)), *lines])

        def done(ok):
            if ok:
                for n, _, new in found:
                    self.image.set_channel(n, new)
                self.refresh_channels()
                self.notify(t("aero_update_done", n=len(found)))

        self.push_screen(ConfirmScreen(msg), done)

    # files ---------------------------------------------------------------

    def _load_file(self, path):
        if str(path).lower().endswith(cpsfile.ADJ_SUFFIX):
            # Adjust file: calibration and passwords only, merged into the image
            return cpsfile.load_adj(Path(path).read_bytes(), self.image)
        if cpsfile.is_cps_file(path):
            return cpsfile.load(Path(path).read_bytes())
        return image.Image.load(path)

    def _save_file(self, path):
        if str(path).lower().endswith(cpsfile.ADJ_SUFFIX):
            Path(path).write_bytes(cpsfile.dump_adj(self.image))
        elif cpsfile.is_cps_file(path):
            Path(path).write_bytes(cpsfile.dump(self.image))
        else:
            self.image.save(path)
        self._mark_saved(path)

    def _mark_saved(self, path):
        """The file now matches the image: whole image, or the .adj zone only."""
        start, end = 0, len(self.image.data)
        if str(path).lower().endswith(cpsfile.ADJ_SUFFIX):
            start, end = cpsfile.ADJ_START, cpsfile.ADJ_START + 16 * cpsfile.ADJ_ROWS
        self.clean[start:end] = self.image.data[start:end]

    def action_open(self):
        def done(path):
            if path:
                try:
                    self.image = self._load_file(path)
                except (OSError, ValueError) as exc:
                    self.notify(t("open_failed", exc=exc), severity="error")
                    return
                self.file_path = path
                self._mark_saved(path)
                self.refresh_all()
                self.status(t("opened", path=path))

        self.push_screen(
            PathScreen(t("path_open"), self.file_path),
            done,
        )

    def action_save(self):
        def done(path):
            if path:
                try:
                    self._save_file(path)
                except OSError as exc:
                    self.notify(t("save_failed", exc=exc), severity="error")
                    return
                self.file_path = path
                self.status(t("saved", path=path))

        self.push_screen(
            PathScreen(
                t("path_save"),
                self.file_path,
            ),
            done,
        )

    # radio ---------------------------------------------------------------

    def current_region(self):
        tab = self.query_one("#tabs", TabbedContent).active
        if tab == "tab-channels":
            return image.CHANNELS
        if tab == "tab-options":
            return image.OPTIONS
        if tab == "tab-password":
            return image.PASSWORD
        if tab == "tab-dtmf":
            return image.DTMF
        if tab == "tab-5tone":
            return image.FIVE_TONE
        if tab == "tab-2tone":
            return image.TWO_TONE
        if tab == "tab-fm":
            return image.FM
        if tab == "tab-calibration":
            return image.CALIBRATION
        name = self.query_one("#region", Select).value
        return next(r for r in image.REGIONS if r.name == name)

    def choose_port(self):
        """Offer the USB-serial adapters (does nothing when there is none)."""
        adapters = ports.list_adapters()
        if not adapters:
            return

        def done(device):
            if device:
                self.port = device
                self.refresh_chrome()

        self.push_screen(PortScreen(adapters), done)

    def _close_port(self):
        """Close the port; the radio restarts. The next action opens it again."""
        self._ka_stop.set()
        with contextlib.suppress(*PORT_ERRORS):  # the port may already be dead
            if self.ser is not None:
                self.ser.close()
        self.ser = self.radio = None

    def _drop_port(self):
        """Close the port after a port error: the next action opens a fresh one."""
        self._close_port()
        if not self.serial_factory:
            self.port = None  # a renumbered adapter: ask again
            self.call_from_thread(self.choose_port)

    def _open_port(self):
        if self.radio is None:
            if self.serial_factory:
                self.ser = self.serial_factory()
            else:
                if not self.port:
                    raise ProtocolError(t("no_port"))
                self.ser = open_port(self.port)
            self.radio = Radio(self.ser)

    def _start(self, worker, *args):
        """Run a read or write worker.

        Opening the port does not restart the radio (measured 2026-11-15), the end of a
        session does (a write, `l`, a lost session). After such an end the handshake waits
        for the user to pass the radio's warning screen; at the first action of the
        launch there is nothing to wait for.
        """
        if not self.serial_factory and not self.port:
            self.notify(t("no_port"), severity="warning")
            self.choose_port()
            return
        alive = self.radio is not None and self.radio.session_alive
        if not self.restart_prompt or alive or not self.had_session:
            worker(*args)
            return

        def done(ok):
            if ok:
                worker(*args)
            else:
                self.status(t("restart_cancelled"))

        self.push_screen(RestartScreen(), done)

    def _session(self):
        self._open_port()
        if self.radio.session_alive:  # the keep-alive held it: no restart in between
            return self.radio
        ident = self.radio.connect(attempts=self.handshake_attempts)
        self.had_session = True  # from now on a closed session means a restarted radio
        self._start_keepalive()
        self.call_from_thread(
            self.status,
            t(
                "radio_ident",
                a=ident.texts[0],
                b=ident.texts[1],
                bands=" ".join(
                    "?" if b is None else f"{b[0]}-{b[1]}" for b in ident.bands
                ),
            ),
        )
        return self.radio

    def _start_keepalive(self):
        self._ka_stop = threading.Event()
        threading.Thread(
            target=self._keepalive_loop, args=(self._ka_stop,), daemon=True
        ).start()

    def _keepalive_loop(self, stop):
        while not stop.wait(KEEPALIVE_S):
            exc = self._keepalive_tick()
            if exc is not None:
                self.call_from_thread(self.status, t("session_lost", exc=exc))
                if isinstance(exc, PORT_ERRORS):
                    self._drop_port()
                return

    def _keepalive_tick(self):
        """One harmless read so the radio does not leave the session.

        Returns the error that ended the session, else None. Skipped while an
        operation holds the port: its own frames keep the session alive.
        """
        radio = self.radio
        if radio is None or not radio.session_alive:
            return None
        if not self.session_lock.acquire(blocking=False):
            return None
        try:
            radio.read_block(image.PASSWORD_ADDR, size=0x10)
        except (ProtocolError, *PORT_ERRORS) as exc:
            return exc
        finally:
            self.session_lock.release()
        return None

    def action_release(self):
        """Let go of the radio: close the port (the radio restarts)."""
        # A keep-alive read takes about 0.1 s; a real read or write takes far longer.
        if not self.session_lock.acquire(timeout=0.5):
            self.notify(t("release_busy"), severity="warning")
            return
        try:
            self._close_port()
        finally:
            self.session_lock.release()
        self.status(t("released"))
        self.refresh_chrome()

    def exit(self, *args, **kwargs):
        self._close_port()
        super().exit(*args, **kwargs)

    def _radio_sync(self, ranges, data):
        """Record that the radio holds `data` over `ranges` (read or written)."""
        for start, end in ranges:
            self.radio_data[start:end] = data[start:end]
            self.clean[start:end] = data[start:end]
        self.radio_known |= {
            r.name
            for r in image.DATA_REGIONS
            if all(any(a <= s and e <= b for a, b in ranges) for s, e in r.ranges)
        }

    def pending_regions(self):
        """Data zones that may differ from the radio; unread zones count."""
        data = self.image.data
        return [
            r
            for r in image.DATA_REGIONS
            if r.name not in self.radio_known
            or any(data[s:e] != self.radio_data[s:e] for s, e in r.ranges)
        ]

    def _progress(self, done, total):
        self.call_from_thread(
            self.query_one("#progress", ProgressBar).update, total=total, progress=done
        )

    def action_read(self):
        # The whole radio in one session (one restart), like "Read from radio"
        # of the CPS; the Memory tab reads only the zone chosen there.
        tab = self.query_one("#tabs", TabbedContent).active
        region = self.current_region() if tab == "tab-memory" else image.ALL
        self.status(t("reading", zone=zone_name(region.name)))
        self._start(self.read_worker, region)

    @work(thread=True, exclusive=True)
    @holding_session
    def read_worker(self, region):
        parts = []  # (start, bytes): only these ranges replace the image
        try:
            radio = self._session()
            # Like the CPS: password block first (16-byte read).
            pw = image.PASSWORD_ADDR
            parts.append((pw, radio.read_block(pw, size=0x10)))
            for start, end in image.read_ranges(region):
                if region is image.PASSWORD:
                    continue
                parts.append((start, radio.read_range(start, end, self._progress)))
        except (ProtocolError, *PORT_ERRORS) as exc:
            self.call_from_thread(
                self.notify,
                t("read_failed", exc=exc, hint=t("radio_hint")),
                severity="error",
            )
            if isinstance(exc, PORT_ERRORS):
                self._drop_port()
            return
        self.call_from_thread(self._apply_read, region, parts)

    def _apply_read(self, region, parts):
        """Merge what was read; edits made elsewhere meanwhile are kept."""
        for start, data in parts:
            self.image.data[start : start + len(data)] = data
        self._radio_sync(tuple((s, s + len(d)) for s, d in parts), self.image.data)
        self.refresh_all()
        self.last_read = datetime.now()
        self.last_read_what = zone_name(region.name)
        self.refresh_chrome()
        self.refresh_pending()
        self.status(t("read_done", zone=zone_name(region.name)))

    def action_write(self):
        region = self.current_region()
        word = CALIBRATION_WORD if region.calibration else None
        msg = t("write_confirm", zone=zone_name(region.name))

        def done(ok):
            if ok:
                path = self.image.backup(BACKUP_DIR, f"avant-ecriture-{region.name}")
                self.status(
                    t("backup_writing", path=path, names=zone_name(region.name))
                )
                self._start(self.write_worker, [region])

        self.push_screen(ConfirmScreen(msg, word), done)

    def action_write_changes(self):
        regions = self.pending_regions()
        if not regions:
            self.notify(t("write_nothing"))
            return
        names = ", ".join(r.name for r in regions)
        lines = [
            Content.from_markup(format_change(c)).plain for c in self.pending_changes()
        ]
        msg = "\n".join([t("write_changes_confirm", names=names), *lines[:12]])

        def done(ok):
            if ok:
                path = self.image.backup(BACKUP_DIR, "avant-ecriture-groupee")
                self.status(t("backup_writing", path=path, names=names))
                self._start(self.write_worker, regions)

        self.push_screen(ConfirmScreen(msg), done)

    @work(thread=True, exclusive=True)
    @holding_session
    def write_worker(self, regions):
        names = ", ".join(zone_name(r.name) for r in regions)
        snapshot = bytes(self.image.data)  # edits made meanwhile stay pending
        try:
            radio = self._session()
            # Like the CPS: the password block is read before any write.
            radio.read_block(image.PASSWORD_ADDR, size=0x10)
            for region in regions:
                for start, end in region.ranges:
                    radio.write_range(start, snapshot[start:end], self._progress)
                self._radio_sync(region.ranges, snapshot)
        except (ProtocolError, *PORT_ERRORS) as exc:
            self.call_from_thread(
                self.notify,
                t("write_failed", exc=exc, hint=t("radio_hint")),
                severity="error",
            )
            if isinstance(exc, PORT_ERRORS):
                self._drop_port()
            return
        # The radio leaves the session about 1.7 s after a write and restarts (also with the
        # vendor software): stop the keep-alive instead of reporting a lost session.
        radio.session_alive = False
        self._ka_stop.set()
        self.call_from_thread(self.status, t("write_done", zone=names))

    def action_quit(self):
        if self.image.data == self.clean:
            self.exit()
            return
        self.push_screen(
            ConfirmScreen(t("quit_confirm")),
            lambda ok: ok and self.exit(),
        )


def app_class(lang):
    """The application class with its footer shortcuts in `lang`."""
    i18n.set_language(lang)
    return type("KTA16App", (KTA16App,), {"BINDINGS": bindings()})


def main(argv=None):
    i18n.set_language(i18n.detect())
    parser = argparse.ArgumentParser(description=t("cli_desc"))
    parser.add_argument("--port", help=t("cli_port"))
    parser.add_argument("--emulator", action="store_true", help=t("cli_emulator"))
    parser.add_argument("--lang", choices=i18n.LANGUAGES, help=t("cli_lang"))
    parser.add_argument("image", nargs="?", help=t("cli_image"))
    args = parser.parse_args(argv)
    lang = args.lang or i18n.detect()
    cls = app_class(lang)
    factory = None
    if args.emulator:
        from kta16.emulator import FakeSerial, RadioEmulator

        emu = RadioEmulator(bytearray(b"\xff" * 0x4000))
        factory = lambda: FakeSerial(emu)
    app = cls(
        port=args.port,
        serial_factory=factory,
        ask_port=not args.port and not args.emulator,
    )
    if args.image:
        app.image = image.Image.load(args.image)
        app.file_path = args.image
    app.run()
