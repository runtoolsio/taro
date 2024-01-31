from runtools.runcore.util import socket

from runtools.runjob import api, events
from runtools.taro import printer
from runtools.taro.theme import Theme


def run(args):
    # TODO Disable socket log messages
    clean_socket(api.API_FILE_EXTENSION, "API")
    clean_socket(events.TRANSITION_LISTENER_FILE_EXTENSION, "transition listeners")
    clean_socket(events.OUTPUT_LISTENER_FILE_EXTENSION, "output listeners")


def clean_socket(file_extension, socket_group):
    cleaned = socket.clean_stale_sockets(file_extension)
    print(f"Cleaned sockets for {socket_group}: {len(cleaned)}")
    for c in cleaned:
        printer.print_styled(('', '  cleaned: '), (Theme.warning, c))
