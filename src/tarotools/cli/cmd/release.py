from tarotools.cli import argsutil

from tarotools import taro
from tarotools.taro import TerminationStatus
from tarotools.taro.client import ApprovalResult
from tarotools.taro.util import MatchingStrategy


def run(args):
    instance_match = argsutil.instance_matching_criteria(args, MatchingStrategy.FN_MATCH)
    if args.pending:
        responses, _ = taro.client.release_pending_instances(args.pending, instance_match)
    elif args.queued:
        if not instance_match:
            raise ValueError("Instance must be specified when releasing queued")
        responses, _ = taro.client.release_waiting_instances(TerminationStatus.QUEUED, instance_match)
    else:
        assert False, "Missing release option"

    if responses:
        print('Released:')
        for released_resp in responses:
            if released_resp.release_result == ApprovalResult.APPROVED:
                print(released_resp.instance_metadata.id)
