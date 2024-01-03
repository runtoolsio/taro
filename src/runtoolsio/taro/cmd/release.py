from runtoolsio.runcore import client
from runtoolsio.runcore.client import ApprovalResult
from runtoolsio.runcore.run import TerminationStatus
from runtoolsio.runcore.util import MatchingStrategy

from runtoolsio.taro import argsutil


def run(args):
    instance_match = argsutil.instance_matching_criteria(args, MatchingStrategy.FN_MATCH)
    if args.pending:
        responses, _ = client.release_pending_instances(args.pending, instance_match)
    elif args.queued:
        if not instance_match:
            raise ValueError("Instance must be specified when releasing queued")
        responses, _ = client.release_waiting_instances(TerminationStatus.QUEUED, instance_match)
    else:
        assert False, "Missing release option"

    if responses:
        print('Released:')
        for released_resp in responses:
            if released_resp.release_result == ApprovalResult.APPROVED:
                print(released_resp.instance_metadata.id)
