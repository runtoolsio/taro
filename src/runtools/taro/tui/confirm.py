"""Lightweight confirmation modal for destructive actions."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal asking to confirm deletion of a run. Returns True on confirm, False on cancel."""

    DEFAULT_CSS = """
    ConfirmDeleteScreen {
        align: center middle;
        background: $background 60%;
    }
    ConfirmDeleteScreen > Vertical {
        max-width: 60;
        height: auto;
        padding: 1 3;
        border: round $error;
        background: $surface;
    }
    ConfirmDeleteScreen > Vertical > Label {
        width: auto;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("y,enter", "confirm", "Yes", show=True),
        Binding("n,escape", "cancel", "No", show=True),
    ]

    def __init__(self, instance_id) -> None:
        super().__init__()
        self._instance_id = instance_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Delete [bold]{self._instance_id}[/bold]?")
            yield Label("[dim]y/Enter = confirm · n/Esc = cancel[/]")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
