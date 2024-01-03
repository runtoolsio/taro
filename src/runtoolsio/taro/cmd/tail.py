import sys
from runtoolsio.runcore import client
from runtoolsio.runcore.criteria import compound_id_filter, JobRunAggregatedCriteria
from runtoolsio.runcore.job import JobInstanceMetadata
from runtoolsio.runcore.listening import InstanceOutputReceiver, InstanceOutputObserver
from runtoolsio.runcore.run import PhaseMetadata
from runtoolsio.runcore.util import MatchingStrategy

from runtoolsio.taro import argsutil
from runtoolsio.taro import printer, style, cliutil
from runtoolsio.taro.theme import Theme

HIGHLIGHT_TOKEN = (Theme.separator, ' ---> ')


def run(args):
    id_criteria = argsutil.id_matching_criteria(args, MatchingStrategy.PARTIAL)
    if args.follow:
        receiver = InstanceOutputReceiver(compound_id_filter(id_criteria))
        receiver.add_observer_output(TailPrint(receiver))
        receiver.start()
        cliutil.exit_on_signal(cleanups=[receiver.close_and_wait])
        receiver.wait()  # Prevents 'exception ignored in: <module 'threading' from ...>` error message
    else:
        for tail_resp in client.fetch_output(JobRunAggregatedCriteria(id_criteria)).responses:
            printer.print_styled(HIGHLIGHT_TOKEN, *style.job_instance_id_styled(tail_resp.instance_metadata.id))
            for line, is_error in tail_resp.tail:
                print(line, file=sys.stderr if is_error else sys.stdout)
            sys.stdout.flush()


class TailPrint(InstanceOutputObserver):

    def __init__(self, receiver):
        self._receiver = receiver
        self.last_printed_job_instance = None

    def new_instance_output(self, instance_meta: JobInstanceMetadata, phase: PhaseMetadata, output: str, is_err: bool):
        # TODO It seems that this needs locking
        try:
            if self.last_printed_job_instance != instance_meta.id:
                printer.print_styled(HIGHLIGHT_TOKEN, *style.job_instance_id_styled(instance_meta.id))
            self.last_printed_job_instance = instance_meta.id
            print(output, flush=True, file=sys.stderr if is_err else sys.stdout)
        except BrokenPipeError:
            self._receiver.close_and_wait()
            cliutil.handle_broken_pipe(exit_code=1)
