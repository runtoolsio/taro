from typing import List, Optional

import typer
from rich.console import Console
from runtools.runcore import connector

from runtools.runcore.criteria import JobRunCriteria, LifecycleCriterion
from runtools.runcore.env import get_env_config
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy, parse_duration_to_sec
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def wait(
        instance_patterns: List[str] = typer.Argument(
            metavar="PATTERN",
            help="Instance ID patterns to specify which instances to wait for"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        stage: Stage = typer.Option(
            Stage.ENDED.value,
            "-s", "--stage",
            help="Stage to wait for"
        ),
        timeout: Optional[str] = typer.Option(
            None,
            "-t", "--timeout",
            help="Maximum time to wait before exiting (e.g., '30s', '5m', '1h'). Default: wait forever"
        ),
        history_window: Optional[str] = typer.Option(
            None,
            "--history-window",
            "-H",
            help="Check history for specified duration before waiting (e.g., '10s', '5m', '1h', '1d'). Default: disabled"
        ),
):
    """
    Wait for job instances to reach specific stages.

    This command blocks until the specified number of instances reach the
    target stage, then exits. Useful for scripting and automation.

    Examples:
        # Wait for any instance to complete
        taro wait "*"

        # Wait for an instance with 'backup1' run ID to start running
        taro wait @backup1 --stage RUNNING

        # Wait for instance with job name 'job' and run ID '123' to end with a 60 sec timeout
        taro wait job@123 --timeout 60s

        # Wait with a 10 sec history window (race condition protection)
        taro wait "batch*" -h 10s

        # Check if daily backup ran in the last 24 hours, then wait if not
        taro wait daily-backup -h 1d
    """
    run_match = JobRunCriteria.parse_all(instance_patterns, MatchingStrategy.FN_MATCH)
    run_match += LifecycleCriterion(stage=stage)
    env_config = get_env_config(env)
    with connector.create(env_config) as conn:
        watcher = conn.lifecycle_watcher(run_match)
        watcher.wait(timeout=parse_duration_to_sec(timeout) if timeout else None)