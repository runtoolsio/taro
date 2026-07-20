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
