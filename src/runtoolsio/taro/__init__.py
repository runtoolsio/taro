"""
This is a command line interface for the `runcore` library.
"""

import os

import sys

from runtoolsio import runcore
from runtoolsio.runcore import util, paths
from runtoolsio.runcore.common import RuntoolsException, ConfigFileNotFoundError
from runtoolsio.runcore.util import update_nested_dict
from runtoolsio.taro import cmd, cli, config
from runtoolsio.taro.cli import ACTION_SETUP
from runtoolsio.taro.printer import print_styled
from runtoolsio.taro.theme import Theme

__version__ = "0.1.0"

CONFIG_FILE = 'taro.toml'


def main_cli():
    main(None)


def main(args):
    """Taro CLI app main function.

    Note: Configuration is set up before execution of all commands although not all commands require it.
          This practice increases safety (in regards with future extensions) and consistency.
          Performance impact is expected to be negligible.

    :param args: CLI arguments
    """
    try:
        run_app(args)
    except (ConfigFileNotFoundError, RuntoolsException) as e:
        print_styled((Theme.warning, "User error: "), ('', str(e)), file=sys.stderr)
        exit(1)


def run_app(args):
    args_parsed = cli.parse_args(args)

    if args_parsed.no_color or 'NO_COLOR' in os.environ or 'TARO_NO_COLOR' in os.environ:
        os.environ['PROMPT_TOOLKIT_COLOR_DEPTH'] = 'DEPTH_1_BIT'

    if args_parsed.action == ACTION_SETUP:
        run_setup(args_parsed)
    else:
        configure_runcore(args_parsed)
        run_command(args_parsed)


def run_setup(args):
    if args.setup_action == cli.ACTION_SETUP_CONFIG:
        run_setup_config(args)


def run_setup_config(args):
    if args.config_action == cli.ACTION_CONFIG_PRINT:
        util.print_file(paths.lookup_config_file())
    elif args.config_action == cli.ACTION_CONFIG_CREATE:
        created_file = paths.copy_default_config_to_search_path(CONFIG_FILE, args.overwrite)
        print_styled((Theme.success, "Created "), ('', str(created_file)))


def configure_runcore(args):
    """Initialize taro according to provided CLI arguments

    :param args: CLI arguments
    """
    if getattr(args, 'config', None):
        config_path = util.expand_user(args.config)
        try:
            configuration = util.read_toml_file(config_path)
        except FileNotFoundError:
            raise ConfigFileNotFoundError(args.config)
    else:
        try:
            config_path = paths.lookup_file_in_config_path(CONFIG_FILE)
            configuration = util.read_toml_file(config_path)
        except ConfigFileNotFoundError:
            # Use default package config if none config is found in config search path
            configuration = util.read_toml_file(paths.package_config_path(config.__package__, CONFIG_FILE))

    update_nested_dict(configuration, util.split_params(args.set))  # Override config by `set` args
    runcore.configure(**configuration)


def run_command(args_ns):
    cmd.run(args_ns)
