from concurrent.futures.thread import ThreadPoolExecutor
from datetime import timedelta
from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, LifecycleCriterion
from runtools.runcore.env import get_env_config
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy, parse_duration_to_sec, utc_now, DateTimeRange
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
        future_only: bool = typer.Option(
            False,
            "-f", "--future-only",
            help="Skip history search, wait for live events only"
        ),
):
    """
    Wait for job instances to reach specific stages.

    This command blocks until the specified number of instances reach the
    target stage, then exits. Useful for scripting and automation.

    By default, the command first checks history for matching instances that already
    reached the target stage. Use --no-history to wait only for future events.

    Examples:
        # Wait only for future completions of any run, ignore past matches
        taro wait --future-only "*"

        # Wait for backup job to reach RUNNING stage (checks past and current state too)
        taro wait --stage RUNNING @backup1

        # Wait for specific instance to end with 60 second timeout (checks past and current state)
        taro wait --timeout 60s job@123

        # Wait only for new batch job to start, ignore any that already started
        taro wait --stage RUNNING --future-only "batch*"
    """
    executor = ThreadPoolExecutor(max_workers=len(instance_patterns))
    env_config = get_env_config(env)
    watchers = []
    with connector.create(env_config) as conn:
        for pattern in instance_patterns:
            run_match = JobRunCriteria.parse(pattern, MatchingStrategy.FN_MATCH)
            run_match += LifecycleCriterion(stage=stage)
            watcher = conn.watcher(run_match, search_past=not future_only)
            watchers.append(watcher)
            executor.submit(watch_for_run, watcher, parse_duration_to_sec(timeout) if timeout else None)
        try:
            executor.shutdown()
        except KeyboardInterrupt as e:
            for w in watchers:
                w.cancel()
            executor.shutdown()
            raise e

    for watcher in watchers:
        if watcher.is_timed_out:
            raise typer.Exit(code=124)


def watch_for_run(watcher, timeout_sec):
    watcher.wait(timeout=timeout_sec)
    if watcher.matched_runs:
        console.print(
            f"\n[green]✓[/] [bold]{watcher.matched_runs[0].instance_id}[/] reached awaited stage")
    elif watcher.is_timed_out:
        console.print(f"\n[yellow]⏱️  Timeout[/] for [bold]{watcher.run_match}[/] after {timeout_sec} seconds")

