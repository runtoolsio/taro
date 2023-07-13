from tarotools.taro.jobs import persistence
from tarotools.taro.util import MatchingStrategy
from tarotools.cli import argsutil, printer
from tarotools.cli.view import stats


def run(args):
    instance_match = argsutil.instance_matching_criteria(args, MatchingStrategy.PARTIAL)
    job_stats_list = persistence.read_stats(instance_match)
    printer.print_table(job_stats_list, stats.DEFAULT_COLUMNS, show_header=True, pager=True)
