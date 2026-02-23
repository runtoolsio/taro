"""TUI widgets for the instance detail view.

Textual quick reference for maintainers:
- Static is a built-in widget for displaying content. Subclass it and override render()
  to return a Rich renderable (Text, Table, Panel, etc.) — Textual renders Rich natively.
- Tree[str] is a built-in interactive tree widget. Each TreeNode stores a `data` value (here: phase_id).
  Nodes are navigable with arrow keys and fire NodeHighlighted / NodeSelected events.
- render() is called whenever the widget needs to repaint (after refresh(), resize, etc.).
- refresh() marks the widget as dirty so render() is called on the next frame.
- set_interval(secs, callback) creates a repeating timer on the event loop. Returns a Timer
  object with .stop()/.pause()/.resume(). Callback runs on Textual's thread — safe to mutate state.
- on_mount() fires once after the widget is added to the DOM and sized — safe to start timers here.
- Widget class name is used as the CSS selector (InstanceHeader → `InstanceHeader { ... }` in TCSS).
"""

from rich.text import Text
from textual.message import Message
from textual.widgets import Static, Tree
from textual.widgets._tree import TreeNode

from runtools.runcore import util
from runtools.runcore.job import JobRun
from runtools.runcore.run import PhaseRun, Stage
from runtools.taro.style import stage_style, run_term_style, term_style
from runtools.taro.theme import Theme


class InstanceHeader(Static):
    """Header widget showing job identity, stage, elapsed time, and status line.

    Renders two rows:
      Row 1: {job_id} @ {run_id}    {STAGE}    elapsed: HH:MM:SS
      Row 2: Status.__str__() — active operations with progress, warnings

    In live mode, a 1-second timer calls refresh() to keep the elapsed time ticking.
    The timer is stopped when the job ends.
    """

    def __init__(self, job_run: JobRun, *, live: bool = False) -> None:
        super().__init__()
        self._job_run = job_run
        self._live = live
        self._timer = None

    def on_mount(self) -> None:
        if self._live and not self._job_run.lifecycle.is_ended:
            # refresh() triggers render() on the next frame — elapsed time updates each tick
            self._timer = self.set_interval(1.0, self.refresh)

    def update_run(self, job_run: JobRun) -> None:
        """Replace the snapshot and refresh. Called from InstanceApp on each event."""
        self._job_run = job_run
        if self._live and job_run.lifecycle.is_ended and self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.refresh()

    def render(self) -> Text:
        """Build the header as a Rich Text object. Textual renders it directly."""
        job_run = self._job_run
        lifecycle = job_run.lifecycle

        # Row 1: job_id @ run_id     STAGE     elapsed: HH:MM:SS
        line1 = Text()
        line1.append(job_run.job_id, style="bold")
        line1.append(" @ ", style="")
        line1.append(job_run.run_id, style="bright_black")
        line1.append("          ", style="")

        if lifecycle.is_ended and lifecycle.termination:
            stage_text = lifecycle.termination.status.name
        else:
            stage_text = lifecycle.stage.name
        line1.append(stage_text, style=_stage_rich_style(job_run))

        elapsed = lifecycle.elapsed
        elapsed_str = util.format_timedelta(elapsed, show_ms=False, null="--:--:--")
        line1.append("          ", style="")
        line1.append(f"elapsed: {elapsed_str}", style="bright_black")

        # Row 2: status line
        status_str = str(job_run.status or "")
        line2 = Text()
        if status_str:
            line2.append(status_str, style="")

        result = Text()
        result.append(line1)
        result.append("\n")
        result.append(line2)
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

    In live mode, a 1-second timer keeps elapsed times ticking.
    """

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

        new_ids = _collect_phase_ids(job_run.root_phase)
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


def _collect_phase_ids(phase: PhaseRun) -> set[str]:
    """Collect all phase_ids from a phase tree (including the root)."""
    ids = {phase.phase_id}
    for child in phase.children:
        ids.update(_collect_phase_ids(child))
    return ids


def _phase_label(phase: PhaseRun) -> Text:
    """Build a styled label: '{phase_id}  {STAGE}  {elapsed}'."""
    style = _phase_style(phase)
    lifecycle = phase.lifecycle

    label = Text()
    label.append(phase.phase_id, style=style)

    if lifecycle.is_ended and lifecycle.termination:
        stage_text = lifecycle.termination.status.name
    else:
        stage_text = lifecycle.stage.name
    label.append(f"  {stage_text}", style=style)

    elapsed_str = util.format_timedelta(lifecycle.elapsed, show_ms=False, null="")
    if elapsed_str:
        label.append(f"  {elapsed_str}", style=style)

    return label


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
