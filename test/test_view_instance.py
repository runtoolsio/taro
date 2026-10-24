"""Rendering of the lost verdict in instance tables (transport doc point 8)."""
from dataclasses import replace
from datetime import timedelta

from runtools.runcore.test.job import fake_job_run
from runtools.runcore.util import utc_now
from runtools.taro.theme import Theme
from runtools.taro.view import instance as view_inst


def _active(heartbeat_age_s=None):
    run = fake_job_run('j1', term_status=None)
    if heartbeat_age_s is None:
        return run
    return replace(run, heartbeat_at=utc_now() - timedelta(seconds=heartbeat_age_s))


def test_lost_run_status_cell_carries_verdict_and_age():
    assert view_inst.STATUS.value_fnc(_active(200)) == 'LOST 3m'


def test_live_run_status_cell_has_no_badge():
    assert 'LOST' not in view_inst.STATUS.value_fnc(_active(5))
    assert 'LOST' not in view_inst.STATUS.value_fnc(_active())


def test_history_rows_are_unaffected():
    run = replace(fake_job_run('j1'), heartbeat_at=utc_now() - timedelta(hours=1))  # ended: never lost

    assert 'LOST' not in view_inst.STATUS.value_fnc(run)
    assert view_inst.lost_aware([view_inst.JOB_ID])[0].colour_fnc(run) == view_inst.JOB_ID.colour_fnc(run)


def test_lost_aware_dims_the_whole_row_of_a_lost_run():
    [col] = view_inst.lost_aware([view_inst.JOB_ID])

    assert col.colour_fnc(_active(200)) == Theme.subtle
    assert col.colour_fnc(_active()) == view_inst.JOB_ID.colour_fnc(_active())


def test_jobs_counts_exclude_lost_from_running():
    from collections import Counter

    rows = [_active(5), _active(200)]

    assert Counter(r.job_id for r in rows if not r.is_lost()) == {'j1': 1}
    assert Counter(r.job_id for r in rows if r.is_lost()) == {'j1': 1}


def test_jobs_running_cell_shows_lost_separately():
    from runtools.taro.tui.jobs import JobRow, _running_display, _running_style

    assert _running_display(JobRow(stats=None, running=2)) == '2'
    assert _running_display(JobRow(stats=None, running=0, lost=1)) == '1 lost'
    assert _running_display(JobRow(stats=None, running=2, lost=1)) == '2 +1 lost'
    assert _running_style(JobRow(stats=None, running=2, lost=1)) == Theme.error


def test_jobs_metrics_report_lost_jobs():
    from runtools.runcore.job import JobStats
    from runtools.taro.tui.jobs import build_jobs_metrics

    live, lost = _active(5), _active(200)

    metrics = build_jobs_metrics([JobStats('j1')], [live, lost]).plain
    assert '0 running' not in metrics and '1 running' in metrics
    assert '1 lost' in metrics

    no_lost = build_jobs_metrics([JobStats('j1')], [live]).plain
    assert 'lost' not in no_lost


def test_active_row_takes_the_instance_heartbeat_and_passes_bare_run_through():
    from runtools.taro.tui.selector import active_row

    held = _active()  # stored before heartbeat refreshes, which emit no events
    current = _active(200)

    assert active_row(held, None) is held
    inst = type('Inst', (), {'snap': lambda self: current})()
    assert active_row(held, inst).is_lost()
