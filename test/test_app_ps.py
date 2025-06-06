"""
Tests :mod:`app` module
Command: ps
"""
from runtools.taro.jobs.execution import TerminationStatus

import runtools.taro.view.instance as view_inst
from runtools.taro import printer
from taro_test_util import run_app, run_app_as_process_and_wait


def test_job_running(capsys):
    run_app_as_process_and_wait('exec -mc sleep 1', wait_for=TerminationStatus.RUNNING, daemon=True)

    run_app('ps')
    output = capsys.readouterr().out

    jobs = printer.parse_table(output, view_inst.DEFAULT_COLUMNS)
    assert 'sleep 1' == jobs[0][view_inst.JOB_ID]
    assert TerminationStatus.RUNNING.name.casefold() == jobs[0][view_inst.PHASES].casefold()


def test_job_waiting(capsys):
    run_app_as_process_and_wait('exec -mc -P val sleep 1', wait_for=TerminationStatus.PENDING, daemon=True)

    run_app('ps')
    output = capsys.readouterr().out

    jobs = printer.parse_table(output, view_inst.DEFAULT_COLUMNS)
    assert 'sleep 1' == jobs[0][view_inst.JOB_ID]
    assert TerminationStatus.PENDING.name.casefold() == jobs[0][view_inst.PHASES].casefold()


def test_job_status(capsys):
    # Shell to use '&&' to combine commands
    run_app_as_process_and_wait('exec -mc --id p_test echo progress1 && sleep 1',
                                wait_for=TerminationStatus.RUNNING, daemon=True, shell=True)

    run_app('ps')
    output = capsys.readouterr().out

    jobs = printer.parse_table(output, view_inst.DEFAULT_COLUMNS)
    assert jobs[0][view_inst.STATUS] == 'progress1'


def test_job_instance_filter_false(capsys):
    run_app_as_process_and_wait('exec -mc --id f_test_no_job1 sleep 1', wait_for=TerminationStatus.RUNNING, daemon=True)

    run_app('ps f_test_no_job2')
    output = capsys.readouterr().out

    jobs = printer.parse_table(output, view_inst.DEFAULT_COLUMNS)
    assert not jobs


def test_job_instance_filter_true(capsys):
    run_app_as_process_and_wait('exec -mc --id f_test_job1 sleep 1', wait_for=TerminationStatus.RUNNING, daemon=True)

    run_app('ps f_test_job*')
    output = capsys.readouterr().out

    jobs = printer.parse_table(output, view_inst.DEFAULT_COLUMNS)
    assert len(jobs) == 1
