import typer
from rich.console import Console
from rich.text import Text

from runtools.runcore.err import RuntoolsException
from runtools.taro.cmd import approve, dash, env, history, listen, live, of, ps, resume, stats, stop, tail, wait

console = Console(stderr=True)

app = typer.Typer()

app.add_typer(approve.app, name="approve")
app.add_typer(dash.app, name="dash")
app.add_typer(env.app, name="env")
app.add_typer(history.app, name="history")
app.add_typer(listen.app, name="listen")
app.add_typer(live.app, name="live")
app.add_typer(of.app, name="of")
app.add_typer(ps.app, name="ps")
app.add_typer(resume.app, name="resume")
app.add_typer(stats.app, name="stats")
app.add_typer(stop.app, name="stop")
app.add_typer(tail.app, name="tail")
app.add_typer(wait.app, name="wait")

# Single-char aliases for frequently used commands
app.add_typer(dash.app, name="d", hidden=True)
app.add_typer(history.app, name="h", hidden=True)
app.add_typer(live.app, name="l", hidden=True)
app.add_typer(stats.app, name="s", hidden=True)
app.add_typer(tail.app, name="t", hidden=True)
app.add_typer(stop.app, name="x", hidden=True)


def run():
    try:
        app()
    except RuntoolsException as e:
        console.print(Text().append("User error: ", style="bold red").append(str(e)))
        exit(1)
