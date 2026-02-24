"""Instance detail screen — shows header with job identity, stage, elapsed, and status.

Textual quick reference for maintainers:
- App is the top-level object that owns the event loop and the terminal screen.
- App.run() takes over the terminal (alt-screen) and blocks until quit.
- Screen is a full-screen container that can be pushed/popped on App's screen stack.
- compose() declares the widget tree — called once, widgets are instantiated via `yield`.
- on_mount() / on_unmount() are lifecycle hooks fired after the widget tree is built / before teardown.
- CSS_PATH points to a Textual CSS file (subset of CSS) that controls layout and styling.
  Resolved relative to this module's directory.
- BINDINGS maps keys to action methods (action_quit is built-in).
- call_from_thread() is the thread-safe bridge: schedules a callback on Textual's event loop.
  Required because runcore notifications fire on background threads.
- query_one(WidgetType) finds a single widget by type in the tree — similar to CSS selectors.
"""

from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen

from runtools.runcore.job import JobInstance, JobRun, InstancePhaseEvent, InstanceLifecycleEvent
from runtools.taro.tui.widgets import (
    InstanceHeader, OutputPanel, PhaseDetail, PhaseSelected, PhaseTree, collect_phase_ids,
)


class InstanceScreen(Screen):
    """Textual screen for the instance detail view.

    Two modes:
    - live (instance provided): subscribes to events, header ticks elapsed every 1s.
    - historical (job_run provided): static display, no events or ticking.

    Can be used standalone via InstanceApp, or pushed from another app.
    """

    CSS_PATH = "instance.tcss"

    BINDINGS = [
        Binding("escape", "dismiss", "Back", show=True),
        Binding("q", "dismiss", "Quit", show=True),
    ]

    def __init__(self, *, instance: Optional[JobInstance] = None, job_run: Optional[JobRun] = None) -> None:
        super().__init__()
        if instance is not None:
            self._instance = instance
            self._job_run = instance.snap()
            self._live = True
        elif job_run is not None:
            self._instance = None
            self._job_run = job_run
            self._live = False
        else:
            raise ValueError("Either instance or job_run must be provided")

        self._phase_handler = None
        self._lifecycle_handler = None
        self._selected_phase_id = self._job_run.root_phase.phase_id

    def compose(self) -> ComposeResult:
        yield InstanceHeader(self._job_run, live=self._live)
        with Horizontal(id="phase-container"):
            yield PhaseTree(self._job_run, live=self._live)
            yield PhaseDetail(self._job_run, live=self._live)
        yield OutputPanel(self._instance, live=self._live)

    def on_mount(self) -> None:
        """Subscribe to runcore events after the widget tree is ready.

        Observers are called on background threads (runcore event receiver), so each handler
        uses call_from_thread() to safely schedule the update on Textual's event loop.
        """
        if self._live and self._instance is not None:
            self._phase_handler = lambda event: self.app.call_from_thread(self._on_phase_event, event)
            self._lifecycle_handler = lambda event: self.app.call_from_thread(self._on_lifecycle_event, event)
            self._instance.notifications.add_observer_phase(self._phase_handler)
            self._instance.notifications.add_observer_lifecycle(self._lifecycle_handler)

    def on_unmount(self) -> None:
        self._unsubscribe()

    def _unsubscribe(self) -> None:
        if self._instance is not None:
            if self._phase_handler is not None:
                self._instance.notifications.remove_observer_phase(self._phase_handler)
                self._phase_handler = None
            if self._lifecycle_handler is not None:
                self._instance.notifications.remove_observer_lifecycle(self._lifecycle_handler)
                self._lifecycle_handler = None

    def _on_phase_event(self, event: InstancePhaseEvent) -> None:
        self._update_run(event.job_run)

    def _on_lifecycle_event(self, event: InstanceLifecycleEvent) -> None:
        self._update_run(event.job_run)
        if event.job_run.lifecycle.is_ended:
            self._unsubscribe()

    def on_phase_selected(self, event: PhaseSelected) -> None:
        """Handle phase selection from the tree — update the detail and output panels."""
        self._selected_phase_id = event.phase_id
        self.query_one(PhaseDetail).update_phase(event.phase_id)
        self._update_output_filter()

    def _update_run(self, job_run: JobRun) -> None:
        self._job_run = job_run
        self.query_one(InstanceHeader).update_run(job_run)
        self.query_one(PhaseTree).update_run(job_run)
        self.query_one(PhaseDetail).update_run(job_run)
        self._update_output_filter()

    def _update_output_filter(self) -> None:
        """Recompute the output phase filter from the current snapshot and selected phase."""
        if self._selected_phase_id == self._job_run.root_phase.phase_id:
            self.query_one(OutputPanel).update_phase_filter(None)
        else:
            phase = self._job_run.find_phase_by_id(self._selected_phase_id)
            self.query_one(OutputPanel).update_phase_filter(collect_phase_ids(phase) if phase else None)


class InstanceApp(App):
    """Standalone Textual app for the instance detail TUI.

    Thin wrapper that pushes InstanceScreen and exits when it is dismissed.
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, *, instance: Optional[JobInstance] = None, job_run: Optional[JobRun] = None) -> None:
        super().__init__()
        self._instance = instance
        self._job_run = job_run

    def on_mount(self) -> None:
        self.push_screen(
            InstanceScreen(instance=self._instance, job_run=self._job_run),
            callback=lambda _: self.exit(),
        )
