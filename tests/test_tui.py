"""TUI driven headless against the emulator."""

import asyncio
import termios

from textual.widgets import Button, Input, Select, SelectionList, Switch

from kta16 import image, ports, protocol
from kta16.channels import Channel
from kta16.emulator import FakeSerial, RadioEmulator
from kta16.tui import ChannelScreen, ConfirmScreen, KTA16App, PortScreen, RestartScreen


def make_app():
    radio_image = bytearray(b"\xff" * 0x4000)
    src = image.Image(radio_image)
    src.set_channel(
        1,
        Channel(
            145_500_000,
            145_500_000,
            "OFF",
            "88.5",
            "HIGH",
            False,
            "OFF",
            False,
            True,
            None,
            "OFF",
            "QT",
            False,
            "LFPX",
        ),
    )
    radio_image[:] = src.data
    emu = RadioEmulator(radio_image)
    app = KTA16App(serial_factory=lambda: FakeSerial(emu))
    app.handshake_attempts = 1
    return app, emu


def plain(widget):
    """Text of a Static as the user sees it, markup removed."""
    from textual.content import Content

    content = widget.content
    return (
        content.plain
        if isinstance(content, Content)
        else Content.from_markup(str(content)).plain
    )


async def wait_workers(app, pilot):
    for _ in range(100):
        await pilot.pause(0.05)
        if not any(w.is_running for w in app.workers):
            return


def test_read_channels_then_write_back(tmp_path, monkeypatch):
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert app.image.channel(1).name == "LFPX"
            assert app.image.channel(1).tx_tone == "88.5"
            ch = app.image.channel(1)
            app.image.set_channel(2, ch.__class__(**{**ch.__dict__, "name": "COPY"}))
            await pilot.press("w")
            await pilot.click("#yes")
            await wait_workers(app, pilot)
        assert bytes(emu.image[0x1010:0x1014]) == b"COPY"
        assert list(tmp_path.iterdir())  # backup made before writing

    asyncio.run(scenario())


def test_calibration_write_needs_typed_word(tmp_path, monkeypatch):
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-memory"
            app.query_one("#region").value = "calibration"
            await pilot.pause()
            app.image.data[0x3C00] = 0x42
            await pilot.press("w")
            await pilot.click("#yes")  # word not typed: refused
            await wait_workers(app, pilot)
        assert emu.image[0x3C00] == 0xFF
        assert not list(tmp_path.iterdir())

    asyncio.run(scenario())


def test_poke_rejects_calibration_and_garbage():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-memory"
            await pilot.pause()
            poke = app.query_one("#poke")
            spanning = "3bf0=" + "00" * 0x220  # starts and ends outside, covers all
            for text in ("3c00=00", "zz=00", "4000=00", "2a00=", "2a00=0g",
                         spanning, "3b90=00", "3b80=" + "00" * 0x20):  # fmt: skip
                poke.value = text
                await poke.action_submit()
                await pilot.pause()
            assert app.image.data[0x3C00] == 0xFF
            assert app.image.data[0x3B90] == 0xFF and app.image.data[0x3E00] == 0xFF
            poke.value = "2a00=01 02"
            await poke.action_submit()
            await pilot.pause()
            assert app.image.data[0x2A00:0x2A02] == b"\x01\x02"

    asyncio.run(scenario())


def test_dtmf_tab_applies_codes():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-dtmf"
            await pilot.pause()
            app.query_one("#dtmf-code-1").value = "12*#"
            app.query_one("#dtmf-group").value = "*"
            app.query_one("#dtmf-space").value = "#"
            for name in ("master_id", "vice_id"):
                app.query_one(f"#dtmf-fn-{name}").value = "1"
            app.query_one("#dtmf-apply").press()
            await pilot.pause()
            assert app.image.data[0x2900:0x2905] == bytes.fromhex("01 02 0b 0c ff")
            app.query_one("#dtmf-code-2").value = "12E"
            app.query_one("#dtmf-apply").press()
            await pilot.pause()
            assert app.image.data[0x2910] == 0xFF  # refused, image untouched

    asyncio.run(scenario())


def test_edit_commands_of_signal_fm_and_calibration_tabs():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            cases = [
                (
                    "#tt-edit",
                    "enc 1 1981 1124",
                    lambda d: d[0x2D00:0x2D02] == b"\xbd\x07",
                ),
                ("#tt-edit", "enc 1 10 20", lambda d: d[0x2D00:0x2D02] == b"\xbd\x07"),
                ("#tt-edit", "reset 6500", lambda d: d[0x2FF0] == 64),
                ("#tt-edit", "reset 6550", lambda d: d[0x2FF0] == 64),
                ("#ft-edit", "dec CCIR1 1 23 7300", lambda d: d[0x25FB] == 72),
                ("#ft-edit", "dec CCIR1 1 23 59", lambda d: d[0x25FB] == 72),
                ("#ft-edit", "enc 1 12345 - - CCIR2", lambda d: d[0x250F] == 1),
                ("#ft-edit", "enc 1 1234 - - CCIR2", lambda d: d[0x250F] == 1),
                ("#fm-edit", "1 98.3 FJQX", lambda d: d[0x3008:0x300C] == b"FJQX"),
                ("#fm-edit", "1 150 BAD", lambda d: d[0x3008:0x300C] == b"FJQX"),
                ("#cal-edit", "power_high_1 0 12", lambda d: d[0x3C00] == 12),
                ("#cal-edit", "power_high_1 0 999", lambda d: d[0x3C00] == 12),
                ("#cal-edit", "nope 0 1", lambda d: d[0x3C00] == 12),
            ]
            for selector, text, check in cases:
                widget = app.query_one(selector)
                widget.value = text
                await widget.action_submit()
                await pilot.pause()
                assert check(app.image.data), (selector, text)

    asyncio.run(scenario())


def test_open_and_save_cps_text_file(tmp_path):
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)):
            app.image.data[0x0E02] = 9
            for name in ("a.dat", "c.img"):
                app._save_file(str(tmp_path / name))
            assert (tmp_path / "a.dat").read_bytes().startswith(b" 0  0  0 ")
            assert (tmp_path / "c.img").stat().st_size == 0x4000
            for name in ("a.dat", "c.img"):
                assert app._load_file(str(tmp_path / name)).data[0x0E02] == 9
            (tmp_path / "bad.dat").write_bytes(b"garbage")
            try:
                app._load_file(str(tmp_path / "bad.dat"))
            except ValueError:
                return
            raise AssertionError("corrupt file accepted")

    asyncio.run(scenario())


def test_channel_table_uses_radio_numbering_from_zero():
    # the radio shows the first channel as ch000 (user check: "LFPX sur ch002")
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            table = app.query_one("#channels")
            assert (table.get_row("1")[0], table.get_row("1")[2]) == ("0", "LFPX")
            assert table.get_row("200")[0] == "199"

    asyncio.run(scenario())


def test_default_is_a_single_handshake():
    # repeated handshakes make the real radio reboot in a loop
    assert KTA16App().handshake_attempts == 1


def written_addresses(frames):
    return {f[1] << 8 | f[2] for f in frames if f[0] == protocol.CMD_WRITE}


def test_write_modified_zones_in_one_session(tmp_path, monkeypatch):
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-memory"
            app.query_one("#region").value = "all"
            await pilot.pause()
            await pilot.press("r")
            await wait_workers(app, pilot)
            ch = app.image.channel(1)
            app.image.set_channel(2, ch.__class__(**{**ch.__dict__, "name": "COPY"}))
            app.image.data[0x3008:0x300C] = b"FJQX"
            start = len(emu.log)
            await pilot.press("a")
            await pilot.click("#yes")
            await wait_workers(app, pilot)
            frames = emu.log[start:]
            assert frames.count(protocol.HANDSHAKE) == 0  # the read left it open
            assert emu.log.count(protocol.HANDSHAKE) == 1  # one session in all
            addrs = written_addresses(frames)
            assert addrs, "nothing written"
            assert all(
                any(s <= a < e for s, e in image.CHANNELS.ranges + image.FM.ranges)
                for a in addrs
            )
            assert bytes(emu.image[0x1010:0x1014]) == b"COPY"
            assert bytes(emu.image[0x3008:0x300C]) == b"FJQX"
            assert list(tmp_path.iterdir())  # backup before writing
            # nothing left to write: no new session
            start = len(emu.log)
            await pilot.press("a")
            await pilot.pause()
            await wait_workers(app, pilot)
            assert emu.log[start:] == []

    asyncio.run(scenario())


def test_write_modified_zones_counts_unread_zones_and_skips_calibration(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.image.data[0x3C00] = 0x42  # calibration: never in a batch
            app.image.data[0x3DF0:0x3DF6] = b"123456"  # password: same
            await pilot.press("a")
            await pilot.click("#yes")
            await wait_workers(app, pilot)
            addrs = written_addresses(emu.log)
            for region in image.DATA_REGIONS:
                for s, e in region.ranges:
                    assert set(range(s, e, protocol.WRITE_SIZE)) <= addrs
            assert all(a < 0x3100 for a in addrs)
            assert emu.log.count(protocol.HANDSHAKE) == 1
            assert emu.image[0x3C00] == 0xFF
            assert app.pending_regions() == []  # all zones now known

    asyncio.run(scenario())


def test_quit_asks_when_changes_are_neither_written_nor_saved(tmp_path):
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.image.data[0x0E02] = 9
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            await pilot.click("#no")
            await pilot.pause()
            assert app.is_running
            app.file_path = str(tmp_path / "x.img")
            app._save_file(app.file_path)
            await pilot.press("q")
            await pilot.pause()
            assert not isinstance(app.screen, ConfirmScreen)

    asyncio.run(scenario())


def test_default_and_clear_keys_follow_the_tab():
    async def scenario():
        app, emu = make_app()
        app.image = image.Image(emu.image)
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-fm"
            await pilot.pause()
            await pilot.press("d")
            await pilot.click("#yes")
            await pilot.pause()
            assert app.image.data[0x3008:0x300D] == b"QZNEW"
            await pilot.press("c")
            await pilot.click("#yes")
            await pilot.pause()
            assert app.image.data[0x3000:0x3100] == bytes(0x100)
            app.query_one("#tabs").active = "tab-channels"
            await pilot.pause()
            await pilot.press("c")
            await pilot.click("#no")  # cancelled: image untouched
            await pilot.pause()
            assert app.image.channel(1).name == "LFPX"
            await pilot.press("d")  # no measured Default for channels
            await pilot.pause()
            assert not isinstance(app.screen, ConfirmScreen)
            await pilot.press("c")
            await pilot.click("#yes")
            await pilot.pause()
            assert app.image.channel(1) is None

    asyncio.run(scenario())


def test_dtmf_tab_times_rights_and_state():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-dtmf"
            await pilot.pause()
            for key, value in (("on", "80"), ("off", "90"), ("reset", "16000")):
                app.query_one(f"#dtmf-t-{key}").value = value
            app.query_one("#dtmf-t-delay").value = "500"
            app.query_one("#dtmf-group").value = "*"
            app.query_one("#dtmf-space").value = "#"
            app.query_one("#dtmf-mv").value = True
            for right in ("inspection", "monitor", "stun", "kill", "revive"):
                app.query_one(f"#dtmf-r-vice-{right}").value = right == "stun"
            app.query_one("#dtmf-s-rx_disable").value = False
            app.query_one("#dtmf-s-tx_disable").value = True
            app.query_one("#dtmf-apply").press()
            await pilot.pause()
            d = app.image.data
            assert d[0x29F0:0x29F2] == b"\x03\x04"
            assert d[0x2AF6:0x2AF8] == b"\x04\x9f"
            assert d[0x2AF0] == 1 and d[0x2AF2] & 0x1F == 0x04
            assert d[0x2AF3] & 0x03 == 0x02
            for bad in ("85", "abc", "-10"):
                app.query_one("#dtmf-t-on").value = bad
                app.query_one("#dtmf-apply").press()
                await pilot.pause()
                assert d[0x29F0] == 3, bad  # refused, image untouched

    asyncio.run(scenario())


def test_options_tab_edits_vfo_tones():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-options"
            await pilot.pause()
            for text, raw in (("D023N", b"\x01\x00"), ("bad", b"\x01\x00")):
                box = app.query_one("#vfo-rx-1")
                box.value = text
                await box.action_submit()
                await pilot.pause()
                assert app.image.data[0x0F30:0x0F32] == raw, text

    asyncio.run(scenario())


def test_adj_file_holds_calibration_only(tmp_path):
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)):
            app.image.data[0x3C00] = 12
            app.image.data[0x0E02] = 9  # options change, not in a .adj
            path = str(tmp_path / "cal.adj")
            app._save_file(path)
            assert app.image.data != app.clean  # options still unsaved
            assert app.clean[0x3C00] == 12
            app.image.data[0x3C00] = 0xFF
            app.image = app._load_file(path)
            assert app.image.data[0x3C00] == 12 and app.image.data[0x0E02] == 9

    asyncio.run(scenario())


def test_edit_made_during_a_read_is_kept(monkeypatch):
    # a full read lasts about 45 s on the real radio: the user may keep editing
    from kta16.link import Radio

    async def scenario():
        app, _ = make_app()
        original = Radio.read_range

        def slow_read(radio, start, end, progress=None):
            app.image.data[0x3C80] = 9  # calibration edited while the radio is read
            return original(radio, start, end, progress)

        monkeypatch.setattr(Radio, "read_range", slow_read)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")  # channels tab
            await wait_workers(app, pilot)
            assert app.image.channel(1).name == "LFPX"
            assert app.image.data[0x3C80] == 9  # not read by r: kept

    asyncio.run(scenario())


def test_channel_dialog_buttons_stay_visible_in_a_small_terminal():
    from kta16.tui import ChannelScreen

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(ChannelScreen(1, None))
            await pilot.pause()
            dialog = app.screen.query_one("#dialog").region
            for button_id in ("ok", "cancel"):
                region = app.screen.query_one(f"#{button_id}").region
                assert dialog.contains_region(region), button_id
                assert region.height >= 1, button_id
                assert region.bottom <= 30 and region.y >= 0, button_id

    asyncio.run(scenario())


def test_other_dialog_buttons_visible_in_a_small_terminal():
    from kta16.tui import ConfirmScreen, PathScreen

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(60, 14)) as pilot:
            for screen, ids in (
                (ConfirmScreen("Écrire ?", "CALIBRATION"), ("yes", "no")),
                (PathScreen("Ouvrir", "x.img"), ("ok", "cancel")),
            ):
                app.push_screen(screen)
                await pilot.pause()
                for bid in ids:
                    r = app.screen.query_one(f"#{bid}").region
                    assert r.height >= 1 and r.bottom <= 14, bid
                app.pop_screen()
                await pilot.pause()

    asyncio.run(scenario())


def test_themes_start_dark_and_toggle_with_t():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            assert app.theme == "atelier" and app.current_theme.dark
            await pilot.press("t")
            assert app.theme == "papier" and not app.current_theme.dark
            await pilot.press("t")
            assert app.theme == "atelier"

    asyncio.run(scenario())


def test_sidebar_switches_tabs_and_highlights_the_group():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.click("#nav-tab-dtmf")
            await pilot.pause()
            assert app.query_one("#tabs").active == "tab-dtmf"
            assert app.query_one("#nav-tab-dtmf").has_class("-active")
            assert not app.query_one("#nav-tab-channels").has_class("-active")

    asyncio.run(scenario())


def test_status_bar_shows_port_and_last_read():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            text = plain(app.query_one("#statusbar"))
            assert "jamais lue" in text and "radio simulée" in text
            await pilot.press("r")
            await wait_workers(app, pilot)
            text = plain(app.query_one("#statusbar"))
            assert "dernière lecture : toute la radio" in text

    asyncio.run(scenario())


def test_pending_panel_lists_each_change():
    async def scenario():
        app, emu = make_app()
        emu.image[0x0E02] = 5  # squelch on the radio
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-options"
            await pilot.pause()
            await pilot.press("r")  # options zone read: its fields can be compared
            await wait_workers(app, pilot)
            app.image.data[0x0E02] = 6
            app.refresh_pending()
            text = plain(app.query_one("#pending"))
            assert "Squelch Level" in text and "5 -> 6" in text

    asyncio.run(scenario())


def test_channel_list_marks_changed_rows():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert app.query_one("#channels").get_row("1")[1] == ""
            app.image.set_channel(
                2,
                app.image.channel(1).__class__(
                    **{**app.image.channel(1).__dict__, "name": "COPY"}
                ),
            )
            app.refresh_channels()
            assert app.query_one("#channels").get_row("2")[1] == "modifié"

    asyncio.run(scenario())


def test_channel_dialog_uses_segmented_buttons_and_switches():
    from textual.widgets import Switch

    from kta16.tui import ChannelScreen
    from kta16.widgets import Segmented

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(ChannelScreen(3, app.image.channel(3)))
            await pilot.pause()
            screen = app.screen
            assert screen.query_one("#power", Segmented).value == "HIGH"
            assert screen.query_one("#narrow", Segmented).index == 0  # wide
            assert screen.query_one("#busy_lock", Switch).value is False

    asyncio.run(scenario())


def test_channel_dialog_saves_segmented_and_switch_values():
    from textual.widgets import Button, Input, Switch

    from kta16.tui import ChannelScreen
    from kta16.widgets import Segmented

    async def scenario():
        app, _ = make_app()
        result = []
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(ChannelScreen(3, None), result.append)
            await pilot.pause()
            screen = app.screen
            screen.query_one("#name", Input).value = "test"
            screen.query_one("#rx", Input).value = "122.500"
            screen.query_one("#power", Segmented).index = 1  # LOW
            screen.query_one("#scan_add", Switch).value = True
            screen.query_one("#ok", Button).press()
            await pilot.pause()
        action, ch = result[0]
        assert action == "set"
        assert (ch.name, ch.rx_hz, ch.power, ch.scan_add) == (
            "TEST",
            122_500_000,
            "LOW",
            True,
        )

    asyncio.run(scenario())


def test_channel_dialog_warns_when_tx_is_outside_the_radio_bands():
    from textual.widgets import Input

    from kta16.tui import ChannelScreen

    async def scenario():
        app, _ = make_app()
        # band limits as the real radio reports them: 108-136 and 137-174 MHz
        app.image.data[0x3D80:0x3D88] = bytes([1, 0, 8, 1, 3, 6, 0, 1])
        app.image.data[0x3D90:0x3D98] = bytes([1, 3, 7, 1, 7, 4, 0, 1])
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(ChannelScreen(3, None))
            await pilot.pause()
            tx = app.screen.query_one("#tx", Input)
            tx.value = "136.500"
            await pilot.pause()
            assert "bandes" in str(app.screen.query_one("#tx-warn").content)
            tx.value = "145.500"
            await pilot.pause()
            assert str(app.screen.query_one("#tx-warn").content) == ""
            assert "137" in str(app.screen.query_one("#tx-ok").content)

    asyncio.run(scenario())


def test_write_all_shows_the_changes_before_writing(tmp_path, monkeypatch):
    from textual.widgets import Label

    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu = make_app()
        emu.image[0x0E02] = 5
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-options"
            await pilot.pause()
            await pilot.press("r")
            await wait_workers(app, pilot)
            app.image.data[0x0E02] = 6
            await pilot.press("a")
            await pilot.pause()
            text = " ".join(str(w.content) for w in app.screen.query(Label))
            assert "Squelch Level" in text
            await pilot.click("#no")
            await pilot.pause()

    asyncio.run(scenario())


def test_english_interface_when_asked():
    from kta16 import i18n
    from kta16.tui import app_class

    async def scenario():
        cls = app_class("en")
        radio = FakeSerial(RadioEmulator(bytearray(b"\xff" * 0x4000)))
        app = cls(serial_factory=lambda: radio)
        async with app.run_test(size=(160, 50)):
            descriptions = {b.key: b.description for b in cls.BINDINGS}
            assert descriptions["r"] == "Read radio" and descriptions["q"] == "Quit"
            assert "never read" in plain(app.query_one("#statusbar"))
            assert plain(app.query_one("#nav-tab-channels")).startswith("Channels")
            assert (
                str(app.query_one("#pending-panel").query_one(".panel-title").content)
                == "To write"
            )
        i18n.set_language("fr")

    asyncio.run(scenario())


def test_french_is_the_default_interface():
    from kta16 import i18n

    i18n.set_language("fr")
    assert i18n.t("pending_title") == "À écrire"


def test_zones_never_read_are_grouped_in_one_line():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)):
            app.refresh_pending()
            lines = plain(app.query_one("#pending")).splitlines()
            unread = [x for x in lines if "Jamais lues" in x]
            assert len(unread) == 1
            for zone in ("Canaux", "Options", "DTMF", "2-tone", "5-tone", "FM"):
                assert zone in unread[0]

    asyncio.run(scenario())


def test_status_bar_is_the_only_top_line_with_a_ready_light():
    from textual.widgets import Header

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)):
            assert not app.query(Header)
            text = plain(app.query_one("#statusbar"))
            assert text.startswith("KT-A16") and "radio simulée" in text
            assert "Prête" in text and app.query_one("#statusbar").region.y == 0

    asyncio.run(scenario())


def test_pending_panel_groups_changes_by_zone_with_before_and_after():
    async def scenario():
        app, emu = make_app()
        emu.image[0x0E02] = 5
        async with app.run_test(size=(160, 50)) as pilot:
            for tab in ("tab-options", "tab-channels"):
                app.query_one("#tabs").active = tab
                await pilot.pause()
                await pilot.press("r")
                await wait_workers(app, pilot)
            app.image.data[0x0E02] = 6
            app.refresh_pending()
            panel = app.query_one("#pending")
            lines = plain(panel).splitlines()
            assert lines[0] == "1"  # zones to write, alone and big, as in the mockup
            assert "Options" in lines and "  Squelch Level : 5 -> 6" in lines
            assert panel.content.markup.count("[$error]") == 1  # old value in red

    asyncio.run(scenario())


def test_footer_shows_how_many_zones_a_writes():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            active = {
                b.binding.key: b.binding.description
                for b in app.active_bindings.values()
            }
            assert active["a"].endswith("(6)")  # six data zones never read

    asyncio.run(scenario())


def test_sidebar_counts_changes_per_screen_and_marks_the_active_one():
    async def scenario():
        app, emu = make_app()
        emu.image[0x0E02] = 5
        async with app.run_test(size=(160, 50)) as pilot:
            for tab in ("tab-options", "tab-channels"):
                app.query_one("#tabs").active = tab
                await pilot.pause()
                await pilot.press("r")
                await wait_workers(app, pilot)
            app.image.data[0x0E02] = 6
            app.refresh_pending()
            assert plain(app.query_one("#nav-tab-options")).rstrip().endswith("1")
            assert plain(app.query_one("#nav-tab-channels")).rstrip().endswith("Canaux")
            assert app.query_one("#nav-tab-channels").has_class("-active")
            assert not app.query_one("#nav-tab-options").has_class("-active")

    asyncio.run(scenario())


def test_channel_list_has_a_title_with_the_programmed_count():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert "1 / 200" in plain(app.query_one("#channels-title"))

    asyncio.run(scenario())


def test_status_light_shows_the_open_session_after_a_read_then_ready_when_released():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            await pilot.pause(1.2)  # the bar refreshes every second
            assert "Session ouverte" in plain(app.query_one("#statusbar"))
            await pilot.press("l")
            await pilot.pause(1.2)
            assert "Prête" in plain(app.query_one("#statusbar"))

    asyncio.run(scenario())


def read_addresses(frames):
    return [f[1] << 8 | f[2] for f in frames if f[0] == protocol.CMD_READ]


def test_r_reads_the_whole_radio_in_one_session_from_any_tab():
    async def scenario():
        app, emu = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-options"
            await pilot.pause()
            await pilot.press("r")
            await wait_workers(app, pilot)
            addrs = read_addresses(emu.log)
            assert emu.log.count(protocol.HANDSHAKE) == 1
            assert 0x0000 in addrs and 0x30C0 in addrs and 0x3DF0 in addrs
            assert all(a < 0x3100 or a == 0x3DF0 for a in addrs)  # no calibration
            assert {r.name for r in image.DATA_REGIONS} <= app.radio_known
            assert "toute la radio" in plain(app.query_one("#statusbar"))

    asyncio.run(scenario())


def test_r_on_the_memory_tab_reads_only_the_chosen_zone():
    async def scenario():
        app, emu = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-memory"
            app.query_one("#region").value = "dtmf"
            await pilot.pause()
            await pilot.press("r")
            await wait_workers(app, pilot)
            addrs = set(read_addresses(emu.log)) - {0x3DF0}
            assert addrs == set(range(0x2900, 0x2B00, 0x40))
            assert "DTMF" in plain(app.query_one("#statusbar"))

    asyncio.run(scenario())


def test_options_never_read_say_so():

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-options"
            await pilot.pause()
            vfo = app.query_one("#vfo-freq-0")
            assert vfo.value == "" and vfo.placeholder == "non lue"
            squelch = app.query_one("#opt-squelch", Select)
            assert squelch.is_blank() and squelch.prompt == "non lue"

    asyncio.run(scenario())


def test_options_tab_groups_each_vfo_in_its_own_block():
    from textual.widgets import Static

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.query_one("#tabs").active = "tab-options"
            await pilot.pause()
            pane = app.query_one("#tab-options")
            order = [w.id for w in pane.query("Input, Select, .vfo-title") if w.id]
            a = order.index("vfo-title-A")
            b = order.index("vfo-title-B")
            assert a < order.index("vfo-freq-0") < order.index("opt-vfo_a_step") < b
            assert order.index("opt-squelch") < a  # general settings first
            labels = [
                str(w.content) for w in pane.query(Static) if "Step" in str(w.content)
            ]
            assert labels and all(not x.startswith(("A ", "B ", "C ")) for x in labels)

    asyncio.run(scenario())


def test_options_blocks_are_the_screen_lines_with_their_frequency():
    async def scenario():
        radio = image.Image()
        for line, digits in enumerate((12952500, 12527500, 11930500)):
            base = 0x0F00 + 0x20 * line
            radio.data[base : base + 8] = bytes(int(c) for c in f"{digits:08d}")
        emu = RadioEmulator(bytearray(radio.data))
        app = KTA16App(serial_factory=lambda: FakeSerial(emu))
        async with app.run_test(size=(160, 50)) as pilot:
            titles = [plain(app.query_one(f"#vfo-title-{v}")) for v in "ABC"]
            assert titles == ["Ligne A", "Ligne B", "Ligne C"]  # nothing read yet
            await pilot.press("r")
            await wait_workers(app, pilot)
            titles = [plain(app.query_one(f"#vfo-title-{v}")) for v in "ABC"]
            assert titles == [
                "Ligne A (129.525 MHz)",
                "Ligne B (125.275 MHz)",
                "Ligne C (119.305 MHz)",
            ]

    asyncio.run(scenario())


def test_options_tab_lists_the_steps_in_ascending_order():

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)):
            select = app.query_one("#opt-vfo_a_step", Select)
            labels = [
                str(p) for p, value in select._options if value is not Select.NULL
            ]
            assert labels == ["2.50", "5.00", "6.25", "8.33", "10.00", "12.50", "25.00"]

    asyncio.run(scenario())


def test_channel_list_scrolls_to_the_last_channel():
    from textual.widgets import DataTable

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(150, 45)) as pilot:
            table = app.query_one("#channels", DataTable)
            assert table.region.bottom <= app.size.height  # bounded by the screen
            table.focus()
            await pilot.press(*["pagedown"] * 3)  # one page is about 40 rows
            await pilot.pause()
            assert 100 < table.cursor_row < 199 and table.scroll_y > 0
            await pilot.press("ctrl+end")
            await pilot.pause()
            assert table.cursor_row == 199
            assert table.region.y + table.cursor_row - table.scroll_y < app.size.height

    asyncio.run(scenario())


def test_every_option_and_hex_table_is_bounded_by_the_screen():
    from textual.widgets import DataTable

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(150, 30)) as pilot:
            for tab, table_id in (
                ("tab-2tone", "tt-table"),
                ("tab-5tone", "ft-table"),
                ("tab-fm", "fm-table"),
                ("tab-calibration", "cal-table"),
                ("tab-memory", "hex"),
            ):
                app.query_one("#tabs").active = tab
                await pilot.pause()
                table = app.query_one(f"#{table_id}", DataTable)
                assert table.region.bottom <= app.size.height, tab

    asyncio.run(scenario())


def test_channel_name_box_takes_seven_characters_and_the_extra_symbols():
    from textual.widgets import Button, Input

    from kta16.tui import ChannelScreen

    async def scenario():
        app, _ = make_app()
        result = []
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(ChannelScreen(3, None), result.append)
            await pilot.pause()
            name = app.screen.query_one("#name", Input)
            assert name.max_length == 7
            name.value = "a-b_c+d"
            app.screen.query_one("#rx", Input).value = "122.500"
            app.screen.query_one("#ok", Button).press()
            await pilot.pause()
        assert result[0][1].name == "A-B_C+D"

    asyncio.run(scenario())


def test_channel_dialog_fills_name_and_frequency_from_aero_search(monkeypatch):
    hits = [
        {"key": "LFPX", "name": "PX GND", "mhz": 121.6, "desc": "VILLEPREUX Sol"},
        {"key": "LFPX", "name": "VOR PXE", "mhz": 113.75, "desc": "VOR PXE"},
    ]
    monkeypatch.setattr("kta16.aero.load", lambda: hits)

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            screen = ChannelScreen(3, None)
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one("#aero", Input).value = "lfpx"
            await pilot.pause()
            pick = screen.query_one("#aero_pick", SelectionList)
            pick.select(0)
            await pilot.pause()
            assert screen.query_one("#name", Input).value == "PX GND"
            assert screen.query_one("#rx", Input).value == "121.60000"
            assert screen.query_one("#tx", Input).value == "121.60000"  # TX = RX
            pick.deselect(0)
            pick.select(1)  # a VOR is a beacon: nothing to transmit to
            await pilot.pause()
            assert screen.query_one("#rx", Input).value == "113.75000"
            assert screen.query_one("#tx", Input).value == ""
            screen.query_one(
                "#aero", Input
            ).value = "zzzz"  # no hit: nothing is touched
            await pilot.pause()
            assert screen.query_one("#name", Input).value == "VOR PXE"

    asyncio.run(scenario())


def test_tx_band_warning_only_when_the_band_limits_were_read():
    async def scenario(limits):
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            if limits:  # VHF0 108-136 enabled, the other bands unused
                app.image.data[0x3D80 : 0x3D80 + 8] = bytes([1, 0, 8, 1, 3, 6, 0, 1])
            screen = ChannelScreen(3, None)
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one("#tx", Input).value = "145.50000"
            await pilot.pause()
            return str(screen.query_one("#tx-warn").render()).strip()

    assert asyncio.run(scenario(limits=False)) == ""  # blank image: limits unknown
    assert asyncio.run(scenario(limits=True)) != ""  # 145.5 is outside 108-136


class DeadSerial(FakeSerial):
    """Adapter unplugged or renumbered: tcflush answers EIO."""

    def reset_input_buffer(self):
        raise termios.error(5, "Input/output error")

    closed = False

    def close(self):
        self.closed = True


def test_lost_adapter_is_reported_and_port_dropped():
    async def scenario():
        emu = RadioEmulator(bytearray(b"\xff" * 0x4000))
        made = []

        def factory():
            made.append(DeadSerial(emu))
            return made[0]

        app = KTA16App(serial_factory=factory)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert app.radio is None and app.ser is None  # next action reopens
            assert made[0].closed  # the dead port was closed, not leaked

    asyncio.run(scenario())


ADAPTERS = [
    ports.Adapter("/dev/ttyUSB1", "/dev/ttyUSB1  Prolific  067b:2303", True),
    ports.Adapter("/dev/ttyUSB0", "/dev/ttyUSB0  1a86:7523", False),
]


def test_startup_prompt_picks_the_recommended_adapter(monkeypatch):
    monkeypatch.setattr(ports, "list_adapters", lambda: ADAPTERS)

    async def scenario():
        app = KTA16App(ask_port=True)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, PortScreen)
            await pilot.press("enter")  # first line = recommended
            await pilot.pause()
            assert app.port == "/dev/ttyUSB1"
            assert not isinstance(app.screen, PortScreen)

    asyncio.run(scenario())


def test_startup_prompt_escape_keeps_working_offline(monkeypatch):
    monkeypatch.setattr(ports, "list_adapters", lambda: ADAPTERS)

    async def scenario():
        app = KTA16App(ask_port=True)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.port is None
            assert not isinstance(app.screen, PortScreen)

    asyncio.run(scenario())


def test_no_prompt_without_adapter_or_with_explicit_port(monkeypatch):
    async def scenario(adapters, **kw):
        monkeypatch.setattr(ports, "list_adapters", lambda: adapters)
        app = KTA16App(**kw)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, PortScreen)

    asyncio.run(scenario([], ask_port=True))
    asyncio.run(scenario(ADAPTERS, port="/dev/ttyUSB0"))


ATIS_HIT = {"key": "LFPX", "name": "PX ATIS", "mhz": 128.3, "desc": "VILLEPREUX"}
VOR_HIT = {"key": "LFPX", "name": "VOR PXE", "mhz": 113.75, "desc": "VOR PXE"}
AVORD_HIT = {"key": "LFOA", "name": "OA APP", "mhz": 119.7, "desc": "AVORD Approche"}


def pick_aero(hit, monkeypatch, then=None):
    """Open a blank channel form, pick `hit`, return (result, tx_visible, switch)."""
    monkeypatch.setattr("kta16.aero.load", lambda: [hit])
    result, seen = [], {}

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            screen = ChannelScreen(3, None)
            app.push_screen(screen, result.append)
            await pilot.pause()
            screen.query_one("#aero", Input).value = hit["key"]
            await pilot.pause()
            screen.query_one("#aero_pick", SelectionList).select(0)
            await pilot.pause()
            seen["tx_visible"] = screen.query_one("#tx", Input).display
            seen["row_visible"] = screen.query_one("#tx_row").display
            seen["switch"] = screen.query_one("#tx_on", Switch).value
            if then:
                await then(screen, pilot)
            screen.query_one("#ok", Button).press()
            await pilot.pause()

    asyncio.run(scenario())
    return result[0][1], seen


def test_atis_pick_hides_tx_and_writes_200_mhz(monkeypatch):
    ch, seen = pick_aero(ATIS_HIT, monkeypatch)
    assert seen == {"tx_visible": False, "row_visible": True, "switch": False}
    assert ch.tx_hz == 200_000_000


def test_vor_pick_hides_tx_and_leaves_it_empty(monkeypatch):
    ch, seen = pick_aero(VOR_HIT, monkeypatch)
    assert seen == {"tx_visible": False, "row_visible": True, "switch": False}
    assert ch.tx_hz is None


def test_aerodrome_with_vor_in_its_name_keeps_tx_equal_rx(monkeypatch):
    ch, seen = pick_aero(AVORD_HIT, monkeypatch)
    assert seen == {"tx_visible": True, "row_visible": True, "switch": True}
    assert ch.tx_hz == 119_700_000


def test_switching_tx_on_copies_rx(monkeypatch):
    async def turn_on(screen, pilot):
        screen.query_one("#tx_on", Switch).value = True
        await pilot.pause()
        assert screen.query_one("#tx", Input).display
        assert screen.query_one("#tx", Input).value == "128.30000"

    ch, _ = pick_aero(ATIS_HIT, monkeypatch, turn_on)
    assert ch.tx_hz == 128_300_000


def test_reopening_a_200_mhz_channel_shows_tx_off():
    async def scenario():
        app, _ = make_app()
        result = []
        ch = Channel(
            128_300_000, 200_000_000, "OFF", "OFF", "LOW", False, "OFF", False,
            True, None, "OFF", "QT", False, "ATIS",
        )  # fmt: skip
        async with app.run_test(size=(160, 50)) as pilot:
            app.push_screen(ChannelScreen(3, ch), result.append)
            await pilot.pause()
            s = app.screen
            assert not s.query_one("#tx", Input).display
            assert not s.query_one("#tx_on", Switch).value
            s.query_one("#ok", Button).press()
            await pilot.pause()
        assert result[0][1].tx_hz == 200_000_000

    asyncio.run(scenario())


def test_channel_list_leaves_tx_blank_at_200_mhz():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            ch = Channel(
                128_300_000, 200_000_000, "OFF", "OFF", "LOW", False, "OFF", False,
                True, None, "OFF", "QT", False, "ATIS",
            )  # fmt: skip
            app.image.set_channel(1, ch)
            app.refresh_all()
            await pilot.pause()
            assert app.query_one("#channels").get_row("1")[4] == ""

    asyncio.run(scenario())


def move_scenario(keys):
    """Keys pressed on the channel list of the emulated radio (LFPX is channel 1)."""

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            table = app.query_one("#channels")
            table.focus()
            await pilot.pause()
            await pilot.press(*keys)
            await pilot.pause()
            return {
                n: app.image.channel(n).name if app.image.channel(n) else None
                for n in (1, 2, 3)
            }, table.cursor_row

    return asyncio.run(scenario())


def test_space_down_enter_moves_a_channel_down_and_the_cursor_follows():
    names, row = move_scenario(["space", "down", "enter"])
    assert names[1] is None and names[2] == "LFPX"
    assert row == 1  # row index = channel number - 1


def test_space_then_arrows_then_space_drops_and_arrows_move_the_cursor_again():
    names, row = move_scenario(["space", "down", "down", "up", "space", "down"])
    assert names[2] == "LFPX"  # down, down, up: ends on channel 2
    assert row == 2  # after the drop the arrow moves the cursor only


def test_escape_puts_the_channel_back():
    names, row = move_scenario(["space", "down", "down", "escape"])
    assert names[1] == "LFPX" and names[3] is None
    assert row == 0


def test_move_stops_at_the_first_channel():
    names, row = move_scenario(["space", "up", "up"])
    assert names[1] == "LFPX" and row == 0


def test_without_move_mode_arrows_only_move_the_cursor():
    names, row = move_scenario(["down", "down"])
    assert names[1] == "LFPX" and row == 2


class TrackedSerial(FakeSerial):
    closed = False

    def close(self):
        self.closed = True


def session_app():
    app, emu = make_app()
    ports = []

    def factory():
        ports.append(TrackedSerial(emu))
        return ports[-1]

    app.serial_factory = factory
    return app, emu, ports


def handshakes(emu):
    return emu.log.count(protocol.HANDSHAKE)


def test_read_then_write_share_one_session(tmp_path, monkeypatch):
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu, _ = session_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            await pilot.press("w")
            await pilot.click("#yes")
            await wait_workers(app, pilot)
            assert handshakes(emu) == 1

    asyncio.run(scenario())


def test_keepalive_reads_the_password_block_and_yields_to_an_operation():
    async def scenario():
        app, emu, _ = session_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            before = len(emu.log)
            app._keepalive_tick()
            assert bytes([protocol.CMD_READ, 0x3D, 0xF0, 0x10]) in emu.log[before:]
            with app.session_lock:  # an operation holds the port: no frame sent
                before = len(emu.log)
                app._keepalive_tick()
                assert len(emu.log) == before

    asyncio.run(scenario())


def test_lost_session_is_reported_and_the_next_read_reconnects():
    async def scenario():
        app, emu, _ = session_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            app.radio.timeout = 0.05
            emu.silent = True  # the radio left the session
            assert app._keepalive_tick() is not None  # the error that ended it
            assert not app.radio.session_alive
            emu.silent = False
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert handshakes(emu) == 2
            assert app.radio.session_alive

    asyncio.run(scenario())


def test_release_closes_the_port_and_the_next_read_reopens_it():
    async def scenario():
        app, emu, ports = session_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            await pilot.press("l")
            await pilot.pause()
            assert ports[0].closed and app.radio is None and app.ser is None
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert len(ports) == 2 and handshakes(emu) == 2

    asyncio.run(scenario())


def open_saved(name, rx, tx, switch_to=None):
    """Open the form of a channel saved earlier; return (tx box shown, switch shown, switch, result)."""
    ch = Channel(
        rx, tx, "OFF", "OFF", "LOW", False, "OFF", False, True, None, "OFF", "QT",
        False, name,
    )  # fmt: skip
    result, seen = [], {}

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.push_screen(ChannelScreen(3, ch), result.append)
            await pilot.pause()
            s = app.screen
            seen["tx"] = s.query_one("#tx", Input).display
            seen["row"] = s.query_one("#tx_row").display
            seen["on"] = s.query_one("#tx_on", Switch).value
            seen["value"] = s.query_one("#tx", Input).value
            if switch_to is not None:
                s.query_one("#tx_on", Switch).value = switch_to
                await pilot.pause()
            s.query_one("#ok", Button).press()
            await pilot.pause()

    asyncio.run(scenario())
    return seen, result[0][1]


def test_saved_atis_with_tx_shows_the_switch_on_and_can_be_turned_off():
    seen, ch = open_saved("PX ATIS", 128_300_000, 128_300_000, switch_to=False)
    assert seen == {"tx": True, "row": True, "on": True, "value": "128.30000"}
    assert ch.tx_hz == 200_000_000


def test_saved_atis_keeps_a_tx_different_from_rx_when_untouched():
    seen, ch = open_saved("PX ATIS", 128_300_000, 127_000_000)
    assert seen["value"] == "127.00000" and ch.tx_hz == 127_000_000


def test_saved_atis_with_empty_tx_opens_off_and_writes_200_mhz():
    seen, ch = open_saved("PX ATIS", 128_300_000, None)
    assert (seen["tx"], seen["row"], seen["on"]) == (False, True, False)
    assert ch.tx_hz == 200_000_000


def test_saved_vor_shows_the_switch_and_off_leaves_tx_empty():
    seen, ch = open_saved("VOR PXE", 113_750_000, 113_750_000, switch_to=False)
    assert seen["row"] and seen["on"]
    assert ch.tx_hz is None


def test_saved_plain_channel_has_the_switch_on_and_off_writes_200_mhz():
    seen, ch = open_saved("OA APP", 119_700_000, 119_700_000)
    assert (seen["tx"], seen["row"], seen["on"]) == (True, True, True)
    assert ch.tx_hz == 119_700_000
    _, ch = open_saved("OA APP", 119_700_000, 119_700_000, switch_to=False)
    assert ch.tx_hz == 200_000_000


def test_switching_a_saved_channel_back_on_copies_rx():
    seen, ch = open_saved("PX ATIS", 128_300_000, 200_000_000, switch_to=True)
    assert (seen["tx"], seen["on"]) == (False, False)
    assert ch.tx_hz == 128_300_000


def prompting_app():
    app, emu, ports = session_app()
    app.restart_prompt = True  # a real port restarts the radio when it opens
    return app, emu, ports


def test_first_read_after_the_launch_goes_straight_to_the_handshake():
    # Measured on the radio (2026-11-15): opening the port does not restart it.
    async def scenario():
        app, emu, ports = prompting_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert not isinstance(app.screen, RestartScreen)
            assert handshakes(emu) == 1 and len(ports) == 1
            assert app.image.channel(1).name == "LFPX"

    asyncio.run(scenario())


def test_cancelling_the_wait_after_a_released_session_sends_nothing():
    async def scenario():
        app, emu, _ = prompting_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            await pilot.press("l")  # the radio restarts
            await pilot.pause()
            before = len(emu.log)
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, RestartScreen)
            await pilot.click("#cancel")
            await pilot.pause()
            assert len(emu.log) == before and handshakes(emu) == 1

    asyncio.run(scenario())


def test_wait_only_after_a_session_ended_never_while_it_is_open():
    async def scenario():
        app, emu, ports = prompting_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            await pilot.press("r")  # session open: straight to the read
            await wait_workers(app, pilot)
            assert not isinstance(app.screen, RestartScreen)
            assert handshakes(emu) == 1
            app.radio.timeout = 0.05
            emu.silent = True
            assert app._keepalive_tick() is not None  # the radio left the session
            emu.silent = False
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, RestartScreen)  # it restarted: wait
            assert len(ports) == 1  # same open port
            await pilot.click("#ok")
            await wait_workers(app, pilot)
            assert handshakes(emu) == 2 and app.radio.session_alive

    asyncio.run(scenario())


def test_write_then_read_waits_for_the_restart_the_write_caused(tmp_path, monkeypatch):
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu, _ = prompting_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("w")  # first action of the launch: no wait
            await pilot.click("#yes")
            await wait_workers(app, pilot)
            assert handshakes(emu) == 1 and not isinstance(app.screen, RestartScreen)
            await pilot.press("w")
            await pilot.click("#yes")
            await pilot.pause()
            assert isinstance(app.screen, RestartScreen)  # the write restarted it
            await pilot.click("#ok")
            await wait_workers(app, pilot)
            assert handshakes(emu) == 2

    asyncio.run(scenario())


def test_no_port_chosen_asks_again_instead_of_reading():
    async def scenario():
        app, _, _ = prompting_app()
        app.serial_factory = None  # a real run without a port
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await pilot.pause()
            assert not isinstance(app.screen, RestartScreen)

    asyncio.run(scenario())


MULTI_HITS = [
    {"key": "LFPG", "name": "PG ATIS", "mhz": 128.3, "desc": "PARIS CDG"},
    {"key": "LFPG", "name": "PG TWR", "mhz": 118.7, "desc": "PARIS CDG"},
    {"key": "LFPG", "name": "VOR CGN", "mhz": 115.35, "desc": "VOR CGN"},
]


def test_several_aero_lines_give_one_channel_each(monkeypatch):
    monkeypatch.setattr("kta16.aero.load", lambda: MULTI_HITS)
    result = []

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            screen = ChannelScreen(3, None)
            app.push_screen(screen, result.append)
            await pilot.pause()
            screen.query_one("#aero", Input).value = "LFPG"
            await pilot.pause()
            pick = screen.query_one("#aero_pick", SelectionList)
            for i in (0, 1, 2):
                pick.select(i)
            await pilot.pause()
            assert "3" in str(screen.query_one("#aero_count").render())
            assert screen.query_one("#name", Input).value == "PG ATIS"  # first line
            screen.query_one("#busy_lock", Switch).value = True  # a form setting
            screen.query_one("#ok", Button).press()
            await pilot.pause()

    asyncio.run(scenario())
    action, chans = result[0]
    assert action == "insert"
    assert [c.name for c in chans] == ["PG ATIS", "PG TWR", "VOR CGN"]
    assert [c.rx_hz for c in chans] == [128_300_000, 118_700_000, 115_350_000]
    assert [c.tx_hz for c in chans] == [
        200_000_000,
        118_700_000,
        None,
    ]  # ATIS, TX=RX, VOR
    assert all(c.busy_lock for c in chans)


def _plain_channel(name):
    return Channel(
        118_000_000, 118_000_000, "OFF", "OFF", "LOW", False, "OFF", False, True,
        None, "OFF", "QT", False, name,
    )  # fmt: skip


def test_inserting_channels_pushes_the_next_ones():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.image.set_channel(1, _plain_channel("OLD"))
            app.image.set_channel(2, _plain_channel("KEEP"))
            new = [_plain_channel(n) for n in ("A", "B", "C")]
            app.apply_channel_result(1, ("insert", new))
            await pilot.pause()
            names = [app.image.channel(n).name for n in (1, 2, 3, 4)]
            assert names == ["A", "B", "C", "KEEP"]  # 1 is edited, 2 onwards inserted

    asyncio.run(scenario())


def test_inserting_without_room_changes_nothing():
    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            for n in range(2, 201):
                app.image.set_channel(n, _plain_channel("X"))
            before = bytes(app.image.data)
            app.apply_channel_result(1, ("insert", [_plain_channel("A")] * 2))
            await pilot.pause()
            assert bytes(app.image.data) == before

    asyncio.run(scenario())


def block_scenario(keys, setup=None, after=None):
    """Channels A..E on 1..5 (the emulated radio's LFPX replaced), keys on the list."""

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            for n, name in enumerate("ABCDE", 1):
                app.image.set_channel(n, _plain_channel(name))
            app.refresh_channels()
            table = app.query_one("#channels")
            table.focus()
            await pilot.pause()
            if setup:
                await setup(app, pilot, table)
            await pilot.press(*keys)
            await pilot.pause()
            names = [
                app.image.channel(n).name if app.image.channel(n) else None
                for n in range(1, 8)
            ]
            extra = await after(app, pilot, table) if after else None
            return names, table.cursor_row, extra

    return asyncio.run(scenario())


def test_shift_arrows_select_a_block_and_arrows_move_all_of_it():
    names, row, _ = block_scenario(
        ["shift+down", "shift+down", "space", "down", "enter"]
    )
    assert names[:5] == ["D", "A", "B", "C", "E"]  # A B C moved down one place
    assert row == 3  # the cursor followed the block (it was on the last channel of it)


def test_block_moves_back_up():
    names, row, _ = block_scenario(
        ["down", "down", "shift+down", "space", "up", "enter"]
    )  # C D selected, up one place
    assert names[:5] == ["A", "C", "D", "B", "E"]
    assert row == 2


def test_escape_puts_the_whole_block_back():
    names, row, _ = block_scenario(["shift+down", "space", "down", "down", "escape"])
    assert names[:5] == ["A", "B", "C", "D", "E"] and row == 1


def test_escape_without_a_move_clears_the_selection():
    async def after(app, pilot, table):
        return table.block

    _, _, block = block_scenario(["shift+down", "escape"], after=after)
    assert block is None


def test_block_stops_at_the_first_channel():
    names, _, _ = block_scenario(["shift+down", "space", "up", "up"])
    assert names[:3] == ["A", "B", "C"]


def test_shift_click_extends_the_selection_without_opening_the_form():
    async def setup(app, pilot, table):
        await pilot.click(
            "#channels", offset=(8, 1 + 3), shift=True
        )  # row of channel 4
        await pilot.pause()

    async def after(app, pilot, table):
        return table.block, type(app.screen).__name__

    _, _, (block, screen) = block_scenario([], setup=setup, after=after)
    assert block == (1, 4) and screen != "ChannelScreen"


def test_a_plain_arrow_clears_the_selection():
    async def after(app, pilot, table):
        return table.block

    _, _, block = block_scenario(["shift+down", "down"], after=after)
    assert block is None


def test_aero_count_message_wraps_inside_its_column(monkeypatch):
    monkeypatch.setattr("kta16.aero.load", lambda: MULTI_HITS)

    async def scenario():
        app, _ = make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = ChannelScreen(3, None)
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one("#aero", Input).value = "LFPG"
            await pilot.pause()
            pick = screen.query_one("#aero_pick", SelectionList)
            pick.select(0)
            pick.select(1)
            await pilot.pause()
            count = screen.query_one("#aero_count")
            column = count.parent
            # the whole sentence is shown: it wraps on several lines inside the column
            assert count.region.height >= 2
            assert count.region.width <= column.region.width

    asyncio.run(scenario())


def test_a_write_ends_the_session_and_the_next_action_waits_for_the_restart(
    tmp_path, monkeypatch
):
    # Measured on the radio (2026-11-15): it leaves the session 1.7 s after a write
    # and restarts; reads keep it for as long as the keep-alive runs.
    monkeypatch.setattr("kta16.tui.BACKUP_DIR", tmp_path)

    async def scenario():
        app, emu, _ = prompting_app()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("r")
            await wait_workers(app, pilot)
            assert app.radio.session_alive
            await pilot.press("w")
            await pilot.click("#yes")
            await wait_workers(app, pilot)
            assert not app.radio.session_alive  # no keep-alive on a radio that restarts
            before = len(emu.log)
            assert app._keepalive_tick() is None and len(emu.log) == before
            assert "redémarre" in plain(app.query_one("#status"))
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, RestartScreen)  # it restarted: wait again

    asyncio.run(scenario())
