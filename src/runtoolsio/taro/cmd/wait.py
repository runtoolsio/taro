"""
TODO: Create option where the command will terminates if the specified state is found in the previous or current state
      of an existing instance.
"""
from runtoolsio.runcore.criteria import compound_instance_filter
from runtoolsio.runcore.job import JobRun
from runtoolsio.runcore.listening import InstanceTransitionReceiver, InstanceTransitionObserver
from runtoolsio.runcore.run import PhaseRun
from runtoolsio.runcore.util import MatchingStrategy, DateTimeFormat

from runtoolsio.taro import argsutil
from runtoolsio.taro import printer, style, cliutil


def run(args):
    instance_match = compound_instance_filter(argsutil.instance_criteria(args, MatchingStrategy.PARTIAL))
    receiver = InstanceTransitionReceiver(instance_match, args.phases)
    receiver.add_observer_transition(EventHandler(receiver, args.count, args.timestamp.value))
    receiver.start()
    cliutil.exit_on_signal(cleanups=[receiver.close_and_wait])
    receiver.wait()  # Prevents 'exception ignored in: <module 'threading' from ...>` error message, remove when fixed


class EventHandler(InstanceTransitionObserver):

    def __init__(self, receiver, count=1, ts_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE):
        self._receiver = receiver
        self.count = count
        self.ts_format = ts_format

    def new_instance_phase(self, job_run: JobRun, previous_phase: PhaseRun, new_phase: PhaseRun, ordinal: int):
        try:
            printer.print_styled(*style.run_status_line(job_run, ts_prefix_format=self.ts_format))
        except BrokenPipeError:
            self._receiver.close_and_wait()
            cliutil.handle_broken_pipe(exit_code=1)

        self.count -= 1
        if self.count <= 0:
            self._receiver.close()
