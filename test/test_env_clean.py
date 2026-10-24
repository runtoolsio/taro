"""Orphan transport-row policy of `taro env clean` (transport doc, remaining work 2D)."""
from datetime import timedelta

import pytest

from runtools.runcore.db import sqlite
from runtools.runcore.job import InstanceID
from runtools.runcore.output import OutputLine
from runtools.runcore.run import TerminationStatus
from runtools.runcore.test.job import fake_job_run
from runtools.runcore.util import utc_now
from runtools.taro.cmd.env import _orphan_rows


@pytest.fixture
def db():
    with sqlite.create_memory('clean_env') as database:
        yield database


def _run(db, job_id, *, ended_ago=None):
    """A stored run with a pending signal and an output tail; non-ended when ``ended_ago`` is None."""
    if ended_ago is None:
        run = fake_job_run(job_id, term_status=None)
    else:
        ended_at = utc_now().replace(microsecond=0) - ended_ago
        run = fake_job_run(job_id, created_at=ended_at - timedelta(minutes=10), ended_at=ended_at,
                           term_status=TerminationStatus.COMPLETED)
    db.init_run(job_id, 'r1', created_at=run.lifecycle.created_at)
    if ended_ago is None:
        db.store_active_runs(run)
    else:
        db.store_runs(run)
    _rows(db, run.instance_id)
    return run.instance_id


def _rows(db, instance_id):
    db.send_signal(instance_id, 'stop')
    db.append_output([(instance_id, OutputLine('line', 1))])


def _orphans(db):
    signals, tails = _orphan_rows(db)
    return sorted(s.instance_id.job_id for s in signals), sorted(i.job_id for i in tails)


def test_rows_of_ended_and_missing_runs_are_orphans(db):
    _run(db, 'ended', ended_ago=timedelta(hours=1))
    _rows(db, InstanceID('missing', 'r1'))

    assert _orphans(db) == (['ended', 'missing'], ['ended', 'missing'])


def test_rows_of_non_ended_runs_are_kept_including_lost_and_init_only(db):
    _run(db, 'active')
    lost = _run(db, 'lost')
    db._conn.execute("UPDATE runs SET heartbeat_at = '2000-01-01 00:00:00.000' WHERE job_id = 'lost'")
    db._conn.commit()
    _rows(db, db.init_run('init_only', 'r1', created_at=utc_now()))

    assert [r for r in db.read_active_runs() if r.instance_id == lost][0].is_lost()
    assert _orphans(db) == ([], [])


def test_recently_ended_tail_lingers_while_its_signal_is_orphaned(db):
    _run(db, 'just_ended', ended_ago=timedelta(seconds=1))

    assert _orphans(db) == (['just_ended'], [])
