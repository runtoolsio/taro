from collections import defaultdict
import select
import signal
import subprocess
import sys
import textwrap
from threading import Thread
from types import SimpleNamespace

import pytest

from runtools.runcore.job import InstanceObservableNotifications, InstanceOutputEvent
from runtools.runcore.matching import MetadataCriterion
from runtools.runcore.output import OutputLine
from runtools.runcore.test.job import fake_job_run
from runtools.runcore.util import utc_now
from runtools.taro.cmd import tail


def _event(run, ordinal, message=None):
    return InstanceOutputEvent(run.metadata, OutputLine(message or str(ordinal), ordinal), utc_now())


def test_startup_output_is_queued_without_blocking_and_deduplicated(monkeypatch):
    run = fake_job_run('job', term_status=None)
    printed = []
    monkeypatch.setattr(tail, 'print_instance_header', lambda _: None)
    monkeypatch.setattr(tail, 'print_line', lambda line, *_: printed.append(line.ordinal))
    observer = tail.TailPrint(None, (MetadataCriterion.all_match(),), False, False)

    worker = Thread(target=lambda: [observer.instance_output_update(_event(run, n)) for n in (1, 2, 3)],
                    daemon=True)
    worker.start()
    worker.join(1)
    blocked = worker.is_alive()
    assert printed == []
    observer.release(run.metadata, defaultdict(int, {run.metadata: 2}))
    worker.join(1)
    assert not blocked

    observer.instance_output_update(_event(run, 3))
    observer.instance_output_update(_event(run, 4))
    assert printed == [3, 4]


@pytest.mark.parametrize('follow', [False, True])
def test_tail_subscribes_only_when_following_and_handles_replay_during_open(monkeypatch, follow):
    run = fake_job_run('job', term_status=None)
    notifications = InstanceObservableNotifications()
    printed, subscriptions, closed = [], [], []
    conn = SimpleNamespace(notifications=notifications)
    conn.get_instances = lambda _: [SimpleNamespace(
        job_id=run.job_id, run_id=run.run_id, metadata=run.metadata,
        output=SimpleNamespace(tail=lambda **_: [OutputLine('two', 2)]))]

    def open_connector():
        subscriptions.append(bool(notifications.output_notification.observers))
        for n in (1, 2, 3):
            notifications.output_notification.observer_proxy.instance_output_update(_event(run, n))

    conn.open = open_connector
    conn.close = lambda: closed.append(True)
    monkeypatch.setattr(tail.cli, 'select_env', lambda _: 'test')
    monkeypatch.setattr(tail.connector, 'connect', lambda _: conn)
    handlers = {}

    def register_handler(signum, handler):
        previous = handlers.get(signum)
        handlers[signum] = handler
        return previous

    def print_and_stop(line, *_):
        printed.append(line.ordinal)
        if follow and line.ordinal == 3:
            handlers[signal.SIGTERM](signal.SIGTERM, None)

    monkeypatch.setattr(tail.signal, 'signal', register_handler)
    monkeypatch.setattr(tail, 'print_instance_header', lambda _: None)
    monkeypatch.setattr(tail, 'print_line', print_and_stop)

    tail.tail(instance_patterns=[], env='test', lines=1, follow=follow, show_ordinal=False, verbose=False)

    assert subscriptions == [follow]
    assert printed == ([2, 3] if follow else [2])
    assert closed == [True]
    assert all(handler is None for handler in handlers.values())


@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM])
def test_follow_stays_alive_with_only_daemon_polling_threads_until_signal(signum):
    script = textwrap.dedent("""
        from types import SimpleNamespace
        from runtools.runcore.db import sqlite
        from runtools.runcore.proxy import SnapshotJobInstanceProxy
        from runtools.runcore.transport.db import PollingInstanceDirectory
        from runtools.taro.cmd import tail

        db = sqlite.create_memory('follow_wait')
        db.open()
        directory = PollingInstanceDirectory(db, lambda run: SnapshotJobInstanceProxy(run, db, db))

        def close():
            directory.close()
            db.close()
            print('CLOSED', flush=True)

        conn = SimpleNamespace(notifications=directory.notifications, open=directory.open,
                               close=close, get_instances=directory.get_instances)
        tail.cli.select_env = lambda _: 'test'
        tail.connector.connect = lambda _: conn
        original = tail.TailPrint.release

        def release(self, *args):
            original(self, *args)
            print('READY', flush=True)

        tail.TailPrint.release = release
        tail.tail(instance_patterns=[], env='test', lines=1, follow=True,
                  show_ordinal=False, verbose=False)
        print('RETURNED', flush=True)
    """)
    process = subprocess.Popen([sys.executable, '-u', '-c', script], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        assert ready, 'Follow command did not finish startup'
        assert process.stdout.readline().strip() == 'READY'
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=0.2)
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert stdout.splitlines() == ['CLOSED', 'RETURNED']
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_broken_pipe_releases_follow_wait(monkeypatch):
    run = fake_job_run('job', term_status=None)
    observer = tail.TailPrint(None, (MetadataCriterion.all_match(),), False, False)
    observer.release(run.metadata, defaultdict(int))

    def broken_pipe(*_):
        raise BrokenPipeError

    monkeypatch.setattr(tail, 'print_line', broken_pipe)
    observer.instance_output_update(_event(run, 1))

    assert observer.stopped.is_set()
    assert observer.broken_pipe
