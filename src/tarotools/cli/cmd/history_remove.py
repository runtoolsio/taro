from tarotools.cli import cliutil
from tarotools.taro.jobs import persistence
from tarotools.taro.jobs.inst import InstanceMatchCriteria
from tarotools.taro.util import MatchingStrategy


def run(args):
    total = 0
    for instance in args.instances:
        instance_match = InstanceMatchCriteria.parse_pattern(instance, MatchingStrategy.FN_MATCH)
        count = persistence.count_instances(instance_match=instance_match)
        print(str(count) + " records found for " + instance)
        total += count

    if not (total and cliutil.user_confirmation(yes_on_empty=True, catch_interrupt=True)):
        print('Skipped..')
        return

    for instance in args.instances:
        instance_match = InstanceMatchCriteria.parse_pattern(instance, MatchingStrategy.FN_MATCH)
        persistence.remove_instances(instance_match)
