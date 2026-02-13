from typing import List

import typer
from rich.console import Console

from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria, PhaseCriterion, LifecycleCriterion
from runtools.runcore.run import Stage
from runtools.runcore.util import MatchingStrategy
from runtools.taro import cli, cliutil, printer
from runtools.taro.view.instance import JOB_ID, RUN_ID, CREATED, PHASES, STATUS

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def resume(
        instance_patterns: List[str] = cli.INSTANCE_PATTERNS,
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID to resume"),
        env: str = cli.ENV_OPTION_FIELD,
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Skip confirmation prompt and resume all matching instances"
        ),
):
    """Resume jobs waiting at checkpoint"""
    total_resumed = 0

    with connector.connect(env) as conn:
        for pattern in instance_patterns:
            run_match = JobRunCriteria.parse(pattern, MatchingStrategy.FN_MATCH)
            run_match += PhaseCriterion(phase_id=phase, lifecycle=LifecycleCriterion(stage=Stage.CREATED))
            run_match += PhaseCriterion(phase_id=phase, idle=True)
            instances = conn.get_instances(run_match)

            if not instances:
                console.print(f"\n[yellow]⚠[/] No instances found for pattern: [white]{pattern}[/]")
                continue

            resumable = []
            for inst in instances:
                if inst.find_phase_control_by_id(phase):
                    resumable.append(inst)

            if not resumable:
                console.print(
                    f"\n[dim]Pattern [/][white]{pattern}[/][dim] matches {len(instances)} instance(s), but none have phase '{phase}'[/]")
                continue

            console.print(f"\n[dim]Pattern [/][white]{pattern}[/][dim] matches ({len(resumable)} resumable):[/]")

            if not force:
                printer.print_table(
                    [i.to_run() for i in resumable],
                    [JOB_ID, RUN_ID, CREATED, PHASES, STATUS],
                    show_header=True, pager=False
                )

                if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True, newline_before=True):
                    console.print("[dim]Skipped[/]")
                    continue

            for inst in resumable:
                inst.find_phase_control_by_id(phase).resume()
                console.print(f"  [green]✓[/] Resumed {inst.id}")
                total_resumed += 1

        style = "bold" if total_resumed else "yellow"
        console.print(f"\n[{style}]Total resumed: {total_resumed}[/]")
