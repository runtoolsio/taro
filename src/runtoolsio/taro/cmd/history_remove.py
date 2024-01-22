from runtoolsio.runcore import persistence
from runtoolsio.runcore.criteria import EntityRunCriteria
from runtoolsio.runcore.util import MatchingStrategy

from runtoolsio.taro import cliutil


def run(args):
    total = 0
    for instance in args.instances:
        run_match = EntityRunCriteria.from_instance_pattern(instance, MatchingStrategy.FN_MATCH)
        count = persistence.count_instances(instance_match=run_match)
        print(str(count) + " records found for " + instance)
        total += count

    if not (total and cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True)):
        print('Skipped..')
        return

    for instance in args.instances:
        run_match = EntityRunCriteria.from_instance_pattern(instance, MatchingStrategy.FN_MATCH)
        persistence.remove_runs(run_match)
