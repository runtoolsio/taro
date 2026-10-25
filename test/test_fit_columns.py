"""Table columns fit the terminal: low-priority columns are hidden instead of scrolling sideways."""
import asyncio

from textual.app import App

from runtools.runcore.job import InstanceObservableNotifications
from runtools.runcore.test.job import fake_job_run
from runtools.taro.tui.dashboard import ACTIVE_COLUMNS, ACTIVE_DROP_ORDER, DashboardScreen, HISTORY_COLUMNS
from runtools.taro.tui.selector import LinkedTable, fit_columns


def _names(columns):
    return [col.name for col in columns]


def test_wide_table_keeps_every_column():
    assert fit_columns(ACTIVE_COLUMNS, 200, ACTIVE_DROP_ORDER) == list(ACTIVE_COLUMNS)


def test_narrow_table_drops_only_as_many_columns_as_needed_least_important_first():
    assert _names(fit_columns(ACTIVE_COLUMNS, 100, ACTIVE_DROP_ORDER)) == [
        'N', 'JOB ID', 'RUN ID', 'CREATED', 'TIME', 'STATUS']  # PHASES and WARN went first


def test_half_screen_pane_keeps_job_time_and_status():
    assert _names(fit_columns(ACTIVE_COLUMNS, 63, ACTIVE_DROP_ORDER)) == ['JOB ID', 'TIME', 'STATUS']


def test_unknown_width_keeps_every_column():
    assert fit_columns(ACTIVE_COLUMNS, 0, ACTIVE_DROP_ORDER) == list(ACTIVE_COLUMNS)


class _Connector:
    """Just enough of an EnvironmentConnector for the dashboard to mount."""
    output_backends = ()
    notifications = InstanceObservableNotifications()

    def get_instance(self, instance_id):
        return None


class _DashboardApp(App):

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen(_Connector(), [], [fake_job_run('backup'), fake_job_run('report')]))


def _column_offsets(table):
    """Column name → x offset of the column inside the table."""
    offsets, x = {}, 0
    for column in table.columns.values():
        offsets[str(column.key.value)] = x
        x += column.get_render_width(table)
    return offsets


def _shared_column_offsets(width):
    async def scenario():
        app = _DashboardApp()
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause(0.3)
            active, history = (_column_offsets(table) for table in app.screen.query(LinkedTable))
            shared = [name for name in active if name in history]
            return shared, [active[name] for name in shared], [history[name] for name in shared]

    return asyncio.run(scenario())


def _table_layout(width):
    async def scenario():
        app = _DashboardApp()
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause(0.3)
            return [(len(table.columns), table.virtual_size.width <= table.size.width)
                    for table in app.screen.query(LinkedTable)]

    return asyncio.run(scenario())


def test_dashboard_in_a_split_pane_does_not_scroll_sideways():
    assert [fits for _, fits in _table_layout(67)] == [True, True]


def test_dashboard_on_a_wide_terminal_shows_every_column():
    assert [count for count, _ in _table_layout(200)] == [len(ACTIVE_COLUMNS), len(HISTORY_COLUMNS)]


def test_leading_columns_shared_by_both_tables_line_up():
    shared, active_x, history_x = _shared_column_offsets(200)

    assert shared[:5] == ['N', 'JOB ID', 'RUN ID', 'CREATED', 'TIME']
    assert active_x[:5] == history_x[:5]  # columns after TIME differ per table (PHASES vs ENDED, TERM)


def test_leading_columns_line_up_in_a_split_pane():
    shared, active_x, history_x = _shared_column_offsets(67)

    assert shared[0] == 'JOB ID' and active_x[0] == history_x[0]
