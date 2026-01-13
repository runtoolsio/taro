import os
import signal
from typing import Callable, Sequence

import sys

from runtools.runcore.util import TRUE_OPTIONS


def handle_broken_pipe(*, exit_code):
    # According to the official Python doc: https://docs.python.org/3/library/signal.html#note-on-sigpipe
    # Python flushes standard streams on exit; redirect remaining output
    # to devnull to avoid another BrokenPipeError at shutdown
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    sys.exit(exit_code)  # Python exits with error code 1 on EPIPE


def user_confirmation(*, yes_on_empty=False, catch_interrupt=False, newline_before=False):
    print(("\n" if newline_before else "") + "Do you want to continue? [Y/n] ", end="")
    try:
        i = input()
    except KeyboardInterrupt:
        if catch_interrupt:
            return False
        else:
            raise

    return i.lower() in TRUE_OPTIONS or (yes_on_empty and '' == i)
