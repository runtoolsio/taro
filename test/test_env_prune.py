"""`taro env prune` removes ended runs only: an active run is never history."""
from datetime import timedelta

import pytest

from runtools.runcore.run import TerminationStatus
from runtools.runcore.test.job import fake_job_run
from runtools.runcore.util import utc_now
from runtools.taro.cmd.env import _prune_match

ACTIVE = fake_job_run('report', term_status=None)


def _ended(days_ago):
    ended_at = utc_now() - timedelta(days=days_ago)
    return fake_job_run('report', created_at=ended_at - timedelta(minutes=10), ended_at=ended_at,
                        term_status=TerminationStatus.COMPLETED)


@pytest.mark.parametrize('keep_days', [0, 7])
def test_active_runs_are_never_pruned(keep_days):
    match, _ = _prune_match('*', keep_days)

    assert not match(ACTIVE)


def test_keep_zero_prunes_every_ended_run():
    match, _ = _prune_match('*', 0)

    assert match(_ended(days_ago=0))


def test_keep_days_prunes_only_runs_ended_before_them():
    match, _ = _prune_match('*', 7)

    assert match(_ended(days_ago=8))
    assert not match(_ended(days_ago=6))
