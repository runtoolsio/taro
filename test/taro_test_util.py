from multiprocessing import Queue
from multiprocessing.context import Process
from pathlib import Path
from typing import Dict, Tuple

# TODO Remove
import prompt_toolkit
import tomli_w
from prompt_toolkit.output import DummyOutput
from tarotools.cli import main

from tarotools.taro import paths, JobInstanceDetail, InstanceWarningObserver, cfg, PhaseTransitionObserver, program
from tarotools.taro.jobs import runner
from tarotools.taro.jobs.instance import WarnEventCtx


# TODO consider to move to taro.test to be accessible from dependencies

def reset_config():
    # TODO Automate
    cfg.log_mode = cfg.DEF_LOG
    cfg.log_stdout_level = cfg.DEF_LOG_STDOUT_LEVEL
    cfg.log_file_level = cfg.DEF_LOG_FILE_LEVEL
    cfg.log_file_path = cfg.DEF_LOG_FILE_PATH

    cfg.persistence_enabled = cfg.DEF_PERSISTENCE_ENABLED
    cfg.persistence_type = cfg.DEF_PERSISTENCE_TYPE
    cfg.persistence_database = cfg.DEF_PERSISTENCE_DATABASE

    cfg.plugins_load = cfg.DEF_PLUGINS_LOAD


def run_app_as_process(command, daemon=False, shell=False, state_queue=None) -> Process:
    p = Process(target=run_app, args=(command, shell, state_queue), daemon=daemon)
    p.start()
    return p


def run_app(command, shell=False, state_queue=None):
    """
    Run command
    :param command: command to run
    :param shell: use shell for executing command
    :param state_queue: queue for putting new execution states of running jobs
    """
    program.USE_SHELL = shell
    # Prevent UnsupportedOperation error: https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1107
    prompt_toolkit.output.defaults.create_output = NoFormattingOutput
    observer = None
    if state_queue:
        observer = PutPhaseToQueueObserver(state_queue)
        runner.register_transition_callback(observer)

    try:
        main(command.split())
    finally:
        prompt_toolkit.output.defaults.create_output = None
        program.USE_SHELL = False
        if observer:
            runner.deregister_transition_callback(observer)


def run_app_as_process_and_wait(command, *, wait_for, timeout=2, daemon=False, shell=False) -> Process:
    """
    Execute the command and wait for the job to reach the specified state.

    :param command: command to execute
    :param wait_for: state for which the execution wait
    :param timeout: waiting timeout
    :param daemon: whether the command as executed as a daemon process
    :param shell: execute the command using shell
    :return: the app as a process
    """

    waiter = StateWaiter()
    p = run_app_as_process(command, daemon, shell, waiter.state_queue)
    waiter.wait_for_state(wait_for, timeout)
    return p


def create_test_config(config):
    create_custom_test_config(paths.CONFIG_FILE, config)


def create_custom_test_config(filename, config):
    path = _custom_test_config_path(filename)
    with open(path, 'wb') as outfile:
        tomli_w.dump(config, outfile)
    return path


def remove_test_config():
    remove_custom_test_config(paths.CONFIG_FILE)


def remove_custom_test_config(filename):
    config = _custom_test_config_path(filename)
    if config.exists():
        config.unlink()


def _test_config_path() -> Path:
    return _custom_test_config_path(paths.CONFIG_FILE)


def _custom_test_config_path(filename) -> Path:
    return Path.cwd() / filename


class NoFormattingOutput(DummyOutput):
    def write(self, data: str) -> None:
        print(data, end='')

    def write_raw(self, data: str) -> None:
        print(data)

    def fileno(self) -> int:
        raise NotImplementedError()


class StateWaiter:
    """
    This class is used for waiting for execution states of job executed in different process.

    See :class:`PutStateToQueueObserver`

    Attributes:
        state_queue The process must put execution states into this queue
    """

    def __init__(self):
        self.state_queue = Queue()

    def wait_for_state(self, state, timeout=1):
        while True:
            if state == self.state_queue.get(timeout=timeout):
                return


class PutPhaseToQueueObserver(PhaseTransitionObserver):
    """
    This observer puts execution states into the provided queue. With multiprocessing queue this can be used for sending
    execution states into the parent process.

    See :class:`StateWaiter`
    """

    def __init__(self, queue):
        self.queue = queue

    def new_phase(self, job_inst: JobInstanceDetail, previous_phase, new_phase, changed):
        self.queue.put_nowait(new_phase)


class TestWarningObserver(InstanceWarningObserver):

    def __init__(self):
        self.warnings: Dict[str, Tuple[JobInstanceDetail, WarnEventCtx]] = {}

    def new_instance_warning(self, job_inst: JobInstanceDetail, warning_ctx):
        self.warnings[warning_ctx.warning.name] = (job_inst, warning_ctx)
