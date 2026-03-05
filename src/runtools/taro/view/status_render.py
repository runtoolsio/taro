"""Rich Text rendering for job status with visual progress bars.

Produces styled ``Text`` objects suitable for both TUI (Textual DataTable cells)
and Rich Live/Table views. All cells stay as ``Text`` — no custom renderables.
"""

import time

from rich.text import Text

from runtools.runcore.status import Operation, Status

MAX_BAR = 30
SEPARATOR = "  "
WIDTH_SAFETY_MARGIN = 3
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPINNER_FPS = 8


def render_status(status: Status | None, width: int) -> Text:
    """Render status as styled Text, with visual progress bars when possible.

    Operations with a known total get progress bars (fallback ladder).
    Operations without a total get a spinner with count.

    Args:
        status: Current job status snapshot (may be None).
        width: Available character width for the cell.
    """
    if not status:
        return Text("")

    active_ops = [op for op in status.operations if not op.finished]
    if not active_ops:
        return Text(str(status))

    bar_ops = [op for op in active_ops if op.pct_done is not None and op.total > 0]
    spinner_ops = [op for op in active_ops if op.pct_done is None or op.total <= 0]

    # Be conservative: runtime table layout may be a few chars tighter than hints.
    effective_width = max(width - WIDTH_SAFETY_MARGIN, 0)

    # Reserve space for spinner ops, then give the rest to bar ops.
    spinner_texts = [_spinner(op) for op in spinner_ops]
    spinner_width = sum(t.cell_len for t in spinner_texts) + len(SEPARATOR) * max(len(spinner_texts) - 1, 0)
    if bar_ops and spinner_texts:
        spinner_width += len(SEPARATOR)
    bar_width = effective_width - spinner_width

    bar_result = _render_bar_ops(bar_ops, bar_width) if bar_ops else None

    if bar_result and spinner_texts:
        result = bar_result
        for t in spinner_texts:
            result.append(SEPARATOR)
            result.append_text(t)
        return result
    elif bar_result:
        return bar_result
    elif spinner_texts:
        return _join(spinner_texts)

    return Text(str(status))


def _render_bar_ops(bar_ops: list[Operation], width: int) -> Text | None:
    """Render operations with known totals using the fallback ladder."""
    if width <= 0:
        return None

    # Try uniform representation levels — distribute width evenly
    n = len(bar_ops)
    sep_total = len(SEPARATOR) * (n - 1)
    per_op_width = (width - sep_total) // n

    for bar_builder in (_build_bar, _build_short_bar):
        bars = [bar_builder(op, per_op_width) for op in bar_ops]
        if all(bars):
            return _join(bars)

    # Greedy fallback: compact → pct only → +N
    result = Text()
    remaining = width

    for i, op in enumerate(bar_ops):
        leftover_count = len(bar_ops) - i - 1
        reserve = len(f" +{leftover_count}") if leftover_count else 0
        sep = len(SEPARATOR) if i > 0 else 0

        for renderer in (_compact, _pct_only):
            text = renderer(op)
            if text.cell_len + sep <= remaining - reserve:
                if i > 0:
                    result.append(SEPARATOR)
                    remaining -= len(SEPARATOR)
                result.append_text(text)
                remaining -= text.cell_len
                break
        else:
            count = leftover_count + 1
            if not result:
                head = _pct_only(op)
                if count > 1:
                    head.append(f" +{count - 1}", style="dim")
                return head
            result.append(f" +{count}", style="dim")
            break

    return result if result.cell_len > 0 else None


def _join(texts: list[Text]) -> Text:
    result = Text()
    for i, t in enumerate(texts):
        if i > 0:
            result.append(SEPARATOR)
        result.append_text(t)
    return result


def _format_number(value: float) -> str:
    """Format a number: drop decimal if it's a whole number."""
    return str(int(value)) if value == int(value) else str(value)


def _spinner(op: Operation) -> Text:
    """Spinner representation for ops without a known total: ``name ⠹ count unit``."""
    frame = SPINNER_FRAMES[int(time.monotonic() * SPINNER_FPS) % len(SPINNER_FRAMES)]
    text = Text()
    text.append(f"{op.name} ", style="")
    text.append(frame, style="bright_blue")
    completed_str = _format_number(op.completed) if op.completed is not None else ""
    if completed_str:
        text.append(f" {completed_str}", style="dim")
        if op.unit:
            text.append(f" {op.unit}", style="dim")
    return text


def _compact(op: Operation) -> Text:
    """Compact representation: ``name pct%``."""
    pct = round(max(0.0, min(op.pct_done, 1.0)) * 100)
    text = Text()
    text.append(f"{op.name} ", style="")
    text.append(f"{pct}%", style="dim")
    return text


def _pct_only(op: Operation) -> Text:
    """Minimal representation: ``pct%``."""
    pct = round(max(0.0, min(op.pct_done, 1.0)) * 100)
    return Text(f"{pct}%", style="dim")


def _build_bar(op: Operation, width: int) -> Text | None:
    """Full bar: ``{name} {completed}/{total} {unit} ━━━╸╺━━━ {pct}%``"""
    completed_str = _format_number(op.completed)
    total_str = _format_number(op.total)
    prefix = f"{op.name} {completed_str}/{total_str}"
    if op.unit:
        prefix += f" {op.unit}"
    prefix += " "
    return _bar_with_prefix(op, prefix, width)


def _build_short_bar(op: Operation, width: int) -> Text | None:
    """Short bar: ``{name} ━━━╸╺━━━ {pct}%``"""
    return _bar_with_prefix(op, f"{op.name} ", width)


def _bar_with_prefix(op: Operation, prefix: str, width: int) -> Text | None:
    """Build a styled progress bar with the given prefix.

    Returns:
        Styled Text, or None if not enough space for a meaningful bar (min 4 chars).
    """
    clamped = max(0.0, min(op.pct_done, 1.0))
    pct = round(clamped * 100)
    suffix = f" {pct}%"

    bar_width = min(width - len(prefix) - len(suffix), MAX_BAR)
    if bar_width < 4:
        return None

    filled_total = bar_width * clamped
    filled = int(filled_total)
    remainder = filled_total - filled

    if filled >= bar_width:
        bright = "━" * bar_width
        dim_bar = ""
    elif remainder >= 0.5:
        bright = "━" * filled + "╸"
        dim_bar = "━" * (bar_width - filled - 1)
    else:
        bright = "━" * filled
        dim_bar = "╺" + "━" * (bar_width - filled - 1)

    text = Text()
    text.append(prefix)
    if bright:
        text.append(bright, style="bright_blue")
    if dim_bar:
        text.append(dim_bar, style="bright_black")
    text.append(suffix, style="dim")
    return text
