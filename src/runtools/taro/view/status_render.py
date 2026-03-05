"""Rich Text rendering for job status with visual progress bars.

Produces styled ``Text`` objects suitable for both TUI (Textual DataTable cells)
and Rich Live/Table views. All cells stay as ``Text`` — no custom renderables.
"""

import time

from rich.text import Text

from runtools.runcore.status import Operation, Status

MAX_BAR = 30
SEPARATOR = "  "
GROUP_SEPARATOR = "  ·  "
WIDTH_SAFETY_MARGIN = 3
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPINNER_FPS = 8


def render_status(status: Status | None, width: int) -> Text:
    """Render status as styled Text, with visual progress bars when possible.

    Operations with a known total get progress bars (fallback ladder).
    Operations without a total get a spinner with count.
    All ops are rendered in creation order.

    Args:
        status: Current job status snapshot (may be None).
        width: Available character width for the cell.
    """
    if not status:
        return Text("")

    active_ops = [op for op in status.operations if not op.finished]
    if not active_ops:
        return Text(str(status))

    bar_ops = [op for op in active_ops if _has_progress(op)]

    # Be conservative: runtime table layout may be a few chars tighter than hints.
    effective_width = max(width - WIDTH_SAFETY_MARGIN, 0)

    # Pre-render spinner ops (fixed width); compute remaining width for bar ops.
    spinner_cache = {id(op): _spinner(op) for op in active_ops if not _has_progress(op)}
    spinner_total = sum(t.cell_len for t in spinner_cache.values())
    sep_total = len(GROUP_SEPARATOR) * (len(active_ops) - 1)  # conservative estimate
    bar_width = effective_width - spinner_total - sep_total

    # Pick uniform bar level for all bar ops.
    bar_cache = _build_uniform_bars(bar_ops, bar_width)

    # Assemble in creation order, with a · between different op types.
    result = Text()
    prev_is_spinner: bool | None = None
    for op in active_ops:
        op_id = id(op)
        is_spinner = op_id in spinner_cache
        text = spinner_cache.get(op_id) or (bar_cache or {}).get(op_id)
        if text is None:
            continue
        if result.cell_len > 0:
            sep = GROUP_SEPARATOR if prev_is_spinner != is_spinner else SEPARATOR
            result.append(sep, style="dim")
        result.append_text(text)
        prev_is_spinner = is_spinner

    return result if result.cell_len > 0 else Text(str(status))


def _has_progress(op: Operation) -> bool:
    return op.pct_done is not None and op.total > 0


def _build_uniform_bars(bar_ops: list[Operation], width: int) -> dict[int, Text] | None:
    """Build bar representations for ops with known totals, keyed by id(op).

    Tries uniform levels (full bar → short bar → compact → pct only).
    Returns None if no bar ops or width is insufficient.
    """
    if not bar_ops or width <= 0:
        return None

    n = len(bar_ops)
    per_op_width = width // n if n else 0

    for builder in (_build_bar, _build_short_bar):
        bars = [builder(op, per_op_width) for op in bar_ops]
        if all(bars):
            return {id(op): bar for op, bar in zip(bar_ops, bars)}

    # Greedy fallback: compact → pct only
    result = {}
    remaining = width
    for i, op in enumerate(bar_ops):
        sep = len(SEPARATOR) if i > 0 else 0
        for renderer in (_compact, _pct_only):
            text = renderer(op)
            if text.cell_len + sep <= remaining:
                result[id(op)] = text
                remaining -= text.cell_len + sep
                break
        else:
            break

    return result if result else None


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
