"""Instance detail screen — shows header with job identity, stage, elapsed, and status.

Textual quick reference for maintainers:
- App is the top-level object that owns the event loop and the terminal screen.
- App.run() takes over the terminal (alt-screen) and blocks until quit.
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

from runtools.runcore.job import JobInstance, JobRun, InstancePhaseEvent, InstanceLifecycleEvent
from runtools.taro.tui.widgets import InstanceHeader
from textual.app import App, ComposeResult
from textual.binding import Binding


class InstanceApp(App):
    """Textual app for the instance detail TUI.

    Two modes:
    - live (instance provided): subscribes to events, header ticks elapsed every 1s.
    - historical (job_run provided): static display, no events or ticking.
    """

    CSS_PATH = "instance.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
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

    def compose(self) -> ComposeResult:
        yield InstanceHeader(self._job_run, live=self._live)

    def on_mount(self) -> None:
        """Subscribe to runcore events after the widget tree is ready.

        Observers are called on background threads (runcore event receiver), so each handler
        uses call_from_thread() to safely schedule the update on Textual's event loop.
        """
        if self._live and self._instance is not None:
            self._phase_handler = lambda event: self.call_from_thread(self._on_phase_event, event)
            self._lifecycle_handler = lambda event: self.call_from_thread(self._on_lifecycle_event, event)
            self._instance.notifications.add_observer_phase(self._phase_handler)
            self._instance.notifications.add_observer_lifecycle(self._lifecycle_handler)

    def on_unmount(self) -> None:
        self._unsubscribe()

    def _unsubscribe(self) -> None:
        if self._instance is not None:
            self._instance.notifications.remove_observer_phase(self._phase_handler)
            self._phase_handler = None

            self._instance.notifications.remove_observer_lifecycle(self._lifecycle_handler)
            self._lifecycle_handler = None

    def _on_phase_event(self, event: InstancePhaseEvent) -> None:
        self._update_run(event.job_run)

    def _on_lifecycle_event(self, event: InstanceLifecycleEvent) -> None:
        self._update_run(event.job_run)
        if event.job_run.lifecycle.is_ended:
            self._unsubscribe()

    def _update_run(self, job_run: JobRun) -> None:
        header = self.query_one(InstanceHeader)
        header.update_run(job_run)
