import typer

from runtools.taro.cmd import approve

app = typer.Typer()

app.add_typer(approve.app, name="approve")
