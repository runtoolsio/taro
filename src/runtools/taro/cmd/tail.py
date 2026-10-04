import signal
from collections import defaultdict
from threading import Event, Lock
from typing import List, Optional

import typer
from rich.console import Console
from rich.text import Text

from runtools.runcore import connector
from runtools.runcore.job import InstanceOutputObserver, InstanceOutputEvent
from runtools.runcore.matching import JobRunCriteria, MetadataCriterion
from runtools.runcore.output import OutputLine
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli, cliutil
from runtools.taro.view.output_render import format_line_verbose, format_line_plain

app = typer.Typer(name="tail", invoke_without_command=True)
console = Console()

@app.callback()
def tail(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance filter patterns"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
        lines: int = typer.Option(
            100,
            "-n", "--lines",
            help="Number of output lines to show (0 for all)"
        ),
        follow: bool = typer.Option(
            False,
            "-f", "--follow",
            help="Keep printing"
        ),
        show_ordinal: bool = typer.Option(
            False,
            "-o", "--ordinal",
            help="Show line numbers (ordinals) for each output line"
        ),
        verbose: bool = typer.Option(
            False,
            "-v", "--verbose",
            help="Show timestamp, level, logger, and DEBUG lines"
        ),
):
    """Print last output from job instances"""
    if instance_patterns:
        metadata_criteria = tuple(MetadataCriterion.parse(p, MatchingStrategy.PARTIAL) for p in instance_patterns)
    else:
        metadata_criteria = (MetadataCriterion.all_match(),)

    instance_to_last_line = defaultdict(lambda: 0)
    last_printed_instance = None

    resolved = cli.select_env(env)
    conn = connector.connect(resolved)
    tail_print = TailPrint(conn, metadata_criteria, show_ordinal, verbose)
    previous_handlers = {}

    def stop_follow(_, __):
        tail_print.stopped.set()

    try:
        if follow:
            conn.notifications.add_observer_output(tail_print)
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.signal(signum, stop_follow)
        conn.open()
        for inst in conn.get_instances(JobRunCriteria(metadata_criteria=metadata_criteria)):
            print_instance_header(inst)
            for output_line in inst.output.tail(max_lines=lines):
                instance_to_last_line[inst.metadata] = output_line.ordinal
                if _should_show(output_line, verbose):
                    print_line(output_line, show_ordinal, verbose)
                    last_printed_instance = inst.metadata
        if follow:
            tail_print.release(last_printed_instance, instance_to_last_line)
            tail_print.stopped.wait()
    finally:
        try:
            conn.close()
        finally:
            for signum, previous in previous_handlers.items():
                signal.signal(signum, previous)

    if tail_print.broken_pipe:
        cliutil.handle_broken_pipe(exit_code=1)


class TailPrint(InstanceOutputObserver):

    def __init__(self, conn, metadata_criteria, show_ordinal, verbose):
        self.connector = conn
        self.metadata_criteria = metadata_criteria
        self.show_ordinal = show_ordinal
        self.verbose = verbose
        self.last_printed_instance = None
        self.print_lock = Lock()
        self.stopped = Event()
        self.broken_pipe = False
        self._pending: list[InstanceOutputEvent] = []
        self.instance_to_last_line = None

    def release(self, last_printed_instance, instance_to_last_line):
        try:
            with self.print_lock:
                self.last_printed_instance = last_printed_instance
                self.instance_to_last_line = instance_to_last_line
                pending, self._pending = self._pending, []
                for event in pending:
                    self._print_event(event)
        except BrokenPipeError:
            self.broken_pipe = True
            self.stopped.set()

    def instance_output_update(self, event: InstanceOutputEvent):
        if self.stopped.is_set() or not any(c(event.instance) for c in self.metadata_criteria):
            return
        try:
            with self.print_lock:
                if self.instance_to_last_line is None:
                    self._pending.append(event)
                else:
                    self._print_event(event)
        except BrokenPipeError:
            self.broken_pipe = True
            self.stopped.set()

    def _print_event(self, event: InstanceOutputEvent) -> None:
        """Print under the caller's lock, deduplicating initial replay and live delivery."""
        if event.output_line.ordinal <= self.instance_to_last_line[event.instance]:
            return
        self.instance_to_last_line[event.instance] = event.output_line.ordinal
        if not _should_show(event.output_line, self.verbose):
            return
        if self.last_printed_instance != event.instance:
            print_instance_header(event.instance)
        self.last_printed_instance = event.instance
        print_line(event.output_line, self.show_ordinal, self.verbose)


def _should_show(line: OutputLine, verbose: bool) -> bool:
    if line.is_tracking_only:
        return False
    if not verbose and line.level == 'DEBUG':
        return False
    return True


def print_instance_header(inst):
    console.print(f"\n[bold cyan]{'─' * 20}[/] [bold]{inst.job_id}@{inst.run_id}[/] [bold cyan]{'─' * 20}[/]")


def print_line(output_line, show_ordinal, verbose):
    formatted = format_line_verbose(output_line) if verbose else format_line_plain(output_line)
    if show_ordinal:
        text = Text(f"{output_line.ordinal}: ")
        text.append_text(formatted)
        formatted = text
    console.print(formatted, highlight=False)
