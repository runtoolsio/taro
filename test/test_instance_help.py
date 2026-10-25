"""Contextual help on the instance screen: `?` toggles Textual's help panel, which shows the focused panel's keys."""
import asyncio

from textual.app import App
from textual.widgets import HelpPanel, Markdown

from runtools.runcore.test.job import fake_job_run
from runtools.taro.tui.instance_screen import InstanceScreen
from runtools.taro.tui.widgets import OutputPanel


class _InstanceApp(App):

    def on_mount(self) -> None:
        self.push_screen(InstanceScreen(job_run=fake_job_run('job')))


def _help_text(screen) -> str:
    return screen.query_one(HelpPanel).query_one(Markdown).source


def test_question_mark_toggles_help_for_the_focused_panel():
    async def scenario():
        app = _InstanceApp()
        async with app.run_test(size=(140, 40)) as pilot:
            screen = app.screen
            screen.query_one(OutputPanel).focus()
            await pilot.press('question_mark')
            await pilot.pause()
            assert '## Output' in _help_text(screen)  # the focused panel's own help

            screen.query_one('PhaseTree').focus()
            await pilot.pause()
            assert '## Instance' in _help_text(screen)  # inherited from the screen

            await pilot.press('question_mark')
            await pilot.pause()
            assert not screen.query(HelpPanel)

    asyncio.run(scenario())
