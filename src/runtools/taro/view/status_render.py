"""Rich Text rendering for job status with visual progress bars.

Produces styled ``Text`` objects suitable for both TUI (Textual DataTable cells)
and Rich Live/Table views. All cells stay as ``Text`` — no custom renderables.
"""

from rich.text import Text

from runtools.runcore.status import Operation, Status

MAX_BAR = 30
SEPARATOR = "  "
WIDTH_SAFETY_MARGIN = 3


def render_status(status: Status | None, width: int) -> Text:
    """Render status as styled Text, with visual progress bars when possible.

    Fallback ladder (uniform level for all ops, then greedy per-op):
      1. Full bars: ``name done/total unit ━━╸━━ pct%`` — width evenly divided
      2. Short bars: ``name ━━╸━━ pct%`` — width evenly divided
      3. Compact ``name pct%`` for each op (greedy)
      4. Percent only ``pct%`` for each op (greedy)
      5. ``+N`` suffix for ops that don't fit

    Args:
        status: Current job status snapshot (may be None).
        width: Available character width for the cell.
    """
    if not status:
        return Text("")

    progress_ops = [op for op in status.operations if not op.finished and op.pct_done is not None and op.total > 0]

    if not progress_ops:
        return Text(str(status))

    # Be conservative: runtime table layout may be a few chars tighter than hints.
    effective_width = max(width - WIDTH_SAFETY_MARGIN, 0)

    # Try uniform representation levels — distribute width evenly
    n = len(progress_ops)
    sep_total = len(SEPARATOR) * (n - 1)
    per_op_width = (effective_width - sep_total) // n

    for bar_builder in (_build_bar, _build_short_bar):
        bars = [bar_builder(op, per_op_width) for op in progress_ops]
        if all(bars):
            return _join(bars)

    # Greedy fallback: compact → pct only → +N
    result = Text()
    remaining = effective_width

    for i, op in enumerate(progress_ops):
        leftover_count = len(progress_ops) - i - 1
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
                # Final compact fallback: always show at least one signal, not full status text.
                head = _pct_only(op)
                if count > 1:
                    head.append(f" +{count - 1}", style="dim")
                return head
            result.append(f" +{count}", style="dim")
            break

    return result


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
