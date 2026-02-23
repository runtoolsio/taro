import itertools
import os
import re
import sys
from collections import namedtuple
from typing import List, Dict, Tuple

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from pypager.pager import Pager
from pypager.source import GeneratorSource

from runtools.runcore.util import iterates

Column = namedtuple('Column', 'name max_width value_fnc colour_fnc')

_ANSI_COLORS = {'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'gray', 'white'}


def _to_pt_style(style: str) -> str:
    """Convert standard color names to prompt_toolkit ANSI names.

    Args:
        style: Space-separated style tokens (e.g. ``"bold bright_red"``).

    Returns:
        Converted style string (e.g. ``"bold ansibrightred"``).
    """
    if not style:
        return style
    converted = []
    for token in style.split():
        if token in _ANSI_COLORS:
            converted.append('ansi' + token)
        elif token.startswith('bright_'):
            base = token[7:]  # strip 'bright_'
            if base in _ANSI_COLORS:
                converted.append('ansibright' + base)
            else:
                converted.append(token)
        else:
            converted.append(token)
    return ' '.join(converted)


def _print_not_formatted(style_text, *, file=None):
    print("".join(text for _, text in style_text), file=file)


def print_styled(*style_and_text: Tuple[str, str], file=None):
    """
    Print styled if printed to terminal.

    :param: style_and_text tuples of style and text to print
    """
    if sys.stdout.isatty():
        pt_pairs = [(_to_pt_style(style), text) for style, text in style_and_text]
        print_formatted_text(FormattedText(pt_pairs), file=file)
    else:
        _print_not_formatted(style_and_text, file=file)


@iterates
def print_table(items, columns: List[Column], *, show_header: bool, pager: bool, footer=()):
    gen = output_gen(items, columns, show_header, stretch_last_column=False, footer=footer)

    if pager and sys.stdout.isatty():
        p = Pager()
        p.add_source(GeneratorSource(line + [('', '\n')] for line in gen))
        p.run()
    else:
        while True:
            print_styled(*next(gen))


def output_gen(items, columns: List[Column], show_header: bool, stretch_last_column: bool, footer=()):
    """
    Table Representation:
        Each column has padding of size 1 from each side applied in both header and values
        Left and right padding is hardcoded in the format token " {:x} "
        Columns are separated by one space
        Header/Values separator line is of the same length as the column
    Column Widths:
        First 50 rows are examined to find optimal width of the columns
    """
    job_iter = iter(items)
    first_fifty = list(itertools.islice(job_iter, 50))
    column_widths = _calc_widths(first_fifty, columns, stretch_last_column)
    column_formats = [" {:" + str(w - 1) + "} " for w in column_widths]

    if show_header:
        yield [('bold', f.format(c.name)) for c, f in zip(columns, column_formats)]
        separator_line = " ".join("-" * w for w in column_widths)
        yield [('bold', separator_line)]

    for item in itertools.chain(first_fifty, job_iter):
        yield [(_to_pt_style(c.colour_fnc(item)), f.format(_limit_text(c.value_fnc(item), w - 2)))
               for c, w, f in zip(columns, column_widths, column_formats)]

    for line in footer:
        yield [(_to_pt_style(line[0]), line[1])]


def _calc_widths(items, columns: List[Column], stretch_last_column: bool):
    widths = [len(c.name) + 2 for c in columns]  # +2 for left and right padding
    for item in items:
        for i, column in enumerate(columns):
            widths[i] = max(widths[i], min(len(column.value_fnc(item)) + 2, column.max_width))

    # vv Add spare terminal length to the last column vv
    try:
        terminal_length = os.get_terminal_size().columns
    except OSError:
        return widths  # Failing in tests

    # Leave a small buffer to account for any edge cases (like wide Unicode characters)
    # or terminal quirks
    terminal_buffer = 1
    effective_terminal_width = terminal_length - terminal_buffer

    # Calculate the actual line length
    # Each column takes its width, plus we have (len(columns) - 1) separator spaces
    actual_length = sum(widths) + (len(columns) - 1)
    spare_length = effective_terminal_width - actual_length

    if spare_length > 0:
        if stretch_last_column:
            widths[-1] += spare_length
        else:
            max_length_in_last_column = \
                max(itertools.chain((len(columns[-1].value_fnc(i)) + 2 for i in items), (widths[-1],)))

            if max_length_in_last_column < widths[-1] + spare_length:
                widths[-1] = max_length_in_last_column
            else:
                widths[-1] += spare_length
    elif spare_length < 0:
        # We need to shrink to fit
        # Reduce the last column by the overflow amount
        widths[-1] = max(widths[-1] + spare_length, 4)  # Keep at least 4 chars

    return widths

def _limit_text(text, limit):
    if not text or len(text) <= limit:
        return text
    return text[:limit - 2] + '..'


def parse_table(output, columns) -> List[Dict[Column, str]]:
    """
    Parses individual lines from provided string containing ps table (must include both header and sep line).
    Columns of the table must be specified.

    :param output: output containing ps table
    :param columns: exact columns of the ps table in correct order
    :return: list of dictionaries where each dictionary represent one item line by column -> value mapping
    """

    lines = [line for line in output.splitlines() if line]  # Ignore empty lines
    header_idx = [i for i, line in enumerate(lines) if all(column.name in line for column in columns)]
    if not header_idx:
        raise ValueError('The output does not contain specified job table')
    column_sep_line = lines[header_idx[0] + 1]  # Line separating header and values..
    sep_line_pattern = re.compile('-+')  # ..consisting of `-` strings for each column
    column_spans = [column.span() for column in sep_line_pattern.finditer(column_sep_line)]
    return [dict(zip(columns, (line[slice(*span)].strip() for span in column_spans)))
            for line in lines[header_idx[0] + 2:]]


class ProgressBar:

    def __init__(self, *, bar_length=20, chart=True, progress=True, percentage=True,
                 complete_char="#", incomplete_char="-"):
        self.bar_length = bar_length
        self.chart = chart
        self.progress = progress
        self.percentage = percentage
        self.complete_char = complete_char
        self.incomplete_char = incomplete_char

    def build_bar(self, completed, total, unit=""):
        """
        Builds a text representing console progress bar.

        Original source: https://stackoverflow.com/a/15860757/1391441
        """
        completed_pct = float(completed) / float(total)
        complete_count = int(round(self.bar_length * completed_pct))
        incomplete_count = (self.bar_length - complete_count)
        bar = ""
        if self.chart:
            bar += "[" + self.complete_char * complete_count + self.incomplete_char * incomplete_count + "] "
        if self.progress:
            bar += f"{completed}/{total} "
            if unit:
                bar += f"{unit} "
        if self.percentage:
            bar += f"({round(completed_pct * 100, 0):.0f}%)"

        return bar.rstrip()

    def print_bar(self, completed, total, unit=""):
        bar = self.build_bar(completed, total, unit)
        suffix = " \r\n" if (float(completed) / float(total)) >= 1. else ""
        text = f"\r{bar}{suffix}"
        sys.stdout.write(text)
        sys.stdout.flush()
