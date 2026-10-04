"""Live output handling of the TUI output panel — stream delivery overlapping the initial pull."""
from runtools.runcore.job import InstanceOutputEvent
from runtools.runcore.output import OutputLine
from runtools.runcore.test.job import fake_job_run
from runtools.runcore.util import utc_now
from runtools.taro.tui.widgets import OutputPanel


def _event(run, ordinal):
    return InstanceOutputEvent(run.metadata, OutputLine(f'line {ordinal}', ordinal), utc_now())


def test_replayed_lines_already_pulled_are_not_displayed_again():
    run = fake_job_run('job', term_status=None)
    panel = OutputPanel(None, run, live=True)
    panel._buffer.add_lines([OutputLine('line 1', 1), OutputLine('line 2', 2)])  # the initial pull

    for ordinal in (1, 2, 3):  # the stream replays the retained tail, then continues
        panel._on_output(_event(run, ordinal))

    assert [line.ordinal for line in panel._live_pending] == [3]
