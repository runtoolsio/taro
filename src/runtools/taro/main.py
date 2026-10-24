from typing import Optional

import typer
from rich.console import Console
from rich.text import Text

from runtools.runcore.err import RuntoolsException
from runtools.taro import __version__
from runtools.taro.cmd import approve, dash, env, history, inspect, jobs, listen, live, output, ps, resume, stop, tail, wait

console = Console(stderr=True)


def version_callback(value: bool):
    if value:
        print(f"taro {__version__}")
        raise typer.Exit()


app = typer.Typer()


@app.callback()
def main(version: Optional[bool] = typer.Option(None, "--version", "-V", "-v", callback=version_callback, is_eager=True,
                                                 help="Show version and exit.")):
    pass

def _add_command(command_app: typer.Typer, name: str, *, hidden: bool = False):
    """Register a callback-style command — a Click group without subcommands.

    Click groups stop option parsing at the first positional argument, so ``taro stop job@r1 -f -e prod``
    would take ``-f -e prod`` as patterns; these commands have no subcommands to protect, so re-enable it.
    """
    app.add_typer(command_app, name=name, hidden=hidden, context_settings={"allow_interspersed_args": True})


_add_command(approve.app, "approve")
_add_command(dash.app, "dash")
app.add_typer(env.app, name="env")  # A real group: interspersed options would swallow its subcommands' options
_add_command(history.app, "history")
_add_command(jobs.app, "jobs")
_add_command(inspect.app, "inspect")
_add_command(listen.app, "listen")
_add_command(live.app, "live")
_add_command(output.app, "output")
_add_command(ps.app, "ps")
_add_command(resume.app, "resume")
_add_command(stop.app, "stop")
_add_command(tail.app, "tail")
_add_command(wait.app, "wait")

# Single-char aliases for frequently used commands
_add_command(dash.app, "d", hidden=True)
_add_command(history.app, "h", hidden=True)
_add_command(jobs.app, "j", hidden=True)
_add_command(live.app, "l", hidden=True)
_add_command(tail.app, "t", hidden=True)
_add_command(output.app, "o", hidden=True)
_add_command(stop.app, "x", hidden=True)

def run():
    try:
        app()
    except RuntoolsException as e:
        console.print(Text().append("User error: ", style="bold red").append(str(e)))
        exit(1)
