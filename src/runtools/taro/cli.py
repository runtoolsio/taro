import argparse
import re
import textwrap
from argparse import RawTextHelpFormatter

import typer

from runtools.runcore.criteria import SortOption
from runtools.runcore.run import TerminationStatus
from runtools.taro import util
from runtools.taro import version
from runtools.taro.argsutil import TimestampFormat

ENV_OPTION_FIELD = typer.Option(None, "--env", "-e", help="Target environment")
INSTANCE_PATTERNS = typer.Argument(..., help="One or more instance ID (metadata) patterns", metavar="PATTERN")

ACTION_EXEC = 'exec'
ACTION_PS = 'ps'
ACTION_HISTORY = 'history'
ACTION_HISTORY_REMOVE = 'history-remove'
ACTION_STATS = 'stats'
ACTION_APPROVE = 'approve'
ACTION_LISTEN = 'listen'
ACTION_WAIT = 'wait'
ACTION_STOP = 'stop'
ACTION_TAIL = 'tail'
ACTION_OUTPUT = 'output'
ACTION_SETUP = 'setup'
ACTION_SETUP_CONFIG = 'config'
ACTION_CONFIG_PRINT = 'print'
ACTION_CONFIG_CREATE = 'create'
ACTION_HOSTINFO = 'hostinfo'


def parse_args(args):
    # TODO destination required
    parser = argparse.ArgumentParser(prog='taro', description='Manage your jobs with Taro')
    parser.add_argument("-V", "--version", action='version', help="show taro version and exit", version=version.get())
    common = argparse.ArgumentParser()  # parent parser for subparsers in case they need to share common options
    common.add_argument('--no-color', action='store_true', help='do not print colours in output')
    init_cfg_group(common)
    subparser = parser.add_subparsers(dest='action')  # command/action

    _init_exec_parser(common, subparser)
    _init_ps_parser(common, subparser)
    _init_history_parser(common, subparser)
    _init_history_remove_parser(common, subparser)
    _init_stats_parser(common, subparser)
    _init_approve_parser(common, subparser)
    _init_listen_parser(common, subparser)
    _init_wait_parser(common, subparser)
    _init_stop_parser(common, subparser)
    _init_tail_parser(common, subparser)
    _init_output_parser(common, subparser)
    _init_setup_parser(subparser)
    _init_hostinfo_parser(common, subparser)

    parsed = parser.parse_args(args)
    _check_conditions(parser, parsed)
    return parsed


def init_cfg_group(common):
    cfg_group = common.add_argument_group("Configuration options")
    cfg_group.description = """
        These options affects the way how the configuration is loaded and set.
        By default the configuration file located in one of the XDG directories is loaded and its content
        overrides values of the cfg module. Changing this default behaviour is not needed under normal usage.
        Therefore these options are usually used only during testing, experimenting and debugging.
        More details in the config doc: https://github.com/taro-suite/taro/blob/master/CONFIG.md
    """
    cfg_group.add_argument('-dc', '--def-config', action='store_true',
                           help='Use configuration stored in default config file. Run `taro config show -dc` to see '
                                'the content of the file.')
    cfg_group.add_argument('-mc', '--min-config', action='store_true',
                           help='Do not load any config file and use minimal configuration instead. Check CONFIG.md '
                                'for minimal configuration values.')
    cfg_group.add_argument('-C', '--config', type=str,
                           help='Load a config file stored in a custom location. The value of this option is the path '
                                'to the custom config file.')
    cfg_group.add_argument('--set', type=str, action='append',
                           help='Override value of a configuration attribute. The value format is: attribute=value. '
                                'See CONFIG.md for attributes details. This option can be used multiple times.')


def _init_exec_parser(common, subparsers):
    """
    Creates parser for `exec` command

    :param common: parent parser
    :param subparsers: sub-parser for exec parser to be added to
    """

    exec_parser = subparsers.add_parser(
        ACTION_EXEC, formatter_class=RawTextHelpFormatter, parents=[common], description='Execute command',
        add_help=False)

    exec_parser.description = textwrap.dedent("""
        Example of the execution: taro exec --id my_job ./my_job.sh arg1 arg2
        
        This is a main command of taro. It is used for managed execution of custom commands and applications.
        Taro provides number of features for commands executed this way. The main use case is a controlled execution of
        cron tasks. That is why command executed with taro is called a "job". Cronjob environment might not have
        taro binary executable on the path though. What usually works is to execute job explicitly using the python
        interpreter: `python3 -m taroapp exec CMD ARGS`. 
            
        It is recommended to use the `--id` option to specify the ID of the job otherwise the ID is constructed from the 
        command and its arguments. """)
    # General options
    exec_parser.add_argument('--id', type=str,
                             help='Set the job ID. It is recommended to keep this value unset only for testing and '
                                  'development purposes.')
    exec_parser.add_argument('--instance', type=str,
                             help='Set the instance ID. A unique value is generated when this option is not set. It '
                                  'is recommended to keep this value unique across all jobs.')
    exec_parser.add_argument('-b', '--bypass-output', action='store_true',
                             help='Normally the output of the executed job is captured by taro where is processed '
                                  'and resend to standard streams. When this option is used taro does not capture '
                                  'the output from the job streams. This disables output based features, but it '
                                  'can help if there is any problem with output processing.')
    exec_parser.add_argument('-o', '--no-overlap', action='store_true', default=False,
                             help='Skip if job with the same job ID is already running')
    exec_parser.add_argument('-s', '--serial', action='store_true', default=False,
                             help='The execution will wait while there is a running job with the same job ID or a job '
                                  'belonging to the same execution group (if specified). As the name implies, '
                                  'this is used to achieve serial execution of the same (or same group of) jobs, '
                                  'i.e., to prevent parallel execution. The difference between this option and '
                                  '--no-overlap is that this option will not terminate the current job when a related '
                                  'job is executing, but puts this job in a waiting state instead. This option is a '
                                  'shortcut for the --max-executions 1 option (see help for more details).')
    exec_parser.add_argument('-m', '--max-executions', type=int, default=0,
                             help='This option restricts the maximum number of parallel executions of the same job or '
                                  'jobs from the same execution group (if specified). If the current number of '
                                  'related executions prevents this job from being executed, then the job is put in a '
                                  'waiting state and resumed when the number of executions decreases. If there are '
                                  'more jobs waiting, the earlier ones have priority.')
    exec_parser.add_argument('-g', '--execution-group', type=str,
                             help='Sets the execution group for the job. The maximum number of simultaneous executions '
                                  'for all jobs belonging to the same execution group can be specified using the '
                                  '`--serial` or `max-executions` options. If an execution group is not set then '
                                  'it defaults to the job ID.')
    exec_parser.add_argument('-P', '--pending', type=str,
                             help='Specifies pending group. The job will wait before execution in pending state'
                                  'until the group receives releasing signal. See the `release` command.')
    exec_parser.add_argument('--warn-time', type=_warn_time_type, action='append', default=[],
                             help='This enables time warning which is trigger when the execution of the job exceeds '
                                  'the period specified by the value of this option. The value must be an integer '
                                  'followed by a single time unit character (one of [smhd]). For example `--warn-time '
                                  '1h` will trigger time warning when the job is executing over one hour.')
    exec_parser.add_argument('--warn-output', type=str, action='append', default=[],
                             help='This enables output warning which is triggered each time an output line of the job '
                                  'matches regex specified by the value of this option. For example `--warn-output '
                                  '"ERR*"` triggers output warning each time an output line contains a word starting '
                                  'with ERR.')
    exec_parser.add_argument('-d', '--depends-on', type=str, action='append', default=[],
                             help='The execution will be skipped if specified dependency job is not running.')
    exec_parser.add_argument('-k', '--kv-filter', action='store_true', default=False,
                             help='Key-value output parser is used for task tracking.')
    exec_parser.add_argument('--kv-alias', type=str, action='append', default=[],
                             help='Mapping of output keys to common fields.')
    exec_parser.add_argument('-p', '--grok-pattern', type=str, action='append', default=[],
                             help='Grok pattern for extracting fields from output used for task tracking.')
    exec_parser.add_argument('--dry-run', type=_str2_term_status, nargs='?', const=TerminationStatus.COMPLETED,
                             help='The job will be started without actual execution of its command. The final state '
                                  'of the job is specified by the value of this option. Default state is COMPLETED. '
                                  'This option can be used for testing some of the functionality like custom plugins.')
    exec_parser.add_argument('-t', '--timeout', type=str,
                             help='The value of this option specifies the signal number or code for stopping the job '
                                  'due to a timeout. A timeout warning is added to the job when it is stopped in this '
                                  'way.')

    exec_parser.add_argument('--param', type=lambda p: p.split('='), action='append',
                             help="Parameters are specified in `name=value` format. They represent metadata of the "
                                  "job instance and have no effect on the job execution. They are stored for the each "
                                  "execution and can be retrieved later. For example the `history` command has "
                                  "`--show-params` option to display `Parameters` column.")
    # Terms command and arguments taken from python doc and docker run help,
    # for this app (or rather exec command) these are operands (alternatively arguments)
    exec_parser.add_argument('command', type=str, metavar='COMMAND', help='Program to execute')
    exec_parser.add_argument('arg', type=str, metavar='ARG', nargs=argparse.REMAINDER, help="Program arguments")


def _init_ps_parser(common, subparsers):
    """
    Creates parsers for `ps` command

    :param common: parent parser
    :param subparsers: sub-parser for ps parser to be added to
    """

    ps_parser = subparsers.add_parser(ACTION_PS, parents=[common], description='Show running jobs', add_help=False)
    ps_parser.add_argument('instances', nargs='*', default=None, type=str, help='Instance matching pattern')
    ps_parser.add_argument('-f', '--format', type=str, choices=['table', 'json', 'jsonp'], default='table',
                           help='output format')
    ps_parser.add_argument('--show-params', action='store_true', help='')


def _init_history_parser(common, subparsers):
    """
    Creates parsers for `history` command

    :param common: parent parser
    :param subparsers: sub-parser for history parser to be added to

    TODO: Example print all jobs -> `taro hist --last | awk '{ print $1 }'`
    """

    hist_parser = subparsers.add_parser(
        ACTION_HISTORY, aliases=['hist'], parents=[common], description='Show jobs history', add_help=False)

    filter_group = hist_parser.add_argument_group('filtering', 'These options allows to filter returned jobs')
    init_filter_group(filter_group)
    filter_group.add_argument('-o', '--offset', type=int, default=-1, help='Number of history entries to skip')
    filter_group.add_argument('-n', '--lines', type=int, default=-1, help='Number of history entries to show')
    filter_group.add_argument('-L', '--last', action='store_true', help='Show last execution of each job')
    filter_group.add_argument('--slowest', action='store_true', help='Show slowest instance from each job')

    hist_parser.add_argument('-a', '--asc', '--ascending', action='store_true', help='Ascending sort')
    hist_parser.add_argument('-s', '--sort', type=str, choices=[s.name.lower() for s in SortOption],
                             default=SortOption.ENDED.name.lower(), help='Sorting criteria')
    hist_parser.add_argument('-p', '--no-pager', action='store_true', help='Do not use pager for output')
    hist_parser.add_argument('--show-params', action='store_true', help='')


def init_filter_group(filter_group):
    filter_group.add_argument('instances', nargs='*', type=str,
                              help='Identifiers of job or instance matching pattern for result filtering')
    filter_group.add_argument('-f', '--from', type=util.dt.parse, help='Show entries not older than the specified date')
    filter_group.add_argument('-t', '--to', type=util.dt.parse, help='Show entries not newer than the specified date')
    filter_group.add_argument('-T', '--today', action='store_true', help='Show only jobs created today (local)')
    filter_group.add_argument('-Y', '--yesterday', action='store_true', help='Show only jobs created yesterday (local)')
    filter_group.add_argument('-1', '--week', action='store_true', help='Show only jobs created from now 7 days back')
    filter_group.add_argument('-2', '--fortnight', action='store_true',
                              help='Show only jobs created from now 2 weeks back')
    filter_group.add_argument('-3', '--month', action='store_true', help='Show only jobs created from now 31 days back')
    filter_group.add_argument('-S', '--success', action='store_true', default=None,
                              help='Show only successfully completed jobs')
    filter_group.add_argument('-N', '--nonsuccess', action='store_true', default=None,
                              help='Show only jobs without successful completion')
    filter_group.add_argument('-F', '--fault', action='store_true', default=None, help='Show only failed jobs')
    filter_group.add_argument('-A', '--aborted', action='store_true', default=None,
                              help='Show only jobs which were aborted by user in any phase')
    filter_group.add_argument('-D', '--rejected', action='store_true', default=None,
                              help='Show only jobs rejected at some phase')
    filter_group.add_argument('-W', '--warning', action='store_true', default=None, help='Show only jobs with warnings')
    # TODO ^^


def _init_history_remove_parser(common, subparsers):
    """
    Creates parsers for `history-remove` command

    :param common: parent parser
    :param subparsers: sub-parser for history-remove parser to be added to
    """

    hist_rm_parser = subparsers.add_parser(
        ACTION_HISTORY_REMOVE, parents=[common], description="Remove job from history", add_help=False)

    hist_rm_parser.add_argument('instances', nargs='+', type=str, help='instance filter')


def _init_stats_parser(common, subparsers):
    """
    Creates parsers for `stats` command

    :param common: parent parser
    :param subparsers: sub-parser for stats parser to be added to
    """

    stats_parser = subparsers.add_parser(
        ACTION_STATS, parents=[common], description="Show jobs statistics", add_help=False)

    filter_group = stats_parser.add_argument_group('filtering', 'These options allows to filter returned jobs')
    init_filter_group(filter_group)


def _init_approve_parser(common, subparsers):
    """
    Creates parsers for `approve` command

    :param common: parent parser
    :param subparsers: sub-parser for `approve` parser to be added to
    """

    approve_parser = subparsers.add_parser(ACTION_APPROVE, parents=[common],
                                           description='Approve jobs waiting in pending state', add_help=False)
    # opt_group = approve_parser.add_mutually_exclusive_group(required=True)
    # opt_group.add_argument('-p', '--pending', type=str, default=None, metavar='GROUP',
    #                        help='Release instances from pending group')
    approve_parser.add_argument('instances', nargs='+', type=str, help='Instance matching pattern')


def _init_listen_parser(common, subparsers):
    """
    Creates parsers for `listen` command

    :param common: parent parser
    :param subparsers: sub-parser for listen parser to be added to
    """

    listen_parser = subparsers.add_parser(ACTION_LISTEN, parents=[common],
                                          description='Print job state changes', add_help=False)
    listen_parser.add_argument('instances', nargs='*', default=None, type=str, help='instance filter')
    listen_parser.add_argument('-t', '--timestamp',
                               type=TimestampFormat.from_str,
                               choices=[f for f in TimestampFormat if f is not TimestampFormat.UNKNOWN],
                               default=TimestampFormat.TIME,
                               help='Timestamp prefix format')


def _init_wait_parser(common, subparsers):
    """). The special characters used in shell-style wildcards are:
    Creates parsers for `wait` command

    :param common: parent parser
    :param subparsers: sub-parser for wait parser to be added to
    """

    wait_parser = subparsers.add_parser(ACTION_WAIT, parents=[common], description='Wait for job state', add_help=False)
    wait_parser.add_argument('instances', nargs='*', default=None, type=str, help='instance filter')
    wait_parser.add_argument('-c', '--count', type=int, default=1, help='Number of occurrences to finish the wait')
    wait_parser.add_argument('-s', '--states', type=str, metavar='STATES', nargs=argparse.REMAINDER,
                             help='States for which the command waits')
    wait_parser.add_argument('-t', '--timestamp',
                             type=TimestampFormat.from_str,
                             choices=[f for f in TimestampFormat if f is not TimestampFormat.UNKNOWN],
                             default=TimestampFormat.DATE_TIME,
                             help='Timestamp prefix format')


def _init_stop_parser(common, subparsers):
    """
    Creates parsers for `stop` command

    :param common: parent parser
    :param subparsers: sub-parser for stop parser to be added to
    """

    stop_parser = subparsers.add_parser(ACTION_STOP, parents=[common], description='Stop job', add_help=False)
    stop_parser.add_argument('--force', action='store_true', help='Force stop all')
    stop_parser.add_argument('instances', type=str, nargs='+', metavar='IDs',
                             help='Identifiers of job or instance to stop')


def _init_tail_parser(common, subparsers):
    """
    Creates parsers for `tail` command

    :param common: parent parser
    :param subparsers: sub-parser for tail parser to be added to
    """

    tail_parser = subparsers.add_parser(ACTION_TAIL, parents=[common], description='Print last output', add_help=False)
    tail_parser.add_argument('instances', nargs='*', default=None, type=str, help='instance filter')
    tail_parser.add_argument('-f', '--follow', action='store_true', help='Keep printing')


def _init_output_parser(common, subparsers):
    """
    Creates parsers for `output` command

    :param common: parent parser
    :param subparsers: sub-parser for output parser to be added to
    """

    output_parser = subparsers.add_parser(ACTION_OUTPUT, parents=[common], description='TBS', add_help=False)
    output_parser.add_argument('instances', nargs='*', default=None, type=str, help='instance filter')
    output_parser.add_argument('-P', '--no-pager', action='store_true', help='Do not use pager for output')


def _init_setup_parser(subparser):
    """
    Creates parsers for `setup` command

    :param subparser: sub-parser for setup parser to be added to
    """

    setup_parser = subparser.add_parser(ACTION_SETUP, description='Setup related actions')
    setup_parser.add_argument('--no-color', action='store_true', help='do not print colours in output')

    setup_subparser = setup_parser.add_subparsers(dest='setup_action')
    config_parser = setup_subparser.add_parser(ACTION_SETUP_CONFIG, help='Config related commands')
    config_subparser = config_parser.add_subparsers(dest='config_action')

    show_config_parser = config_subparser.add_parser(
        ACTION_CONFIG_PRINT, help='Print content of the current configuration')
    show_config_parser.add_argument('-dc', '--def-config', action='store_true', help='Show content of default config')

    create__config_parser = config_subparser.add_parser(
        ACTION_CONFIG_CREATE, help='Create configuration file', add_help=False)
    create__config_parser.add_argument("--overwrite", action="store_true", help="overwrite config file to default")


def _init_hostinfo_parser(common, subparsers):
    """
    Creates parsers for `hostinfo` command

    :param common: parent parser
    :param subparsers: sub-parser for hostinfo parser to be added to
    """

    hostinfo_parser = subparsers.add_parser(
        ACTION_HOSTINFO, parents=[common], description='Show host info', add_help=False)


# TODO Consider: change to str (like SortCriteria case) and remove this function
def _str2_term_status(v):
    try:
        return TerminationStatus[v.upper()]
    except KeyError:
        raise argparse.ArgumentTypeError('Arguments can be only valid execution states: '
                                         + ", ".join([e.name.lower() for e in TerminationStatus]))


def _warn_time_type(arg_value):
    regex = r'^\d+[smhd]$'
    pattern = re.compile(regex)
    if not pattern.match(arg_value):
        raise argparse.ArgumentTypeError(f"Execution time warning value {arg_value} does not match pattern {regex}")
    return arg_value


def _build_warn_validation_regex(*warn_regex):
    return "^(" + "|".join(warn_regex) + ")$"


def _check_conditions(parser, parsed):
    _check_config_option_conflicts(parser, parsed)

    # if parsed.action == ACTION_APPROVE:
    #     if parsed.queued and not parsed.instances:
    #         parser.error('Missing argument `instance`: Min one arg must be specified when releasing queued instances')


def _check_config_option_conflicts(parser, parsed):
    """
    Check that incompatible combinations of options were not used

    :param parser: parser
    :param parsed: parsed arguments
    """
    config_options = []
    if hasattr(parsed, 'def_config') and parsed.def_config:
        config_options.append('def_config')
    if hasattr(parsed, 'min_config') and parsed.min_config:
        config_options.append('min_config')
    if hasattr(parsed, 'config') and parsed.config:
        config_options.append('config')

    if len(config_options) > 1:
        parser.error('Conflicting config options: ' + str(config_options))
