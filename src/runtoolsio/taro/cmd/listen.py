import sys

from runtoolsio.runcore.criteria import compound_instance_filter
from runtoolsio.runcore.job import InstanceTransitionObserver, JobRun
from runtoolsio.runcore.listening import InstanceTransitionReceiver
from runtoolsio.runcore.run import PhaseRun
from runtoolsio.runcore.util import MatchingStrategy, DateTimeFormat
from runtoolsio.taro import argsutil
from runtoolsio.taro import printer, style, cliutil


def run(args):
    instance_match = compound_instance_filter(argsutil.instance_criteria(args, MatchingStrategy.PARTIAL))
    receiver = InstanceTransitionReceiver(instance_match)
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
            styled_texts = style.run_status_line(job_run, ts_prefix_format=self.ts_format)
            printer.print_styled(*styled_texts)
            sys.stdout.flush()
        except BrokenPipeError:
            self._receiver.close_and_wait()
            cliutil.handle_broken_pipe(exit_code=1)
