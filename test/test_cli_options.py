"""Option parsing of taro commands: options are accepted after positional patterns."""
import pytest
import typer
from typer.testing import CliRunner

from runtools.taro import cli, main


@pytest.fixture
def selected_env(monkeypatch):
    """Capture the env the command selects, then stop before it connects anywhere."""
    seen = {}

    def select_env(env_id):
        seen['env'] = env_id
        raise typer.Exit()

    monkeypatch.setattr(cli, 'select_env', select_env)
    return seen


@pytest.mark.parametrize('argv', [
    ['stop', 'job@r1', '-f', '-e', 'prod'],
    ['x', 'job@r1', '-e', 'prod', '-f'],
    ['ps', 'job', '-e', 'prod'],
    ['history', 'job', '-e', 'prod'],
])
def test_options_after_patterns_are_parsed(selected_env, argv):
    result = CliRunner().invoke(main.app, argv)

    assert result.exit_code == 0, result.output
    assert selected_env['env'] == 'prod'


def test_group_subcommands_keep_their_own_options(selected_env):
    result = CliRunner().invoke(main.app, ['env', 'clean', '-f', '-e', 'prod'])

    assert result.exit_code == 0, result.output
    assert selected_env['env'] == 'prod'
