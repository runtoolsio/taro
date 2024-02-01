from runtools import runcore
from runtools.runcore.util import MatchingStrategy

from runtools.taro import cliutil, argsutil


def run(args):
    run_match = argsutil.run_criteria(args, MatchingStrategy.FN_MATCH)
    with runcore.persistence() as db:
        count = db.count_instances(run_match)
        print(str(count) + " records to delete found")

        if not (count and cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True)):
            print('Skipped..')
            return

        db.remove_job_runs(run_match)
        print('Done..')
