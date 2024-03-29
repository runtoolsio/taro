"""
Tests :mod:`app` module
Command: exec
"""
import os

import pytest
from runtools.taro.jobs import runner
from runtools.taro.jobs.execution import TerminationStatus
from runtools.taro.test.observer import TestPhaseObserver
from runtools.taro.test.persistence import test_sqlite_cfg_vars, create_test_sqlite, remove_test_db

from runtools.taro import util
from runtools.taro.cmd.exec import ProgramExecutionError
from taro_test_util import run_app, TestWarningObserver
from .taro_test_util import run_app_as_process_and_wait


@pytest.fixture(autouse=True)
def observer():
    observer = TestPhaseObserver()
    runner.register_state_observer(observer)
    yield observer
    runner.deregister_state_observer(observer)


def test_successful(observer: TestPhaseObserver):
    dir_name = util.unique_timestamp_hex()
    run_app('exec -mc mkdir ' + dir_name)

    assert observer.exec_state(-1) == TerminationStatus.COMPLETED
    os.rmdir(dir_name)  # Exc if not existed


def test_invalid_command(observer: TestPhaseObserver):
    with pytest.raises(ProgramExecutionError) as e:
        run_app('exec -mc non_existing_command')

    assert e.value.code == 1
    assert observer.exec_state(-1) == TerminationStatus.FAILED


def test_failed_command(observer: TestPhaseObserver):
    with pytest.raises(ProgramExecutionError) as e:
        run_app('exec -mc ls --no-such-option')

    assert e.value.code > 0
    assert observer.exec_state(-1) == TerminationStatus.FAILED


def test_invalid_command_print_to_stderr(capsys):
    with pytest.raises(ProgramExecutionError):
        run_app('exec -mc non_existing_command')

    assert 'No such file' in capsys.readouterr().err


def test_default_job_id(observer: TestPhaseObserver):
    run_app('exec -mc echo life is dukkha')
    assert observer.last_job().job_id == 'echo life is dukkha'


def test_explicit_job_id(observer: TestPhaseObserver):
    run_app('exec -mc --id this_is_an_id echo not an id')
    assert observer.last_job().job_id == 'this_is_an_id'


def test_no_overlap(observer: TestPhaseObserver):
    run_app_as_process_and_wait('exec -mc --id j1 sleep 2', wait_for=TerminationStatus.RUNNING, daemon=True)

    run_app('exec -mc --no-overlap --id j1 echo I love JAVA!')
    assert observer.last_state('j1') == TerminationStatus.SKIPPED


def test_skipped_when_dependency_not_running(observer: TestPhaseObserver):
    run_app('exec -mc --depends-on another_job --id j1 echo Something is missing..')
    assert observer.last_state('j1') == TerminationStatus.UNSATISFIED


def test_executed_when_dependency_is_running(observer: TestPhaseObserver):
    run_app_as_process_and_wait('exec -mc --id dependency sleep 2', wait_for=TerminationStatus.RUNNING, daemon=True)

    run_app('exec -mc --depends-on dependency --id j1 echo Free to go!')
    assert observer.last_state('j1') == TerminationStatus.COMPLETED


def test_job_persisted():
    remove_test_db()

    try:
        run_app(f'exec --id persisted_job {test_sqlite_cfg_vars()} echo')
        assert next(iter(create_test_sqlite().read_runs(asc=True))).job_id == 'persisted_job'
    finally:
        remove_test_db()


def test_exec_time_warning():
    observer = TestWarningObserver()
    runner.register_warning_observer(observer)
    try:
        run_app("exec -mc --warn-time=1s sleep 1.2")
    finally:
        runner.deregister_warning_observer(observer)

    assert observer.warnings['exec_time>1.0s']
