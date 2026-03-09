"""TUI widgets for the instance detail view.

Textual quick reference for maintainers:
- Static is a built-in widget for displaying content. Subclass it and override render()
  to return a Rich renderable (Text, Table, Panel, etc.) — Textual renders Rich natively.
- Tree[str] is a built-in interactive tree widget. Each TreeNode stores a `data` value (here: phase_id).
  Nodes are navigable with arrow keys and fire NodeHighlighted / NodeSelected events.
- RichLog is a scrollable, append-only log widget. Supports auto-scroll and incremental writes.
- render() is called whenever the widget needs to repaint (after refresh(), resize, etc.).
- refresh() marks the widget as dirty so render() is called on the next frame.
- set_interval(secs, callback) creates a repeating timer on the event loop. Returns a Timer
  object with .stop()/.pause()/.resume(). Callback runs on Textual's thread — safe to mutate state.
- on_mount() fires once after the widget is added to the DOM and sized — safe to start timers here.
- Widget class name is used as the CSS selector (InstanceHeader → `InstanceHeader { ... }` in TCSS).
"""

from bisect import insort
from typing import Callable, Iterable, Optional

from rich.text import Text
from textual import work
from textual.app import App
from textual.containers import Vertical
from textual.message import Message
from textual.theme import Theme as TextualTheme
from textual.widgets import RichLog, Static, Tree
from textual.widgets._tree import TreeNode
from textual.worker import get_current_worker

from runtools.runcore import util
from runtools.runcore.client import InstanceCallError
from runtools.runcore.job import JobInstance, JobRun, InstanceOutputEvent
from runtools.runcore.output import OutputLine, OutputReadError
from runtools.runcore.run import Outcome, PhaseRun, Stage
from runtools.runcore.util import format_dt_local_tz
from runtools.taro.style import stage_style, run_term_style, term_style
from runtools.taro.theme import Theme
from runtools.taro.view.status_render import render_status


TARO_THEME = TextualTheme(
    name="taro",
    primary="#3dd6b5",       # electric mint — primary identity
    secondary="#9bb1c8",     # cool blue-gray — metadata
    accent="#ffb347",        # apricot amber — focus/selection
    background="#0f1117",    # charcoal black
    surface="#171b24",       # slate surface
    panel="#1f2531",         # raised panel
    success="#7ee787",       # vivid green
    warning="#ffb347",       # amber warning
    error="#ff6b6b",         # coral red
    dark=True,
    variables={
        "footer-background": "#171b24",
    },
)


def setup_theme(app: "App") -> None:
    """Register and activate the Taro theme."""
    app.register_theme(TARO_THEME)
    app.theme = TARO_THEME.name


APP_CSS = """
Screen {
    background: $background;
    scrollbar-color: $accent 50%;
    scrollbar-color-hover: $accent 80%;
    scrollbar-color-active: $accent;
    scrollbar-background: $surface-darken-1;
    scrollbar-background-hover: $surface-darken-1;
    scrollbar-background-active: $surface-darken-2;
}
ConfirmDeleteScreen {
    background: $background 60% !important;
}
Footer {
    background: $surface;
    .footer-key--key {
        background: $accent 35%;
        color: $text;
    }
    .footer-key--description {
        color: $text-muted;
        background: $surface;
    }
}
"""


class Section(Vertical):
    """Bordered section card with focus-within emphasis."""

    DEFAULT_CSS = """
    Section {
        border: round $accent 25%;
        border-title-color: $text-muted;
        border-title-align: left;
        padding: 0 1;
        margin-bottom: 0;
        background: $surface;

        &:focus-within {
            border: round $accent 80%;
            border-title-color: $accent;
            border-title-style: bold;
        }

        .datatable--header {
            color: $text-muted;
        }
    }
    """


_METRIC_SEP = "  ·  "


def build_history_metrics(runs: Iterable[JobRun], *, active_count: int | None = None) -> Text:
    """Build a styled metrics bar from job runs.

    Args:
        runs: Job runs to summarise (typically history).
        active_count: If provided, prepend an "N active" segment.
    """
    run_list = list(runs)
    failed = sum(1 for r in run_list if r.lifecycle.termination
                 and r.lifecycle.termination.status.outcome == Outcome.FAULT)
    succeeded = sum(1 for r in run_list if r.lifecycle.termination
                    and r.lifecycle.termination.status.outcome == Outcome.SUCCESS)
    other = len(run_list) - succeeded - failed

    text = Text()
    if active_count is not None:
        text.append(f"{active_count} active", style=Theme.state_executing if active_count else "dim")
        text.append(_METRIC_SEP, style="dim")
    text.append(f"{succeeded} completed", style="dim")
    text.append(_METRIC_SEP, style="dim")
    text.append(f"{failed} failed", style=Theme.state_failure if failed else "dim")
    if other:
        text.append(_METRIC_SEP, style="dim")
        text.append(f"{other} other", style="dim")
    return text


class ScreenHeader(Static):
    """Reusable two-row header: title + env on row 1, metrics on row 2.

    Row 1: {title}                          {env_name}
    Row 2: metrics text (styled, caller-provided via update_metrics)
    """

    DEFAULT_CSS = """
    ScreenHeader {
        dock: top;
        height: auto;
        padding: 1 2 0 2;
        background: $panel;
        border-bottom: wide $accent 40%;
    }
    """

    def __init__(self, title: str, env_name: str = "") -> None:
        super().__init__()
        self._title = title
        self._env_name = env_name
        self._metrics = Text()

    def update_metrics(self, metrics: Text) -> None:
        self._metrics = metrics
        self.refresh()

    def render(self) -> Text:
        width = self.size.width if self.size.width > 0 else 80
        env_part = Text(f"[ {self._env_name} ]", style=Theme.subtle) if self._env_name else Text()
        title_part = Text(self._title, style=Theme.title)
        pad = width - title_part.cell_len - env_part.cell_len
        line1 = Text()
        line1.append_text(title_part)
        if pad > 0:
            line1.append(" " * pad)
        line1.append_text(env_part)

        if self._metrics.cell_len == 0:
            return line1
        result = Text()
        result.append_text(line1)
        result.append("\n")
        result.append_text(self._metrics)
        return result


class InstanceHeader(Static):
    """Header widget showing job identity, stage, timestamps, and status line.

    Renders two or three rows:
      Row 1: {job_id} @ {run_id}
      Row 2: {STAGE}  ·  created {time}  ·  [ended {time}  ·]  elapsed {time}
      Row 3: Status line (only when active operations/progress exist)

    In live mode, a 0.25-second timer calls refresh() to keep the elapsed time ticking.
    The timer is stopped when the job ends.
    """

    def __init__(self, job_run: JobRun, *, live: bool = False) -> None:
        super().__init__()
        self._job_run = job_run
        self._live = live
        self._timer = None

    def on_mount(self) -> None:
        if self._live and not self._job_run.lifecycle.is_ended:
            # refresh() triggers render() on the next frame — elapsed time and spinner update each tick
            self._timer = self.set_interval(0.25, self.refresh)

    def update_run(self, job_run: JobRun) -> None:
        """Replace the snapshot and refresh. Called from InstanceScreen on each event."""
        self._job_run = job_run
        if self._live and job_run.lifecycle.is_ended and self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.refresh()

    _TIME_LABEL_WIDTH = 9  # "created  ", "ended    ", "elapsed  "

    def render(self) -> Text:
        """Build the header as a Rich Text object. Textual renders it directly."""
        job_run = self._job_run
        lifecycle = job_run.lifecycle
        width = self.size.width if self.size.width > 0 else 80

        # Build right-side time rows (aligned labels)
        created_str = format_dt_local_tz(lifecycle.created_at, null="N/A", include_ms=False)
        time_rows = [("created", created_str)]

        if lifecycle.is_ended and lifecycle.termination:
            ended_str = format_dt_local_tz(lifecycle.termination.terminated_at, null="N/A", include_ms=False)
            time_rows.append(("ended", ended_str))

        elapsed = lifecycle.elapsed
        elapsed_str = util.format_timedelta(elapsed, show_ms=False, null="--:--:--")
        time_rows.append(("elapsed", elapsed_str))

        # Fixed-width right column so labels align vertically
        max_row_len = max(self._TIME_LABEL_WIDTH + len(v) for _, v in time_rows)

        def _compose_line(left_part: Text, time_label: str, time_value: str) -> Text:
            right_part = Text()
            right_part.append(f"{time_label:<{self._TIME_LABEL_WIDTH}}", style="dim")
            right_part.append(time_value, style=Theme.metadata)
            pad = width - left_part.cell_len - max_row_len
            line = Text()
            line.append_text(left_part)
            if pad > 0:
                line.append(" " * pad)
            line.append_text(right_part)
            return line

        # Row 1: job_id @ run_id  STAGE                 created  HH:MM:SS
        id_part = Text()
        id_part.append(job_run.job_id, style=Theme.job)
        id_part.append(" @ ", style="")
        id_part.append(job_run.run_id, style=Theme.metadata)

        if lifecycle.is_ended and lifecycle.termination:
            stage_text = lifecycle.termination.status.name
        else:
            stage_text = lifecycle.stage.name
        id_part.append("  ")
        id_part.append(stage_text, style=_stage_rich_style(job_run))

        label, value = time_rows[0]
        result = _compose_line(id_part, label, value)

        # Remaining time rows: right-aligned under the first
        for label, value in time_rows[1:]:
            result.append("\n")
            result.append_text(_compose_line(Text(), label, value))

        # Status line (only when there's something to show)
        status_line = render_status(job_run.status, width)
        if status_line.cell_len > 0:
            result.append("\n")
            result.append_text(status_line)

        return result


class PhaseSelected(Message):
    """Posted when a phase node is highlighted in the tree."""

    def __init__(self, phase_id: str) -> None:
        super().__init__()
        self.phase_id = phase_id


class PhaseTree(Tree[str]):
    """Interactive tree widget showing the phase hierarchy of a job run.

    Each node displays: {phase_id}  {STAGE}  {elapsed}
    Color-coded by stage/outcome. Nodes are navigable with arrow keys.
    ``TreeNode.data`` stores the ``phase_id`` string for O(1) lookup.

    Always expanded — nodes cannot be collapsed.
    In live mode, a 1-second timer keeps elapsed times ticking.
    """

    ICON_NODE = ""
    ICON_NODE_EXPANDED = ""

    def action_toggle_node(self) -> None:
        """Prevent collapsing — tree is always fully expanded."""
        pass

    def __init__(self, job_run: JobRun, *, live: bool = False) -> None:
        root_phase = job_run.root_phase
        super().__init__(_phase_label(root_phase), data=root_phase.phase_id)
        self._job_run = job_run
        self._live = live
        self._timer = None
        self._node_map: dict[str, TreeNode[str]] = {}

    def on_mount(self) -> None:
        self._populate_children(self.root, self._job_run.root_phase)
        self.root.expand_all()
        if self._live and not self._job_run.lifecycle.is_ended:
            self._timer = self.set_interval(1.0, self._update_labels)

    def update_run(self, job_run: JobRun) -> None:
        """Replace the snapshot and refresh. Called from InstanceScreen on each event."""
        self._job_run = job_run
        if self._live and job_run.lifecycle.is_ended and self._timer is not None:
            self._timer.stop()
            self._timer = None

        new_ids = collect_phase_ids(job_run.root_phase)
        if new_ids == set(self._node_map.keys()) | {job_run.root_phase.phase_id}:
            self._update_labels()
        else:
            self._rebuild()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Post PhaseSelected when the cursor moves to a node."""
        if event.node.data is not None:
            self.post_message(PhaseSelected(event.node.data))

    def _populate_children(self, parent_node: TreeNode[str], phase: PhaseRun) -> None:
        """Recursively add children to the Textual tree and register them in _node_map."""
        for child in phase.children:
            child_node = parent_node.add(_phase_label(child), data=child.phase_id)
            self._node_map[child.phase_id] = child_node
            self._populate_children(child_node, child)

    def _update_labels(self) -> None:
        """Refresh all node labels from the current snapshot without rebuilding structure."""
        root_phase = self._job_run.root_phase
        self.root.set_label(_phase_label(root_phase))
        self._update_labels_recursive(root_phase)

    def _update_labels_recursive(self, phase: PhaseRun) -> None:
        for child in phase.children:
            node = self._node_map.get(child.phase_id)
            if node is not None:
                node.set_label(_phase_label(child))
            self._update_labels_recursive(child)

    def _rebuild(self) -> None:
        """Clear and re-populate the entire tree (structure changed)."""
        cursor_phase_id = self.cursor_node.data if self.cursor_node else None

        self.root.remove_children()
        self._node_map.clear()

        root_phase = self._job_run.root_phase
        self.root.set_label(_phase_label(root_phase))
        self.root.data = root_phase.phase_id
        self._populate_children(self.root, root_phase)
        self.root.expand_all()

        # Restore cursor position if the previously highlighted phase still exists
        if cursor_phase_id and cursor_phase_id in self._node_map:
            self.select_node(self._node_map[cursor_phase_id])


class PhaseDetail(Static):
    """Detail panel showing full information about the currently selected phase.

    Renders a Rich Text block with phase metadata, lifecycle timestamps, and diagnostics.
    Updated when the user navigates the PhaseTree or when a new snapshot arrives.
    """

    def __init__(self, job_run: JobRun, *, live: bool = False) -> None:
        super().__init__()
        self._job_run = job_run
        self._phase_id = job_run.root_phase.phase_id
        self._live = live
        self._timer = None

    def on_mount(self) -> None:
        if self._live and not self._job_run.lifecycle.is_ended:
            self._timer = self.set_interval(1.0, self.refresh)

    def update_phase(self, phase_id: str) -> None:
        """Select a different phase to display."""
        self._phase_id = phase_id
        self.refresh()

    def update_run(self, job_run: JobRun) -> None:
        """Replace the snapshot and refresh."""
        self._job_run = job_run
        if self._live and job_run.lifecycle.is_ended and self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.refresh()

    def render(self) -> Text:
        phase = self._job_run.find_phase_by_id(self._phase_id)
        if phase is None:
            return Text("Phase not found", style="dim")

        style = _phase_style(phase)
        lifecycle = phase.lifecycle
        text = Text()

        # Operations filtered by selected phase + descendants (root shows all)
        if self._job_run.status and self._job_run.status.operations:
            if self._phase_id == self._job_run.root_phase.phase_id:
                visible_ops = self._job_run.status.operations
            else:
                phase_ids = collect_phase_ids(phase)
                visible_ops = [op for op in self._job_run.status.operations if op.source in phase_ids]
            fmt_num = lambda v: str(int(v)) if v == int(v) else str(v)
            for op in visible_ops:
                if op.finished:
                    text.append(f"{op.finished_summary}\n", style="dim")
                else:
                    text.append(f"{op.name}", style="")
                    if op.pct_done is not None:
                        pct = round(max(0.0, min(op.pct_done, 1.0)) * 100)
                        text.append(f" {pct}%", style=Theme.state_executing)
                    if op.completed is not None:
                        parts = fmt_num(op.completed)
                        if op.total is not None:
                            parts += f"/{fmt_num(op.total)}"
                        if op.unit:
                            parts += f" {op.unit}"
                        text.append(f" {parts}", style=Theme.metadata)
                    text.append("\n")
            if visible_ops:
                text.append("─" * 30 + "\n", style=Theme.metadata)

        # Phase ID and type
        text.append(phase.phase_id, style=Theme.label)
        if phase.phase_type:
            text.append(f"  ({phase.phase_type})", style=Theme.metadata)
        text.append("\n")

        # Stage / termination status
        text.append(_phase_stage_text(phase), style=style)
        text.append("\n")

        # Timestamps — always show created; show started only when it meaningfully differs (wait time)
        text.append(f"Created:     {format_dt_local_tz(lifecycle.created_at, null='N/A', include_ms=False)}\n",
                     style=Theme.metadata)
        if lifecycle.started_at and int(lifecycle.created_at.timestamp()) != int(lifecycle.started_at.timestamp()):
            text.append(f"Started:     {format_dt_local_tz(lifecycle.started_at, null='N/A', include_ms=False)}\n",
                         style=Theme.metadata)
        if lifecycle.termination:
            text.append(
                f"Terminated:  {format_dt_local_tz(lifecycle.termination.terminated_at, null='N/A', include_ms=False)}"
                "\n",
                style=Theme.metadata,
            )

        # Elapsed / total run time
        elapsed = util.format_timedelta(lifecycle.total_run_time or lifecycle.elapsed, show_ms=False, null="N/A")
        text.append(f"Elapsed:     {elapsed}\n", style=Theme.metadata)

        # Stop reason
        if phase.stop_reason:
            text.append(f"Stop reason: {phase.stop_reason.name}\n", style=Theme.state_incomplete)

        # Termination message
        if lifecycle.termination and lifecycle.termination.message:
            text.append(f"Message:     {lifecycle.termination.message}\n")

        # Attributes
        if phase.attributes:
            text.append("\nAttributes\n", style=Theme.section_heading)
            for key, value in phase.attributes.items():
                text.append(f"  {key}: {value}\n", style=Theme.metadata)

        # Variables
        if phase.variables:
            text.append("\nVariables\n", style=Theme.section_heading)
            for key, value in phase.variables.items():
                text.append(f"  {key}: {value}\n", style=Theme.metadata)

        # Faults
        if self._job_run.faults:
            text.append("\nFaults\n", style=Theme.state_failure)
            for fault in self._job_run.faults:
                text.append(f"  [{fault.category}] {fault.reason}\n", style=Theme.error)
                if fault.stack_trace:
                    text.append(f"{fault.stack_trace}\n", style="dim")

        # Termination stack trace
        if lifecycle.termination and lifecycle.termination.stack_trace:
            text.append("\nStack trace\n", style=Theme.state_failure)
            text.append(f"{lifecycle.termination.stack_trace}\n", style="dim")

        # Children count
        if phase.children:
            text.append(f"\n{len(phase.children)} {'child' if len(phase.children) == 1 else 'children'}\n",
                         style=Theme.metadata)

        return text


class OutputBuffer:
    """Ordered, deduplicated buffer for output lines.

    Handles out-of-order arrival via ordinal-based insertion sort and deduplication.
    """

    def __init__(self):
        self._lines: list[OutputLine] = []
        self._seen: set[int] = set()

    def add_line(self, line: OutputLine):
        if line.ordinal in self._seen:
            return
        self._seen.add(line.ordinal)
        if not self._lines or line.ordinal > self._lines[-1].ordinal:
            self._lines.append(line)
        else:
            insort(self._lines, line, key=lambda l: l.ordinal)

    def add_lines(self, lines: Iterable[OutputLine]):
        for line in lines:
            self.add_line(line)

    def get_lines(self, phase_ids: set[str] | None = None) -> list[OutputLine]:
        if phase_ids is None:
            return list(self._lines)
        return [line for line in self._lines if line.source in phase_ids]


class OutputPanel(RichLog):
    """Bottom panel displaying job output with phase filtering.

    In live mode, subscribes to output events and appends lines in real-time.
    Supports filtering by phase subtree — selecting a phase shows output from
    that phase and all its descendants.

    History mode loads only the last _DEFAULT_TAIL_LINES by default for fast startup.
    Press 'f' (via InstanceScreen binding) to load full output.
    """

    _WRITE_BATCH_SIZE = 500
    _DEFAULT_TAIL_LINES = 1000

    def __init__(self, instance: Optional[JobInstance], job_run: JobRun, *,
                 output_reader: Optional[Callable] = None, live: bool = False) -> None:
        super().__init__(wrap=True, highlight=False, markup=False)
        self._instance = instance
        self._job_run = job_run
        self._output_reader = output_reader
        self._live = live
        self._buffer = OutputBuffer()
        self._phase_filter: set[str] | None = None  # None = show all
        self._load_generation = 0  # incremented on any reload (filter change or full load)
        self._tail_mode: bool = not live  # history starts in tail mode
        self._output_observer = None

    def on_mount(self) -> None:
        # Subscribe to live events BEFORE fetching tail (dedup handles overlap)
        if self._live and self._instance is not None:
            self._output_observer = _OutputObserver(self)
            self._instance.notifications.add_observer_output(self._output_observer)
        # Load output: live tail for active instances (fast, in-memory)
        if self._instance is not None:
            try:
                self._buffer.add_lines(self._instance.output.tail())
                self._write_batch(self._buffer.get_lines(self._phase_filter))
            except InstanceCallError:
                # Instance may have ended — fall back to storage reader
                if self._output_reader:
                    self._reload_history()
        elif self._output_reader:
            self._reload_history()

    def on_unmount(self) -> None:
        if self._instance is not None and self._output_observer is not None:
            self._instance.notifications.remove_observer_output(self._output_observer)
            self._output_observer = None

    def _on_output(self, event: InstanceOutputEvent) -> None:
        """Handle a live output event — called on Textual's event loop via call_from_thread."""
        self._buffer.add_line(event.output_line)
        line = event.output_line
        if self._phase_filter is None or line.source in self._phase_filter:
            self._write_line(line)

    def _reload_history(self) -> None:
        """Clear display and reload history output from storage with current filter/tail settings."""
        self._load_generation += 1
        self.clear()
        self._load_history_output()

    @work(thread=True, exclusive=True, group="output_load")
    def _load_history_output(self) -> None:
        """Load stored output in a background thread, writing batches to the UI."""
        worker = get_current_worker()
        max_lines = self._DEFAULT_TAIL_LINES if self._tail_mode else 0
        try:
            lines = self._output_reader(
                self._job_run.instance_id, sources=self._phase_filter, max_lines=max_lines,
            )
        except OutputReadError as e:
            if not worker.is_cancelled:
                self.app.call_from_thread(self.write, Text(f"Error reading output: {e}", style=Theme.error))
            return

        gen = self._load_generation
        truncated = self._tail_mode and len(lines) >= self._DEFAULT_TAIL_LINES

        for i in range(0, len(lines), self._WRITE_BATCH_SIZE):
            if worker.is_cancelled or gen != self._load_generation:
                return
            batch = lines[i:i + self._WRITE_BATCH_SIZE]
            self.app.call_from_thread(self._write_batch, batch)

        if truncated and not worker.is_cancelled and gen == self._load_generation:
            self.app.call_from_thread(
                self.write,
                Text(f"── showing last {self._DEFAULT_TAIL_LINES} lines (press F for full output) ──", style="dim"),
            )

    def update_phase_filter(self, phase_ids: set[str] | None) -> None:
        """Filter output to a phase subtree (None = all)."""
        if phase_ids == self._phase_filter:
            return
        self._phase_filter = phase_ids
        if self._live:
            # Live mode: filter from in-memory buffer (instant)
            self._load_generation += 1
            self.clear()
            self._write_batch(self._buffer.get_lines(phase_ids))
        else:
            # History mode: reload from storage with targeted sources + max_lines
            self._reload_history()

    def load_full(self) -> None:
        """Switch from tail mode to full output and reload."""
        if not self._tail_mode:
            return
        self._tail_mode = False
        self._reload_history()

    def _write_batch(self, lines: list[OutputLine]) -> None:
        """Write multiple lines as a single Text object to minimize DOM updates."""
        if not lines:
            return
        batch = Text()
        for i, line in enumerate(lines):
            if i > 0:
                batch.append("\n")
            batch.append(line.message, style=Theme.error if line.is_error else "")
        self.write(batch)

    def _write_line(self, line: OutputLine) -> None:
        self.write(Text(line.message, style=Theme.error if line.is_error else ""))


class _OutputObserver:
    """Bridges runcore output events (background thread) to OutputPanel (Textual event loop)."""

    def __init__(self, panel: OutputPanel) -> None:
        self._panel = panel

    def instance_output_update(self, event: InstanceOutputEvent) -> None:
        self._panel.app.call_from_thread(self._panel._on_output, event)


def _phase_stage_text(phase: PhaseRun) -> str:
    """Resolve display text for a phase's current stage."""
    lifecycle = phase.lifecycle
    if lifecycle.is_ended and lifecycle.termination:
        return lifecycle.termination.status.name
    if phase.is_idle:
        return "WAITING"
    return lifecycle.stage.name


def collect_phase_ids(phase: PhaseRun) -> set[str]:
    """Collect all phase_ids from a phase tree (including the root)."""
    ids = {phase.phase_id}
    for child in phase.children:
        ids.update(collect_phase_ids(child))
    return ids


def _phase_label(phase: PhaseRun) -> Text:
    """Build a styled label: '{phase_id}  {STAGE}  {elapsed}'."""
    style = _phase_style(phase)
    lifecycle = phase.lifecycle

    label = Text()
    label.append(phase.phase_id, style=style)
    label.append(f"  {_phase_tree_stage_text(phase)}", style=style)

    elapsed_str = util.format_timedelta(lifecycle.elapsed, show_ms=False, null="")
    if elapsed_str:
        label.append(f"  {elapsed_str}", style=style)

    return label


def _phase_tree_stage_text(phase: PhaseRun) -> str:
    """Compact status text used in the phase tree labels."""
    lifecycle = phase.lifecycle
    if lifecycle.is_ended and lifecycle.termination:
        return "✓" if lifecycle.termination.status.outcome == Outcome.SUCCESS else "✗"
    return _phase_stage_text(phase)


def _phase_style(phase: PhaseRun) -> str:
    """Determine Rich style string for a phase node."""
    if phase.stop_requested:
        return Theme.state_incomplete
    if phase.is_idle:
        return Theme.idle

    lifecycle = phase.lifecycle
    if lifecycle.stage == Stage.RUNNING:
        return Theme.state_executing
    if lifecycle.stage == Stage.CREATED:
        return Theme.state_before_execution
    # ENDED
    if lifecycle.termination:
        style = term_style(lifecycle.termination.status)
        return style if style else "dim"
    return "dim"


def _stage_rich_style(job_run: JobRun) -> str:
    """Determine Rich style for the stage/termination indicator."""
    if job_run.lifecycle.is_ended and job_run.lifecycle.termination:
        return run_term_style(job_run)
    return stage_style(job_run)
