import typer
from rich.console import Console
from rich.text import Text
from runtools.runcore.err import RuntoolsException

from runtools.taro.cmd import approve, history

console = Console(stderr=True)

app = typer.Typer()

app.add_typer(approve.app, name="approve")
app.add_typer(history.app, name="history")
app.add_typer(history.hist_app, name="hist")  # Alias for history


def run():
    try:
        app()
    except RuntoolsException as e:
        console.print(Text().append("User error: ", style="bold red").append(str(e)))
        exit(1)
