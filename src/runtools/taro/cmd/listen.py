import sys

from runtools import runcore
from runtools.runcore.criteria import compound_instance_filter
from runtools.runcore.job import InstanceTransitionObserver, JobRun
from runtools.runcore.run import PhaseRun
from runtools.runcore.util import MatchingStrategy, DateTimeFormat
from runtools.taro import argsutil
from runtools.taro import printer, style, cliutil


def run(args):
    instance_match = compound_instance_filter(argsutil.instance_criteria(args, MatchingStrategy.PARTIAL))
    receiver = runcore.instance_transition_receiver(instance_match)
    receiver.add_observer_transition(TransitionPrint(receiver, args.timestamp.value))
    receiver.start()
    cliutil.exit_on_signal(cleanups=[receiver.close_and_wait])
    receiver.wait()  # Prevents 'exception ignored in: <module 'threading' from ...>` error message


class TransitionPrint(InstanceTransitionObserver):

    def __init__(self, receiver, ts_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE):
        self._receiver = receiver
        self.ts_format = ts_format

    def new_instance_phase(self, job_run: JobRun, previous_phase: PhaseRun, new_phase: PhaseRun, ordinal: int):
        try:
            styled_status_line = style.run_status_line(job_run, ts_prefix_format=self.ts_format)
            printer.print_styled(*styled_status_line)
            sys.stdout.flush()
        except BrokenPipeError:
            self._receiver.close_and_wait()
            cliutil.handle_broken_pipe(exit_code=1)
