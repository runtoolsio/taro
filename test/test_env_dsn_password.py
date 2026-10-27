"""DSN passwords never show on screen, and storing one in the registry is warned about."""
import pytest
from typer.testing import CliRunner

from runtools.taro.cmd import env


@pytest.mark.parametrize('dsn, shown', [
    ('postgresql://runtools:s3cret@db/rt', 'postgresql://runtools:***@db/rt'),
    ('host=db user=rt password=s3cret dbname=rt', 'host=db user=rt password=*** dbname=rt'),
    ("host=db password='a b' dbname=rt", 'host=db password=*** dbname=rt'),
    ('postgresql://u@db/rt?password=s3cret&sslmode=verify-full',
     'postgresql://u@db/rt?password=***&sslmode=verify-full'),
])
def test_password_is_masked(dsn, shown):
    assert env._redact(dsn) == shown


@pytest.mark.parametrize('location', [
    'postgresql://runtools@db/rt',
    'postgresql://alice@db/rt?options=-c%20role%3Druntools_ops',
    '/home/u/data/env.db',
])
def test_location_without_password_is_unchanged(location):
    assert env._redact(location) == location


@pytest.fixture
def created(monkeypatch):
    monkeypatch.setattr(env, 'create_environment', lambda entry, config: None)


def test_create_warns_when_the_dsn_holds_a_password(created):
    result = CliRunner().invoke(env.app, ['create', 'work', '--dsn', 'postgresql://rt:s3cret@db/rt'])

    assert result.exit_code == 0
    assert '~/.pgpass' in result.output


def test_create_does_not_warn_without_a_password(created):
    result = CliRunner().invoke(env.app, ['create', 'work', '--dsn', 'postgresql://rt@db/rt'])

    assert result.exit_code == 0
    assert '~/.pgpass' not in result.output
