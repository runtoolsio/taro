from runtools import runcore
from runtools.runcore.db import SortCriteria
from runtools.runcore.util import MatchingStrategy

from runtools.taro import printer, argsutil, cliutil
from runtools.taro.view import instance as view_inst


def run(args):
    run_match = argsutil.run_criteria(args, MatchingStrategy.PARTIAL)
    if args.slowest:
        args.last = True
        args.sort = SortCriteria.TIME.name
        args.asc = False

    sort = SortCriteria[args.sort.upper()]
    with runcore.persistence() as db:
        runs = db.read_job_runs(run_match, sort, asc=args.asc, limit=args.lines, offset=args.offset, last=args.last)

    columns = [view_inst.JOB_ID, view_inst.RUN_ID, view_inst.CREATED, view_inst.ENDED, view_inst.EXEC_TIME,
               view_inst.TERM_STATUS, view_inst.RESULT, view_inst.WARNINGS]
    if args.show_params:
        columns.insert(2, view_inst.PARAMETERS)

    try:
        printer.print_table(runs, columns, show_header=True, pager=not args.no_pager)
    except BrokenPipeError:
        cliutil.handle_broken_pipe(exit_code=1)
