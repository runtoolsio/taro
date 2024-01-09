import sys

from runtoolsio.runcore.job import InstanceTransitionObserver, JobRun
from runtoolsio.runcore.listening import InstanceTransitionReceiver
from runtoolsio.runcore.run import PhaseRun
from runtoolsio.runcore.util import MatchingStrategy, DateTimeFormat

from runtoolsio.taro import argsutil
from runtoolsio.taro import printer, style, cliutil


def run(args):
    receiver = InstanceTransitionReceiver(argsutil.id_match(args, MatchingStrategy.PARTIAL))
    receiver.add_observer_transition(EventPrint(receiver, args.timestamp.value))
    receiver.start()
    cliutil.exit_on_signal(cleanups=[receiver.close_and_wait])
    receiver.wait()  # Prevents 'exception ignored in: <module 'threading' from ...>` error message


class EventPrint(InstanceTransitionObserver):

    def __init__(self, receiver, ts_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE):
        self._receiver = receiver
        self.ts_format = ts_format

    def new_instance_phase(self, job_run: JobRun, previous_phase: PhaseRun, new_phase: PhaseRun, ordinal: int):
        try:
            printer.print_styled(*style.job_instance_id_status_line_styled(
                job_run.metadata.entity_id, new_phase, new_phase.started_at, ts_prefix_format=self.ts_format))
            sys.stdout.flush()
        except BrokenPipeError:
            self._receiver.close_and_wait()
            cliutil.handle_broken_pipe(exit_code=1)
