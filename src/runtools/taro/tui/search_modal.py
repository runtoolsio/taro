"""Minimal search prompt — used by OutputPanel for vim-style `/` search."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input


class SearchModal(ModalScreen[str]):
    """Prompt the user for a search query. Returns the entered string, or '' on cancel."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
        background: $background 60%;
    }
    SearchModal > Vertical {
        width: 60;
        height: auto;
        padding: 0 1;
        border: round $accent;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, initial: str = "") -> None:
        super().__init__()
        self._initial = initial

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(value=self._initial, placeholder="/ search")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss("")
