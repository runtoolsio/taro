import json

from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from tarotools import taro
from tarotools.cli import printer, argsutil
from tarotools.cli.view import instance as view_inst
from tarotools.taro.job import JobRuns
from tarotools.taro.util import MatchingStrategy


def run(args):
    instance_match = argsutil.instance_matching_criteria(args, MatchingStrategy.PARTIAL)
    job_instances = taro.client.get_active_runs(instance_match).responses
    instances = JobRuns(job_instances)

    if args.format == 'table': 
        columns = view_inst.DEFAULT_COLUMNS
        if args.show_params:
            columns.insert(2, view_inst.PARAMETERS)
        printer.print_table(instances, columns, show_header=True, pager=False)
    elif args.format == 'json':
        print(json.dumps(instances.to_dict()))
    elif args.format == 'jsonp':
        json_str = json.dumps(instances.to_dict(), indent=2)
        print(highlight(json_str, JsonLexer(), TerminalFormatter()))
    else:
        assert False, 'Unknown format: ' + args.format
