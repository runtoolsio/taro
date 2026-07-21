"""Rendering of the liveness verdict in instance tables (transport doc point 8)."""
from runtools.runcore.job import InstanceLiveness
from runtools.runcore.test.job import fake_job_run
from runtools.taro.theme import Theme
from runtools.taro.view import instance as view_inst


def _row(liveness):
    return view_inst.ActiveInstanceRow(fake_job_run('j1', term_status=None), liveness)


def test_lost_run_status_cell_carries_verdict_and_age():
    assert view_inst.STATUS.value_fnc(_row(InstanceLiveness(200.0, True))) == 'LOST 3m'


def test_live_run_status_cell_has_no_badge():
    assert 'LOST' not in view_inst.STATUS.value_fnc(_row(InstanceLiveness(5.0, False)))
    assert 'LOST' not in view_inst.STATUS.value_fnc(_row(InstanceLiveness()))


def test_plain_job_run_rows_are_unaffected():
    run = fake_job_run('j1', term_status=None)  # history views pass bare JobRuns — no liveness

    assert 'LOST' not in view_inst.STATUS.value_fnc(run)
    assert view_inst.lost_aware([view_inst.JOB_ID])[0].colour_fnc(run) == view_inst.JOB_ID.colour_fnc(run)


def test_lost_aware_dims_the_whole_row_of_a_lost_run():
    [col] = view_inst.lost_aware([view_inst.JOB_ID])

    assert col.colour_fnc(_row(InstanceLiveness(200.0, True))) == Theme.subtle
    assert col.colour_fnc(_row(InstanceLiveness())) == view_inst.JOB_ID.colour_fnc(_row(InstanceLiveness()))


def test_row_delegates_run_attributes():
    row = _row(InstanceLiveness())

    assert view_inst.JOB_ID.value_fnc(row) == 'j1'
    assert row.lifecycle.created_at is not None  # sort key access path


def test_jobs_counts_exclude_lost_from_running():
    from collections import Counter

    from runtools.taro.tui import jobs as tui_jobs

    rows = [_row(InstanceLiveness(5.0, False)), _row(InstanceLiveness(200.0, True))]

    assert Counter(r.job_id for r in rows if not tui_jobs._is_lost(r)) == {'j1': 1}
    assert Counter(r.job_id for r in rows if tui_jobs._is_lost(r)) == {'j1': 1}


def test_jobs_running_cell_shows_lost_separately():
    from runtools.taro.tui.jobs import JobRow, _running_display, _running_style
    from runtools.taro.theme import Theme

    assert _running_display(JobRow(stats=None, running=2)) == '2'
    assert _running_display(JobRow(stats=None, running=0, lost=1)) == '1 lost'
    assert _running_display(JobRow(stats=None, running=2, lost=1)) == '2 +1 lost'
    assert _running_style(JobRow(stats=None, running=2, lost=1)) == Theme.error


def test_jobs_metrics_report_lost_jobs():
    from runtools.runcore.job import JobStats
    from runtools.taro.tui.jobs import build_jobs_metrics

    live, lost = _row(InstanceLiveness(5.0, False)), _row(InstanceLiveness(200.0, True))

    metrics = build_jobs_metrics([JobStats('j1')], [live, lost]).plain
    assert '0 running' not in metrics and '1 running' in metrics
    assert '1 lost' in metrics

    no_lost = build_jobs_metrics([JobStats('j1')], [live]).plain
    assert 'lost' not in no_lost


def test_active_row_attaches_liveness_and_passes_bare_run_through():
    from runtools.taro.tui.selector import active_row

    run = fake_job_run('j1', term_status=None)

    assert active_row(run, None) is run
    inst = type('Inst', (), {'liveness': InstanceLiveness(200.0, True)})()
    assert active_row(run, inst).liveness.is_lost
