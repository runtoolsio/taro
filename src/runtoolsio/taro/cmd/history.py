from runtoolsio.runcore import persistence
from runtoolsio.runcore.persistence import SortCriteria
from runtoolsio.runcore.util import MatchingStrategy

from runtoolsio.taro import printer, argsutil, cliutil
from runtoolsio.taro.view import instance as view_inst


def run(args):
    run_match = argsutil.run_matching_criteria(args, MatchingStrategy.PARTIAL)
    if args.slowest:
        args.last = True
        args.sort = SortCriteria.TIME.name
        args.asc = False

    sort = SortCriteria[args.sort.upper()]
    runs = persistence.read_runs(run_match, sort, asc=args.asc, limit=args.lines, offset=args.offset, last=args.last)

    columns = [view_inst.JOB_ID, view_inst.INSTANCE_ID, view_inst.CREATED, view_inst.ENDED, view_inst.EXEC_TIME,
               view_inst.WARNINGS, view_inst.TERM_STATUS, view_inst.RESULT]
    if args.show_params:
        columns.insert(2, view_inst.PARAMETERS)

    try:
        printer.print_table(runs, columns, show_header=True, pager=not args.no_pager)
    except BrokenPipeError:
        cliutil.handle_broken_pipe(exit_code=1)
