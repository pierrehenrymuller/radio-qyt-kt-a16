"""Widgets of the TUI that Textual does not provide."""

from typing import ClassVar

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


class Segmented(Widget, can_focus=True):
    """A few joined buttons, one of them chosen: ` HIGH | LOW `.

    Left and right arrows (or a click) change the choice; it never wraps.
    """

    COMPONENT_CLASSES: ClassVar = {"segmented--active"}
    DEFAULT_CSS = """
    Segmented { width: auto; height: 3; border: round $panel; padding: 0; }
    Segmented:focus { border: round $accent; }
    Segmented > .segmented--active { background: $accent; color: $background; text-style: bold; }
    """
    BINDINGS: ClassVar = [
        Binding("left", "move(-1)", "", show=False),
        Binding("right", "move(1)", "", show=False),
    ]

    index = reactive(0)

    class Changed(Message):
        def __init__(self, segmented, index):
            super().__init__()
            self.segmented, self.index = segmented, index

    def __init__(self, options, index=0, **kwargs):
        super().__init__(**kwargs)
        options = list(options)
        if not options:
            raise ValueError("at least one option")
        if not 0 <= index < len(options):
            raise ValueError("index outside the options")
        self.options = options
        self.set_reactive(Segmented.index, index)

    @property
    def value(self):
        return self.options[self.index]

    def _label(self, i):
        return f" {self.options[i]} "

    def render(self):
        active = self.get_component_rich_style("segmented--active")
        text = Text(no_wrap=True)
        for i in range(len(self.options)):
            text.append(self._label(i), style=active if i == self.index else None)
        return text

    def _choose(self, index):
        if 0 <= index < len(self.options) and index != self.index:
            self.index = index
            self.post_message(self.Changed(self, index))

    def action_move(self, step):
        self._choose(self.index + step)

    def on_click(self, event):
        offset = event.get_content_offset(self)
        if offset is None:
            return
        start = 0
        for i in range(len(self.options)):
            start += len(self._label(i))
            if offset.x < start:
                self._choose(i)
                return
        self.focus()
