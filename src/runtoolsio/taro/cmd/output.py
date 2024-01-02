import itertools
from runtoolsio.runcore import client
from runtoolsio.runcore import persistence
from runtoolsio.runcore.job import JobInst
from runtoolsio.runcore.util import MatchingStrategy

from runtoolsio.taro import printer, argsutil
from runtoolsio.taro.theme import Theme
from runtoolsio.taro.view.instance import JOB_ID, INSTANCE_ID, CREATED, ENDED, STATE


def run(args):
    instance_match = argsutil.instance_matching_criteria(args, MatchingStrategy.PARTIAL)
    instances, _ = client.read_job_instances(instance_match)

    if not instances:
        instances = persistence.read_instances(instance_match)

    if not instances:
        print('No matching instance found')
        return

    columns = [JOB_ID, INSTANCE_ID, CREATED, ENDED, STATE]
    instance = sorted(instances, key=JobInst.created_at, reverse=True)[0]
    footer_gen = itertools.chain(
        (('', ''), (Theme.warning, 'Error output:')),
        (['', err] for err in instance.error_output)
    )
    printer.print_table([instance], columns, show_header=True, pager=not args.no_pager, footer=footer_gen)
