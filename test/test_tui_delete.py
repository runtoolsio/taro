"""Deleting a history run the login may not delete: the dashboard says why and keeps running."""
import asyncio

from textual.app import App

from runtools.runcore.db import PermissionDeniedError
from runtools.runcore.job import InstanceObservableNotifications
from runtools.runcore.test.job import fake_job_run
from runtools.taro.tui.dashboard import DashboardScreen
from runtools.taro.tui.selector import LinkedTable


class _ViewerConnector:
    """Just enough of an EnvironmentConnector for the dashboard, connected as a login that can't delete."""
    output_backends = ()
    notifications = InstanceObservableNotifications()

    def get_instance(self, instance_id):
        return None

    def remove_history_runs(self, run_match):
        raise PermissionDeniedError('billing', 'permission denied for table runs')


class _DashboardApp(App):

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen(_ViewerConnector(), [], [fake_job_run('backup')]))


def test_denied_delete_is_notified_and_the_dashboard_keeps_running():
    async def scenario():
        app = _DashboardApp()
        async with app.run_test() as pilot:
            history = app.screen.query_one("#history-table", LinkedTable)
            history.focus()
            await pilot.press("D", "y")
            await pilot.pause()
            return (isinstance(app.screen, DashboardScreen), history.row_count,
                    [notification.message for notification in app._notifications])

    on_dashboard, rows, messages = asyncio.run(scenario())

    assert on_dashboard
    assert rows == 1
    assert messages == ["Permission denied in environment 'billing': permission denied for table runs"]
