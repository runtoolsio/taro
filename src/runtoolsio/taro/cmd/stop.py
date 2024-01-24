from runtoolsio.runcore.client import APIClient
from runtoolsio.runcore.util import MatchingStrategy

from runtoolsio.taro import printer, style, argsutil, cliutil
from runtoolsio.taro.printer import print_styled
from runtoolsio.taro.view.instance import JOB_ID, INSTANCE_ID, CREATED, STATE, RUN_ID


def run(args):
    with APIClient() as client:
        run_match = argsutil.run_criteria(args, MatchingStrategy.FN_MATCH)
        instances_to_stop, _ = client.get_active_runs(run_match)

        if not instances_to_stop:
            print('No instances to stop: ' + " ".join(args.instances))
            return

        if not args.force:
            print('Instances to stop:')
            printer.print_table(instances_to_stop, [JOB_ID, RUN_ID, INSTANCE_ID, CREATED, STATE], show_header=True, pager=False)
            if not cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True):
                return

        for stop_resp in client.stop_instances(run_match).responses:
            print_styled(*style.entity_run_id(stop_resp.instance_metadata) + [('', ' -> '), ('', stop_resp.stop_result.name)])
