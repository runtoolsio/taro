"""`taro env create --grant-profiles`: postgres only, and a missing role fails the creation with a clear message."""
from typer.testing import CliRunner

from runtools.runcore.db import ProfileRolesNotFoundError
from runtools.taro.cmd import env


def test_grant_profiles_are_passed_to_the_creation(monkeypatch):
    calls = []
    monkeypatch.setattr(env, 'create_environment', lambda entry, config, **options: calls.append(options))

    result = CliRunner().invoke(env.app, ['create', 'billing', '--dsn', 'postgresql://rt@db/rt',
                                          '--grant-profiles', 'billing'])

    assert result.exit_code == 0
    assert calls == [{'grant_profiles': 'billing'}]


def test_grant_profiles_need_a_postgres_environment(monkeypatch):
    calls = []
    monkeypatch.setattr(env, 'create_environment', lambda entry, config, **options: calls.append(options))

    result = CliRunner().invoke(env.app, ['create', 'billing', '--grant-profiles', 'billing'])

    assert result.exit_code == 2
    assert '--dsn' in result.output
    assert not calls


def test_missing_profile_roles_are_named(monkeypatch):
    def create(entry, config, **options):
        raise ProfileRolesNotFoundError(['billing_node', 'billing_viewer'])

    monkeypatch.setattr(env, 'create_environment', create)

    result = CliRunner().invoke(env.app, ['create', 'billing', '--dsn', 'postgresql://rt@db/rt',
                                          '--grant-profiles', 'billing'])

    assert result.exit_code == 1
    assert 'billing_node, billing_viewer' in result.output
