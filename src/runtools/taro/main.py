import typer
from rich.console import Console
from rich.text import Text

from runtools.runcore.err import RuntoolsException
from runtools.taro.cmd import approve, history, ps, stats, stop, tail, wait

console = Console(stderr=True)

app = typer.Typer()

app.add_typer(approve.app, name="approve")
app.add_typer(history.hist_app, name="h")  # Alias for history
app.add_typer(history.app, name="history")
app.add_typer(ps.app, name="ps")
app.add_typer(stats.app, name="stats")
app.add_typer(stop.app, name="stop")
app.add_typer(tail.app, name="tail")
app.add_typer(wait.app, name="wait")


def run():
    try:
        app()
    except RuntoolsException as e:
        console.print(Text().append("User error: ", style="bold red").append(str(e)))
        exit(1)
