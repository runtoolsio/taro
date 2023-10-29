"""
Tests :mod:`app` module
Command: exec
"""

import pytest

import test_plugin
from taro_test_util import run_app, remove_test_config, create_test_config
from tarotools import taro
from tarotools.taro import TerminationStatus
from tarotools.taro.jobs import runner
from tarotools.taro.test.observer import TestPhaseObserver


@pytest.fixture(autouse=True)
def setup():
    ext_module_prefix = taro.jobs.managed.EXT_PLUGIN_MODULE_PREFIX
    taro.jobs.managed.EXT_PLUGIN_MODULE_PREFIX = 'test_'
    yield
    taro.jobs.managed.EXT_PLUGIN_MODULE_PREFIX = ext_module_prefix
    remove_test_config()


@pytest.fixture
def observer():
    observer = TestPhaseObserver()
    runner.register_state_observer(observer)
    yield observer
    runner.deregister_state_observer(observer)


def test_plugin_executed():
    create_test_config({"plugins": ["test_plugin"]})  # Use testing plugin in package 'test_plugin'
    run_app('exec --id run_with_test_plugin echo')

    assert test_plugin.TestPlugin.instance_ref().job_instances[-1].job_id == 'run_with_test_plugin'


def test_invalid_plugin_ignored(observer: TestPhaseObserver):
    test_plugin.TestPlugin.error_on_new_job_instance = BaseException('Must be captured')
    create_test_config({"plugins": ["test_plugin"]})  # Use testing plugin in package 'test_plugin'
    run_app('exec --id run_with_failing_plugin echo')

    assert observer.exec_state(-1) == TerminationStatus.COMPLETED
