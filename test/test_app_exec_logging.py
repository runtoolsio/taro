"""
Tests :mod:`app` module
Command: exec
Description: Test that logging is configured according to configuration file and CLI options overrides
"""
import logging
from pathlib import Path

import pytest

from runtoolsio.taro import log
from taro_test_util import run_app, create_test_config, remove_test_config


@pytest.fixture(autouse=True)
def remove_config_if_created():
    yield
    remove_test_config()


def test_logging_disabled_by_default():
    create_test_config(dict())
    run_app('exec echo')
    assert log.is_disabled()


def test_logging_enabled_in_config():
    create_test_config({"log": {"mode": True}})
    run_app('exec echo')
    assert not log.is_disabled()


def test_logging_disabled_in_config():
    create_test_config({"log": {"mode": False}})
    run_app('exec echo')
    assert log.is_disabled()


def test_logging_enabled_cli_override():
    create_test_config({"log": {"mode": False}})
    run_app('exec --set log_mode=on echo')
    assert not log.is_disabled()


def test_logging_disabled():
    run_app('exec -mc --set log_mode=off echo')
    assert log.is_disabled()


def test_logging_stdout_level_in_config():
    create_test_config({"log": {"mode": True, "stdout": {"level": "error"}}})
    run_app('exec echo')
    assert logging.ERROR == log.get_console_level()


def test_logging_stdout_level_cli_override():
    create_test_config({"log": {"mode": True, "stdout": {"level": "error"}}})
    run_app('exec --set log_stdout_level=warn echo')
    assert logging.WARN == log.get_console_level()


def test_logging_file_level_in_config():
    create_test_config({"log": {"mode": True, "file": {"level": "error"}}})
    run_app('exec echo')
    assert logging.ERROR == log.get_file_level()


def test_logging_file_level_cli_override():
    create_test_config({"log": {"mode": True, "file": {"level": "error"}}})
    run_app('exec --set log_file_level=warn echo')
    assert logging.WARN == log.get_file_level()


def test_logging_file_path_in_config():
    create_test_config({"log": {"mode": True, "file": {"level": "error", "path": "to_liberation.log"}}})
    try:
        run_app('exec echo')
        assert log.get_file_path().endswith('to_liberation.log')
    finally:
        log_file = Path('to_liberation.log')
        if log_file.exists():
            log_file.unlink()


def test_logging_file_path_cli_override():
    create_test_config({"log": {"mode": True, "file": {"level": "error", "path": "to_liberation.log"}}})
    try:
        run_app('exec --set log_file_path=to_nowhere.log echo')
        assert log.get_file_path().endswith('to_nowhere.log')
    finally:
        log_file = Path('to_nowhere.log')
        if log_file.exists():
            log_file.unlink()
