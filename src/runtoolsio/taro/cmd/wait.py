"""
TODO: Create option where the command will terminates if the specified state is found in the previous or current state
      of an existing instance.
"""
from runtoolsio.runcore.listening import InstanceTransitionReceiver, InstanceTransitionObserver
from runtoolsio.runcore.util import MatchingStrategy, DateTimeFormat

from runtoolsio.taro import argsutil
from runtoolsio.taro import printer, style, cliutil


def run(args):
    id_match = argsutil.id_match(args, MatchingStrategy.PARTIAL)
    receiver = InstanceTransitionReceiver(id_match, args.phases)
    receiver.add_observer_transition(EventHandler(receiver, args.count, args.timestamp.value))
    receiver.start()
    cliutil.exit_on_signal(cleanups=[receiver.close_and_wait])
    receiver.wait()  # Prevents 'exception ignored in: <module 'threading' from ...>` error message, remove when fixed


class EventHandler(InstanceTransitionObserver):

    def __init__(self, receiver, count=1, ts_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE):
        self._receiver = receiver
        self.count = count
        self.ts_format = ts_format

    def state_update(self, instance_meta, previous_phase, new_phase, changed):
        try:
            printer.print_styled(*style.job_instance_id_status_line_styled(
                instance_meta.id, new_phase, changed, ts_prefix_format=self.ts_format))
        except BrokenPipeError:
            self._receiver.close_and_wait()
            cliutil.handle_broken_pipe(exit_code=1)

        self.count -= 1
        if self.count <= 0:
            self._receiver.close()
