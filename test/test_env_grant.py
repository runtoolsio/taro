"""`taro env grant`: postgres only, and refusals name what's missing — nothing is granted."""
import pytest
from typer.testing import CliRunner

from runtools.runcore.db import NotEnvironmentOwnerError, ProfileRolesNotFoundError
from runtools.runcore.env import EnvironmentEntry, EnvironmentKind
from runtools.taro.cmd import env

POSTGRES = EnvironmentEntry(id='billing', kind=EnvironmentKind.POSTGRES, location='postgresql://rt@db/rt')


@pytest.fixture
def grants(monkeypatch):
    calls = []
    monkeypatch.setattr(env, 'lookup', lambda name: POSTGRES)
    monkeypatch.setattr(env, 'grant_profiles', lambda entry, prefix: calls.append((entry.id, prefix)))
    return calls


def test_profiles_are_granted_to_the_environment(grants):
    result = CliRunner().invoke(env.app, ['grant', 'billing', '--profiles', 'runtools'])

    assert result.exit_code == 0
    assert grants == [('billing', 'runtools')]


def test_grant_needs_a_postgres_environment(grants, monkeypatch):
    monkeypatch.setattr(env, 'lookup', lambda name: EnvironmentEntry(id=name, kind=EnvironmentKind.LOCAL))

    result = CliRunner().invoke(env.app, ['grant', 'dev', '--profiles', 'runtools'])

    assert result.exit_code == 2
    assert not grants


@pytest.mark.parametrize('error, shown', [
    (ProfileRolesNotFoundError(['runtools_node', 'runtools_viewer']), 'runtools_node, runtools_viewer'),
    (NotEnvironmentOwnerError('billing'), 'Not the owner'),
])
def test_refusals_say_why(monkeypatch, error, shown):
    def grant_profiles(entry, prefix):
        raise error

    monkeypatch.setattr(env, 'lookup', lambda name: POSTGRES)
    monkeypatch.setattr(env, 'grant_profiles', grant_profiles)

    result = CliRunner().invoke(env.app, ['grant', 'billing', '--profiles', 'runtools'])

    assert result.exit_code == 1
    assert shown in ' '.join(result.output.split())
    assert 'nothing was granted' in ' '.join(result.output.split())
