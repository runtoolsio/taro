import typer

ENV_OPTION_FIELD = typer.Option(None, "--env", "-e", help="Target environment")
INSTANCE_PATTERNS = typer.Argument(..., help="One or more instance ID (metadata) patterns", metavar="PATTERN")
INSTANCE_PATTERNS_OPTIONAL = typer.Argument(
    default=None, help="Instance ID patterns (interactive selector when omitted)", metavar="PATTERN"
)
