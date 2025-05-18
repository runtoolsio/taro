from typing import List, Dict

import typer

from runtools.runcore import env, connector
from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.env import EnvironmentNotFoundError, DEFAULT_LOCAL_ENVIRONMENT, EnvironmentConfigUnion
from runtools.runcore.paths import ConfigFileNotFoundError

app = typer.Typer(invoke_without_command=True)


def env_option():
    return typer.Option((), "--env", "-e", help="Target environment")


def resolve_env_configs(*env_ids) -> Dict[str, EnvironmentConfigUnion]:
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
        mixed_explicit_local = True
        env_ids_set.remove(DEFAULT_LOCAL_ENVIRONMENT)
    else:
        mixed_explicit_local = False

    try:
        env_configs = env.get_env_configs(*env_ids_set)
    except (ConfigFileNotFoundError, EnvironmentNotFoundError) as e:
        if env_ids_set and env_ids_set != {DEFAULT_LOCAL_ENVIRONMENT}:
            raise e
        return {DEFAULT_LOCAL_ENVIRONMENT: env.get_default_config(DEFAULT_LOCAL_ENVIRONMENT)}

    if (not env_ids_set or mixed_explicit_local) and DEFAULT_LOCAL_ENVIRONMENT not in env_configs:
        env_configs[DEFAULT_LOCAL_ENVIRONMENT] = env.get_default_config(DEFAULT_LOCAL_ENVIRONMENT)

    return env_configs


@app.callback()
def approve(
        instance_patterns: List[str] = typer.Argument(..., help="One or more instance ID (metadata) patterns",
                                                      metavar="PATTERN"),
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        env_ids: List[str] = env_option(),
):
    for env_config in resolve_env_configs(*env_ids).values():
        with connector.create(env_config) as conn:
            instances = conn.get_instances(JobRunCriteria.parse_all(instance_patterns))
            for instance in instances:
                pc = instance.find_phase_control_by_id(phase)
                if not pc:
                    continue
                pc.approve()
