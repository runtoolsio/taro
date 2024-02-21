from runtools import runcore
from runtools.runcore.client import ApprovalResult
from runtools.runcore.util import MatchingStrategy

from runtools.taro import argsutil


def run(args):
    run_match = argsutil.run_criteria(args, MatchingStrategy.FN_MATCH)
    responses, _ = runcore.approve_pending_instances(run_match, None)
    approved = [r.instance_metadata for r in responses if r.release_result == ApprovalResult.APPROVED]

    if approved:
        print('Approved:')
        for a in approved:
            print(a)
