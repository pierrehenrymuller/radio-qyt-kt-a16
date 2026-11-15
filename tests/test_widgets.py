"""Segmented buttons: one choice among a few, like the Cockpit mockup."""

import asyncio

from textual.app import App

from kta16.widgets import Segmented


class Harness(App):
    def __init__(self):
        super().__init__()
        self.changes = []

    def compose(self):
        yield Segmented(["HIGH", "LOW"], index=0, id="power")

    def on_segmented_changed(self, event):
        self.changes.append((event.segmented.id, event.index))


def run(scenario):
    async def go():
        app = Harness()
        async with app.run_test(size=(40, 8)) as pilot:
            await scenario(app, pilot, app.query_one("#power", Segmented))
        return app

    return asyncio.run(go())


def test_starts_on_the_given_option():
    async def scenario(app, pilot, seg):
        assert (seg.index, seg.value) == (0, "HIGH")

    run(scenario)


def test_arrow_keys_move_and_stop_at_the_ends():
    async def scenario(app, pilot, seg):
        seg.focus()
        await pilot.press("right")
        assert seg.value == "LOW"
        await pilot.press("right")  # no wrap: stays on the last option
        assert seg.value == "LOW"
        await pilot.press("left", "left")
        assert seg.value == "HIGH"

    app = run(scenario)
    assert app.changes == [("power", 1), ("power", 0)]


def test_click_selects_the_clicked_segment():
    async def scenario(app, pilot, seg):
        # " HIGH " is 6 cells, " LOW " follows; the border takes one cell
        await pilot.click("#power", offset=(9, 1))
        assert seg.value == "LOW"
        await pilot.click("#power", offset=(3, 1))
        assert seg.value == "HIGH"

    run(scenario)


def test_rejects_empty_options_and_bad_index():
    import pytest

    with pytest.raises(ValueError):
        Segmented([])
    with pytest.raises(ValueError):
        Segmented(["A", "B"], index=2)
