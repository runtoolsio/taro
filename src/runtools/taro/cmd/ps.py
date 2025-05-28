import json
from typing import List, Optional

import typer
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

import runtools.runcore
from runtools.runcore import connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import get_env_config
from runtools.runcore.job import JobRuns
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, argsutil, cli, cliutil
from runtools.taro.view import instance as view_inst

app = typer.Typer(name="ps", invoke_without_command=True)


@app.callback()
def ps(
        instance_patterns: List[str] = typer.Argument(
            default=None,
            metavar="PATTERN",
            help="Instance ID patterns to filter results"
        ),
        env: Optional[str] = cli.ENV_OPTION_FIELD,
):
    """Show active/running job instances"""
    run_match = JobRunCriteria.parse_all(instance_patterns,
                                         MatchingStrategy.PARTIAL) if instance_patterns else JobRunCriteria.all()
    env_config = get_env_config(env)
    with connector.create(env_config) as conn:
        runs = conn.get_active_runs(run_match)
    columns = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.EXEC_TIME, view_inst.WARNINGS,
               view_inst.STATUS]
    try:
        printer.print_table(runs, columns, show_header=True, pager=False)
    except BrokenPipeError:
        cliutil.handle_broken_pipe(exit_code=1)


def run(args):
    run_match = argsutil.run_criteria(args, MatchingStrategy.PARTIAL)
    active_runs = runtools.runcore.get_active_runs(run_match).responses
    runs = JobRuns(active_runs)

    if args.format == 'table':
        columns = view_inst.DEFAULT_COLUMNS
        if args.show_params:
            columns.insert(2, view_inst.PARAMETERS)
        printer.print_table(runs, columns, show_header=True, pager=False)
    elif args.format == 'json':
        print(json.dumps(runs.to_dict()))
    elif args.format == 'jsonp':
        json_str = json.dumps(runs.to_dict(), indent=2)
        print(highlight(json_str, JsonLexer(), TerminalFormatter()))
    else:
        assert False, 'Unknown format: ' + args.format
