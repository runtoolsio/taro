from typing import List, Optional

import typer
from runtools.runcore import env
from runtools.runcore.env import EnvironmentNotFoundError, DEFAULT_LOCAL_ENVIRONMENT
from runtools.runcore.paths import ConfigFileNotFoundError

app = typer.Typer(invoke_without_command=True)


def env_option() -> Optional[str]:
    return typer.Option(
        None,
        "--env", "-e",
        help="Target environment (e.g. dev, prod)"
    )


@app.callback()
def approve(
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        instance_ids: List[str] = typer.Argument(..., help="One or more instance IDs"),
        env_id: Optional[str] = env_option(),
):
    try:
        env_config, _ = env.load_env_config(env_id)
    except (ConfigFileNotFoundError, EnvironmentNotFoundError) as e:
        if env_id == DEFAULT_LOCAL_ENVIRONMENT:
            env_config, _ = env.load_env_default_config(env_id)
        else:
            raise e

# def run(args):
#     run_match = argsutil.run_criteria(args, MatchingStrategy.FN_MATCH)
#     responses, _ = runcore.approve_pending_instances(run_match, None)
#     approved = [r.instance_metadata for r in responses if r.release_result == ApprovalResult.APPROVED]
#
#     if approved:
#         print('Approved:')
#         for a in approved:
#             print(a)
