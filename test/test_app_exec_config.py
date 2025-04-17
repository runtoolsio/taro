"""
Tests :mod:`app` module
Command: exec
Description: Tests of execution related to the config file
"""
from runtools.taro.cfg import LogMode

from runtools.taro import cfg
from taro_test_util import run_app, create_test_config, remove_test_config


def test_config_file_empty():
    create_test_config(None)
    try:
        run_app('exec echo alles gute')
    finally:
        remove_test_config()


def test_config_file_loaded():
    create_test_config({"log": {"mode": True}})
    try:
        run_app('exec echo alles gute')
        assert cfg.log_enabled == LogMode.ENABLED
    finally:
        remove_test_config()
