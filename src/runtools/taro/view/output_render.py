"""Shared output line formatting for TUI and CLI.

Provides plain and verbose renderers that produce Rich Text objects.
"""

from datetime import datetime

from rich.text import Text

from runtools.runcore.output import OutputLine
from runtools.taro.theme import Theme

_LEVEL_DISPLAY = {
    'DEBUG': ('DEBUG', Theme.log_debug),
    'INFO': ('INFO ', Theme.log_info),
    'WARNING': ('WARN ', Theme.warning),
    'WARN': ('WARN ', Theme.warning),
    'ERROR': ('ERROR', Theme.error),
    'CRITICAL': ('CRIT ', f'bold {Theme.error}'),
}


def abbreviate_logger(name: str) -> str:
    """Abbreviate logger name: 3+ segments → keep last 2."""
    parts = name.split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 3 else name


def format_time(timestamp: datetime) -> str:
    """Format a datetime as local HH:MM:SS.mmm for display."""
    local = timestamp.astimezone()
    return local.strftime('%H:%M:%S.') + f'{local.microsecond // 1000:03d}'


def _append_fields(text: Text, fields: dict, *, has_message: bool = True, error: bool = False) -> None:
    if has_message:
        text.append("  ")
    first = True
    for k, v in fields.items():
        if not first:
            text.append(" ")
        text.append(f"{k}=", style=Theme.log_field_key)
        text.append(str(v), style=Theme.error if error else "")
        first = False


def format_line_verbose(line: OutputLine) -> Text:
    text = Text()
    if line.timestamp:
        text.append(format_time(line.timestamp), style=Theme.log_timestamp)
        text.append(" ")
    if line.level:
        label, style = _LEVEL_DISPLAY.get(line.level, (f'{line.level:<5}', ''))
        text.append(label, style=style)
        text.append("  ")
    if line.logger:
        text.append(abbreviate_logger(line.logger), style=Theme.log_logger)
        text.append("  ")
    if line.thread:
        text.append(line.thread, style=Theme.log_timestamp)
        text.append("  ")
    text.append(line.message, style=Theme.error if line.is_error else "")
    if line.fields:
        _append_fields(text, line.fields, has_message=bool(line.message), error=line.is_error)
    return text


def format_line_plain(line: OutputLine) -> Text:
    text = Text(line.message, style=Theme.error if line.is_error else "")
    if line.fields:
        _append_fields(text, line.fields, has_message=bool(line.message), error=line.is_error)
    return text
