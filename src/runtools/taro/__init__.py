"""
This is a command line interface for the `runcore` library.
"""

import os

import sys

import runtools.runcore.util.files
from runtools import runcore
from runtools.runcore import util, paths
from runtools.runcore.err import RuntoolsException
from runtools.runcore.paths import ConfigFileNotFoundError
from runtools.runcore.util import update_nested_dict
from runtools.taro import cmd, cli, config
from runtools.taro.cli import ACTION_SETUP
from runtools.taro.printer import print_styled
from runtools.taro.theme import Theme

__version__ = "0.1.0"

CONFIG_FILE = 'taro.toml'


def main_cli():
    main(None)


def main(args_raw):
    """Taro CLI app main function.

    Note: Configuration is set up before execution of all commands although not all commands require it.
          This practice increases safety (in regards with future extensions) and consistency.
          Performance impact is expected to be negligible.

    :param args_raw: CLI arguments
    """
    try:
        run_app(args_raw)
    except RuntoolsException as e:
        print_styled((Theme.error, "User error: "), ('', str(e)), file=sys.stderr)
        exit(1)


def run_app(args_raw):
    args = cli.parse_args(args_raw)

    if args.no_color or 'NO_COLOR' in os.environ or 'TARO_NO_COLOR' in os.environ:
        os.environ['PROMPT_TOOLKIT_COLOR_DEPTH'] = 'DEPTH_1_BIT'

    if args.action == ACTION_SETUP:
        run_setup(args)
    else:
        configure_runcore(args)
        run_command(args)


def run_setup(args):
    if args.setup_action == cli.ACTION_SETUP_CONFIG:
        run_setup_config(args)


def run_setup_config(args):
    if args.config_action == cli.ACTION_CONFIG_PRINT:
        util.print_file(resolve_config_path(args))
    elif args.config_action == cli.ACTION_CONFIG_CREATE:
        created_file = runtools.runcore.util.files.copy_config_to_search_path(config.__package__, CONFIG_FILE, args.overwrite)
        print_styled((Theme.success, "Created "), ('', str(created_file)))


def resolve_config_path(args):
    """
    Resolve path to the configuration file based on provided CLI arguments.

    Args:
        args (Namespace): Parsed CLI arguments

    Returns:
        str: The configuration file path.
    """
    if getattr(args, 'config', None):
        return util.expand_user(args.config)

    if getattr(args, 'def_config', False):
        return default_config_path()

    try:
        return paths.lookup_file_in_config_path(CONFIG_FILE)
    except ConfigFileNotFoundError:
        # Use default package config if none config is found in config search path
        return default_config_path()


def default_config_path():
    return paths.package_config_path(config.__package__, CONFIG_FILE)


def configure_runcore(args):
    """Configure `runcore` facade by resolved configuration

    Args:
        args (Namespace): Parsed CLI arguments
    """
    try:
        configuration = util.read_toml_file(resolve_config_path(args))
    except FileNotFoundError:
        raise ConfigFileNotFoundError(args.config)  # Could happen only when the path is explicitly specified

    update_nested_dict(configuration, util.split_params(args.set))  # Override config by `set` args
    runcore.configure(**configuration)


def run_command(args_ns):
    cmd.run(args_ns)
