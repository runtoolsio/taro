from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.matching import criteria
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy, parse_duration_to_sec, format_dt_local_tz
from runtools.taro import cli

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def wait(
        instance_patterns: Optional[List[str]] = typer.Argument(
            default=None,
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

    This command blocks until each pattern is matched by a distinct run that
    reached the target stage, then exits. Useful for scripting and automation.

    By default, the command first checks history for matching instances that already
    reached the target stage. Use --future-only to wait only for future events.

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
    patterns = instance_patterns or ["*"]
    criteria_list = []
    for pattern in patterns:
        criteria_list.append(criteria().pattern(pattern, MatchingStrategy.FN_MATCH).reached_stage(stage).build())

    timeout_sec = parse_duration_to_sec(timeout) if timeout else None
    with connector.connect(env) as conn:
        watcher = conn.watcher(*criteria_list, search_past=not future_only)
        try:
            watcher.wait(timeout=timeout_sec)
        except KeyboardInterrupt:
            watcher.cancel()
            raise

    for entry in watcher.watched_runs:
        if entry.matched_run:
            stage_color = "blue" if stage == Stage.ENDED else "green"
            formatted_ts = format_dt_local_tz(entry.matched_run.lifecycle.transition_at(stage), include_ms=False)
            console.print(
                f"[green]✓[/] [bold]{entry.matched_run.instance_id}[/]"
                f" reached [{stage_color}]{stage.value}[/] stage at {formatted_ts}")
        elif watcher.is_timed_out:
            console.print(f"[yellow]⏱️  Timeout[/] for [bold]{entry.criteria}[/] after {timeout_sec} seconds")

    if watcher.is_timed_out:
        raise typer.Exit(code=124)
