from runtools import runcore
from runtools.runcore.util import MatchingStrategy

from runtools.taro import argsutil, printer
from runtools.taro.view import stats


def run(args):
    run_match = argsutil.run_criteria(args, MatchingStrategy.PARTIAL)
    with runcore.persistence() as db:
        job_stats_list = db.read_job_stats(run_match)

    printer.print_table(job_stats_list, stats.DEFAULT_COLUMNS, show_header=True, pager=True)
