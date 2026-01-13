import typer

ENV_OPTION_FIELD = typer.Option(None, "--env", "-e", help="Target environment")
INSTANCE_PATTERNS = typer.Argument(..., help="One or more instance ID (metadata) patterns", metavar="PATTERN")
