import signal
from collections import defaultdict
from threading import Lock, Event
from typing import List, Optional

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.connector import EnvironmentConnector
from runtools.runcore.criteria import JobRunCriteria, MetadataCriterion
from runtools.runcore.env import get_env_config
from runtools.runcore.job import InstanceOutputObserver, InstanceOutputEvent
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli, cliutil

app = typer.Typer(name="tail", invoke_without_command=True)
console = Console()

_connector: Optional[EnvironmentConnector] = None


def _close_connector(_, __):
    if _connector:
        _connector.close()


@app.callback()
def tail(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance filter patterns"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
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
):
    """Print last output from job instances"""
    if instance_patterns:
        metadata_criteria = [MetadataCriterion.parse(p, MatchingStrategy.PARTIAL) for p in instance_patterns]
    else:
        metadata_criteria = [MetadataCriterion.all_match()]

    instance_to_last_line = defaultdict(lambda: 0)
    last_printed_instance = None

    conn = connector.create(get_env_config(env))
    tail_print = TailPrint(conn, metadata_criteria, show_ordinal)
    conn.add_observer_output(tail_print)
    try:
        conn.open()
        for inst in conn.get_instances(JobRunCriteria(metadata_criteria=metadata_criteria)):
            print_instance_header(inst)
            for output_line in inst.output.tail():
                print_line(output_line, show_ordinal)
                instance_to_last_line[inst.metadata] = output_line.ordinal
                last_printed_instance = inst.metadata
    finally:
        if not follow:
            conn.close()
            return

    global _connector
    _connector = conn
    signal.signal(signal.SIGINT, _close_connector)
    signal.signal(signal.SIGTERM, _close_connector)
    tail_print.release(last_printed_instance, instance_to_last_line)


class TailPrint(InstanceOutputObserver):

    def __init__(self, conn, metadata_criteria, show_ordinal):
        self.connector = conn
        self.metadata_criteria = metadata_criteria
        self.show_ordinal = show_ordinal
        self.last_printed_instance = None
        self.print_lock = Lock()
        self.latch = Event()
        self.instance_to_last_line = None

    def release(self, last_printed_instance, instance_to_last_line):
        self.last_printed_instance = last_printed_instance
        self.instance_to_last_line = instance_to_last_line
        self.latch.set()

    def instance_output_update(self, event: InstanceOutputEvent):
        self.latch.wait()
        last_line = self.instance_to_last_line[event.instance]
        if event.output_line.ordinal <= last_line or not any(1 for c in self.metadata_criteria if c(event.instance)):
            return
        try:
            with self.print_lock:
                if self.last_printed_instance != event.instance:
                    print_instance_header(event.instance)
                self.last_printed_instance = event.instance
                print_line(event.output_line, self.show_ordinal)
        except BrokenPipeError:
            self.connector.close()
            cliutil.handle_broken_pipe(exit_code=1)


def print_instance_header(inst):
    console.print(f"\n[bold cyan]{'─' * 20}[/] [bold]{inst.job_id}@{inst.run_id}[/] [bold cyan]{'─' * 20}[/]")


def print_line(output_line, show_ordinal):
    text = f"{output_line.ordinal}: {output_line.message}" if show_ordinal else output_line.message
    if output_line.is_error:
        # TODO stderr?
        console.print(f"[red]{text}[/]", highlight=False)
    else:
        console.print(text, highlight=False)
