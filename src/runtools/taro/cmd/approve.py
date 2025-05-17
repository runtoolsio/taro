from typing import List, Optional, Tuple

import typer
from runtools.runcore import env
from runtools.runcore.env import EnvironmentNotFoundError, DEFAULT_LOCAL_ENVIRONMENT
from runtools.runcore.paths import ConfigFileNotFoundError

app = typer.Typer(invoke_without_command=True)


def env_option():
    return typer.Option((), "--env", "-e", help="Target environment")


def resolve_env_configs(*env_ids):
    """
    Load environment configurations with fallback for missing local environment.

    Behavior:
    1. No environments specified:
        - Load all available environments.
        - Add default `local` environment if it is not found in the loaded configs.
    2. Environments specified and includes `local`:
        - Load specified environments.
        - Add default `local` environment if it is not found in the loaded configs.
    3. Environments specified and does NOT include `local`:
        - Load only the specified environments.
    """
    env_ids_set = set(env_ids)
    if DEFAULT_LOCAL_ENVIRONMENT in env_ids_set and len(env_ids_set) > 1:
        explicit_local = True
        env_ids_set.remove(DEFAULT_LOCAL_ENVIRONMENT)
    else:
        explicit_local = False

    try:
        env_configs = env.get_env_configs(*env_ids_set)
    except (ConfigFileNotFoundError, EnvironmentNotFoundError) as e:
        if env_ids_set and env_ids_set != {DEFAULT_LOCAL_ENVIRONMENT}:
            raise e
        return {DEFAULT_LOCAL_ENVIRONMENT: env.get_default_config(DEFAULT_LOCAL_ENVIRONMENT)}

    if (not env_ids_set or explicit_local) and DEFAULT_LOCAL_ENVIRONMENT not in env_configs:
        env_configs[DEFAULT_LOCAL_ENVIRONMENT] = env.get_default_config(DEFAULT_LOCAL_ENVIRONMENT)

    return env_configs


@app.callback()
def approve(
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        instance_ids: List[str] = typer.Argument(..., help="One or more instance IDs"),
        env_ids: List[str] = env_option(),
):
    env_configs = resolve_env_configs(*env_ids)

    print(env_configs)

# def run(args):
#     run_match = argsutil.run_criteria(args, MatchingStrategy.FN_MATCH)
#     responses, _ = runcore.approve_pending_instances(run_match, None)
#     approved = [r.instance_metadata for r in responses if r.release_result == ApprovalResult.APPROVED]
#
#     if approved:
#         print('Approved:')
#         for a in approved:
#             print(a)
