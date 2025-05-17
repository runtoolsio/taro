import typer
from rich.console import Console
from rich.text import Text
from runtools.runcore.err import RuntoolsException

from runtools.taro.cmd import approve

console = Console(stderr=True)

app = typer.Typer()

app.add_typer(approve.app, name="approve")


def run():
    try:
        app()
    except RuntoolsException as e:
        console.print(Text().append("User error: ", style="bold red").append(str(e)))
        exit(1)
