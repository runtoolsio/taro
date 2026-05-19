"""Dashboard TUI command — persistent overview of active instances and history."""

from typing import List, Optional

import typer

from runtools.runcore import connector
from runtools.runcore.matching import criteria
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli
from runtools.taro.tui.dashboard import DashboardApp

app = typer.Typer(invoke_without_command=True)


@app.callback()
def dash(
        instance_patterns: List[str] = typer.Argument(default=None, metavar="PATTERN",
                                                      help="Instance ID patterns to filter results"),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        history_limit: int = typer.Option(50, "--history", "-n", help="Maximum number of history rows to display"),
        tags: List[str] = typer.Option(
            None, "--tag", "-t", metavar="TAG",
            help="Filter by tag (label) — exact match, repeatable; ALL must be present. "
                 "Combines with positional patterns as AND."),
):
    """Open a persistent dashboard TUI with active instances and history.

    The dashboard shows two live-updating tables: active instances on top and
    completed runs below. Selecting a row opens the instance detail view;
    dismissing it returns to the dashboard.

    Examples:
        taro dash
        taro dash "backup*" "sync*"
        taro dash --env production
        taro dash -n 100
        taro dash -t prod
    """
    include_tag = not tags
    active_builder = criteria().patterns_or_all(instance_patterns, MatchingStrategy.PARTIAL,
                                                include_tag=include_tag)
    history_builder = (criteria()
                       .patterns_or_all(instance_patterns, MatchingStrategy.PARTIAL,
                                        include_tag=include_tag)
                       .during(Stage.CREATED, today=True))
    if tags:
        active_builder.tags(*tags)
        history_builder.tags(*tags)
    active_match = active_builder.build()
    history_match = history_builder.build()

    resolved = cli.select_env(env)
    with connector.connect(resolved) as conn:
        instances = list(conn.get_instances(active_match))
        history_runs = conn.read_runs(history_match, asc=False, limit=history_limit)
        DashboardApp(conn, instances, history_runs, env_name=conn.env_id, run_match=active_match).run()
