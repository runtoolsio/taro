import os
import re
import subprocess
import tempfile
import tomllib
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Tuple

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.padding import Padding

from runtools.runcore import connector
from runtools.runcore.transport.unix_socket import resolve_env_dir, clean_stale_component_dirs
from runtools.runcore.env import (
    EnvironmentEntry, EnvironmentKind, LocalEnvironmentConfig, PostgresEnvironmentConfig,
    available_environments, load_env_config, save_env_config, lookup, open_env_db,
    create_environment, add_environment, delete_environment,
    EnvironmentNotFoundError, EnvironmentAlreadyExistsError,
)
from runtools.runcore.db import Signal, TAIL_LINGER_AFTER_END
from runtools.runcore.job import HEARTBEAT_STALE_AFTER, InstanceID
from runtools.runcore.matching import criteria
from runtools.runcore.util import MatchingStrategy, utc_now
from runtools.runcore.util.files import format_toml, read_toml_file
from runtools.taro import cli, cliutil, printer
from runtools.taro.view import instance as view_inst

app = typer.Typer(name="env", invoke_without_command=True, no_args_is_help=True)
console = Console()


_PATH_OPTION = typer.Option(None, "--path", "-p", help="local: database file (default path when omitted)")
_DSN_OPTION = typer.Option(None, "--dsn", help="postgres: libpq connection string — keep the password in ~/.pgpass")


_URI_PASSWORD = re.compile(r"(://[^:/@\s]+:)[^@\s]*@")                 # postgresql://user:secret@host
_KEYWORD_PASSWORD = re.compile(r"(\bpassword\s*=\s*)('[^']*'|[^\s&]+)")  # password=secret, ?password=secret


def _redact(location: str) -> str:
    """The location with any DSN password masked — for display, and to detect one."""
    return _KEYWORD_PASSWORD.sub(r"\1***", _URI_PASSWORD.sub(r"\1***@", location))


def _warn_if_password(dsn: Optional[str]):
    if dsn and _redact(dsn) != dsn:
        console.print("[yellow]Warning:[/] the DSN contains a password, stored as plain text in the environment "
                      "registry — prefer leaving it out and putting it in ~/.pgpass")


def _entry(name: str, path: Optional[str], dsn: Optional[str]) -> EnvironmentEntry:
    """The kind follows the location option: ``--dsn`` is a postgres environment, otherwise local (sqlite)."""
    if path and dsn:
        console.print("[red]Error:[/] use either --path (local) or --dsn (postgres), not both")
        raise typer.Exit(2)
    if dsn:
        return EnvironmentEntry(id=name, kind=EnvironmentKind.POSTGRES, location=dsn)
    return EnvironmentEntry(id=name, kind=EnvironmentKind.LOCAL, location=path)


@app.command()
def create(
        name: str = typer.Argument(..., help="Environment name"),
        path: Optional[str] = _PATH_OPTION,
        dsn: Optional[str] = _DSN_OPTION,
):
    """Create a new environment: a local SQLite database, or a schema in PostgreSQL with --dsn.

    Examples:
        taro env create dev
        taro env create staging --path ~/data/staging.db
        taro env create work --dsn postgresql://runtools@db/runtools

    An environment that already exists in PostgreSQL (created from another machine) is joined with `add`.
    """
    entry = _entry(name, path, dsn)
    _warn_if_password(dsn)
    try:
        config = PostgresEnvironmentConfig() if dsn else LocalEnvironmentConfig()
        create_environment(entry, config)
    except EnvironmentAlreadyExistsError:
        console.print(f"[red]Environment '{name}' already exists[/] — to use one created elsewhere, run "
                      f"`taro env add {name}` with the same location")
        raise typer.Exit(1)
    console.print(f"[green]Created {entry.kind.value} environment '[bold]{name}[/bold]'[/]")


@app.command()
def add(
        name: str = typer.Argument(..., help="Environment name — the same as where it was created"),
        path: Optional[str] = _PATH_OPTION,
        dsn: Optional[str] = _DSN_OPTION,
):
    """Register an existing environment on this machine, e.g. a postgres one created from another machine.

    Its stored config is left untouched.

    Examples:
        taro env add work --dsn postgresql://runtools@db/runtools
    """
    entry = _entry(name, path, dsn)
    _warn_if_password(dsn)
    try:
        add_environment(entry)
    except EnvironmentAlreadyExistsError:
        console.print(f"[red]Environment '{name}' is already registered[/]")
        raise typer.Exit(1)
    except EnvironmentNotFoundError:
        console.print(f"[red]No environment '{name}' at that location[/] — create it with `taro env create`")
        raise typer.Exit(1)
    console.print(f"[green]Added {entry.kind.value} environment '[bold]{name}[/bold]'[/]")


@app.command("list")
def list_envs():
    """List available environments."""
    envs = available_environments()
    if not envs:
        console.print("No environments available. Run [bold]taro env create <name>[/] to create one.")
        return
    for entry in envs:
        label = "[dim](built-in)[/]" if entry.is_builtin_local else f"[dim]{entry.kind}[/]"
        path_info = _redact(entry.location) if entry.location else "(default)"
        console.print(f"  [bold]{entry.id}[/]  {label}  {path_info}")


@app.command()
def delete(
        name: str = typer.Argument(..., help="Environment name to delete"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Delete environment (DB file + registry entry)."""
    try:
        lookup(name)  # validate it exists (and is not built-in local)
    except EnvironmentNotFoundError:
        console.print(f"[red]Environment '{name}' not found[/]")
        raise typer.Exit(1)

    if not force:
        confirm = input(f"Delete environment '{name}' and its data? [y/N] ").strip().lower()
        if confirm != 'y':
            console.print("Cancelled")
            raise typer.Exit()

    delete_environment(name)
    console.print(f"[green]Deleted environment '[bold]{name}[/bold]'[/]")


@app.command()
def show(
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Show DB-stored configuration for an environment."""
    entry = cli.select_env(env_id)
    env_config = load_env_config(entry)
    console.print(Padding(f"[dim]Environment:[/] [ {entry.id} ]", pad=(0, 0, 0, 0)))
    print(format_toml(env_config.model_dump(mode='json')))


@app.command()
def edit(
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Edit DB-stored configuration in $EDITOR."""
    entry = cli.select_env(env_id)
    env_config = load_env_config(entry)

    dump = env_config.model_dump(mode='json')
    original_content = (
        "# Environment configuration (TOML format)\n"
        "# Lines starting with # are comments and ignored.\n"
        "#\n"
        "# Example plugin config:\n"
        "# [[plugins.sns.rules]]\n"
        '# stage = ["running", "ended"]    # created, running, ended (default: ended)\n'
        '# outcome = "fault"               # outcome group: success, fault, aborted, rejected\n'
        '# term_status = "failed"          # specific status: failed, completed, stopped, etc.\n'
        '# topic_arn = "arn:aws:sns:eu-west-1:123:alerts"\n'
        '# format = "slack"                # json (default) or slack\n'
        "\n"
        + format_toml(dump) + "\n"
    )

    editor = os.environ.get('EDITOR', 'vi')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(original_content)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            console.print("[red]Editor exited with error[/]")
            raise typer.Exit(1)

        edited = read_toml_file(tmp_path)
        original_normalized = tomllib.loads(format_toml(dump))
        if edited == original_normalized:
            console.print("[dim]No changes made[/dim]")
            os.unlink(tmp_path)
            return
        new_config = type(env_config).model_validate(edited)
        save_env_config(entry, new_config)
        console.print(f"[green]Configuration saved for '{entry.id}'[/]")
    except typer.Exit:
        raise
    except (tomllib.TOMLDecodeError, ValidationError) as e:
        console.print(f"[red]Invalid configuration:[/] {e}")
        console.print(f"[dim]Temp file kept at: {tmp_path}[/dim]")
        raise typer.Exit(1)
    else:
        os.unlink(tmp_path)


@app.command()
def clean(
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Remove state left behind by dead processes.

    Stale component directories (local environments) and the signal and output-tail rows of runs that
    have ended or no longer exist. Lost runs are not ended — resolve them with `mark-lost` first.
    Run history is never touched.
    """
    entry = cli.select_env(env_id)
    if entry.kind is EnvironmentKind.LOCAL:
        _clean_component_dirs(entry)
    _clean_orphan_rows(entry, force)


def _clean_component_dirs(entry: EnvironmentEntry):
    env_config = load_env_config(entry)
    env_dir = resolve_env_dir(entry.id, env_config.root_dir)
    removed = clean_stale_component_dirs(env_dir)
    if removed:
        console.print(f"Cleaned {len(removed)} stale component directories:")
        for d in removed:
            console.print(f"  {d}")
    else:
        console.print(f"No stale component directories found in {env_dir}")


def _clean_orphan_rows(entry: EnvironmentEntry, force: bool):
    with open_env_db(entry) as db:
        signals, tails = _orphan_rows(db)
        if not signals and not tails:
            console.print("No orphan signal or output-tail rows found")
            return

        console.print(f"Orphan rows of ended or missing runs in [bold]{entry.id}[/]: "
                      f"[bold]{len(signals)}[/] signals, [bold]{len(tails)}[/] output tails")
        if not force and not cliutil.user_confirmation(catch_interrupt=True):
            raise typer.Exit()

        # Delete the previewed rows as is: ended stays ended and a deleted run stays deleted — except an ID
        # re-run under a reused ordinal while the prompt waits, an accepted limitation (ops are re-sendable)
        db.delete_signals([s.signal_id for s in signals])
        db.delete_output_tails(tails)
        console.print(f"[green]Removed {len(signals)} signals and {len(tails)} output tails[/]")


def _orphan_rows(db) -> Tuple[List[Signal], List[InstanceID]]:
    """Signal and output-tail rows whose run has ended or no longer exists.

    Lifecycle, not liveness: a lost run is still non-ended, so its rows stay until `mark-lost` resolves
    it. An ended run's tail lingers briefly (`TAIL_LINGER_AFTER_END`) so a follower's last poll sees it.
    """
    signals = db.read_signals()
    tails = db.output_tail_instances()
    ends = db.read_run_ends({s.instance_id for s in signals} | set(tails))
    linger_cutoff = utc_now() - timedelta(seconds=TAIL_LINGER_AFTER_END)

    def gone(instance_id, ended_before=None):
        if instance_id not in ends:
            return True  # The run row is gone
        ended = ends[instance_id]
        return ended is not None and (ended_before is None or ended < ended_before)

    return [s for s in signals if gone(s.instance_id)], [i for i in tails if gone(i, ended_before=linger_cutoff)]


@app.command()
def prune(
        pattern: str = typer.Argument("*", metavar="PATTERN",
                                      help="Job pattern to prune ('*' for all)"),
        keep_days: Optional[int] = typer.Option(None, "--keep-days", "-k",
                                      help="Keep runs newer than N days (0 = remove all matched). "
                                           "Defaults to the environment's configured retention."),
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Remove old run history and output files.

    With no --keep-days, applies the environment's configured retention
    (``retention.keep_days``); a flag overrides it. The preview + confirmation
    guard against accidental loss (skip with --force).

    Examples:
        taro env prune                                # apply the env's configured retention
        taro env prune "*" --keep-days 0              # wipe all history
        taro env prune "*" --keep-days 7              # keep last week
        taro env prune "test_*" --keep-days 0         # wipe all test runs
        taro env prune "backup" --keep-days 30 -e dev # prune old backup runs
    """
    resolved = cli.select_env(env_id)
    if keep_days is None:
        keep_days = load_env_config(resolved).retention.keep_days
    if keep_days is None:
        console.print("[red]Error:[/] no retention configured for this environment; pass --keep-days")
        raise typer.Exit(2)
    if keep_days < 0:
        console.print("[red]Error:[/] --keep-days must be >= 0")
        raise typer.Exit(2)

    if keep_days == 0:
        match = criteria().pattern(pattern, MatchingStrategy.FN_MATCH).build()
        desc = f"runs matching '{pattern}'"
    else:
        cutoff = datetime.now(UTC) - timedelta(days=keep_days)
        match = (criteria()
                 .pattern(pattern, MatchingStrategy.FN_MATCH)
                 .ended(until=cutoff)
                 .build())
        desc = f"runs matching '{pattern}' older than {keep_days} days"

    with connector.connect(resolved) as conn:
        # Preview: count matching runs
        preview = conn.read_runs(match, asc=False)
        if not preview:
            console.print("[dim]No matching runs to remove[/]")
            return

        n_preview = len(preview)
        console.print(f"Currently matching: [bold]{n_preview}[/] {desc} in [bold]{resolved.id}[/]")

        if not force:
            confirm = input("Proceed? [y/N] ").strip().lower()
            if confirm != 'y':
                console.print("Cancelled")
                raise typer.Exit()

        removed = conn.remove_history_runs(match)
        n = len(removed)
        console.print(f"[green]Removed {n} {'run' if n == 1 else 'runs'} and output files[/]")


@app.command("mark-lost")
def mark_lost(
        instance_patterns: Optional[List[str]] = typer.Argument(
            default=None, metavar="PATTERN", help="Instance ID patterns (all lost runs when omitted)"),
        env_id: Optional[str] = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Resolve lost runs — their owner stopped heartbeating — as LOST.

    A deliberate operator act: lost runs are never resolved automatically, since a silent owner may
    still recover and finish truthfully. A run whose owner attests again before the mark is kept.

    Examples:
        taro env mark-lost                  # all lost runs
        taro env mark-lost "backup@*" -e prod
    """
    resolved = cli.select_env(env_id)
    run_match = criteria().patterns_or_all(instance_patterns, MatchingStrategy.FN_MATCH).build()
    with open_env_db(resolved) as db:  # Storage, not the live view: a dead node's runs are listed on every kind
        lost = [run for run in db.read_active_runs(run_match) if run.is_lost()]
        if not lost:
            console.print("[dim]No lost runs found[/]")
            raise typer.Exit()

        if not force:
            printer.print_table(
                lost,
                [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.EXEC_TIME, view_inst.PHASES,
                 view_inst.STATUS],
                show_header=True, pager=False,
            )
            if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                raise typer.Exit()

        marked = set(db.mark_lost_runs([run.instance_id for run in lost], HEARTBEAT_STALE_AFTER))
        for run in lost:
            if run.instance_id in marked:
                console.print(f"  [green]✓[/] Marked lost {run.instance_id}")
            else:
                console.print(f"  [yellow]⚠[/] {run.instance_id} no longer lost "
                              f"(owner attested or run already ended)")

        console.print(f"\n[{'bold' if marked else 'yellow'}]Total marked lost: {len(marked)}[/]")
