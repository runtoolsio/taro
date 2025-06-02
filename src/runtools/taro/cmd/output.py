import itertools

import runtools.runcore
from runtools import runcore
from runtools.runcore.util import MatchingStrategy
from runtools.taro import printer, argsutil
from runtools.taro.theme import Theme
from runtools.taro.view.instance import JOB_ID, INSTANCE_ID, CREATED, ENDED, PHASES


def run(args):
    run_match = argsutil.run_criteria(args, MatchingStrategy.PARTIAL)
    instances, _ = runtools.runcore.get_active_runs(run_match)

    if not instances:
        instances = runcore.read_job_runs(run_match)

    if not instances:
        print('No matching instance found')
        return

    columns = [JOB_ID, INSTANCE_ID, CREATED, ENDED, PHASES]
    instance = sorted(instances, key=lambda r: r.created_at, reverse=True)[0]
    footer_gen = itertools.chain(
        (('', ''), (Theme.warning, 'Error output:')),
        (['', err] for err in instance.error_output)
    )
    printer.print_table([instance], columns, show_header=True, pager=not args.no_pager, footer=footer_gen)
