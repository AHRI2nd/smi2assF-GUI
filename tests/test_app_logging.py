import logging
import logging.handlers
import queue
from pathlib import Path

import pytest

from smi2ass_app_logging import MAX_LOG_BYTES, configure_app_logging, get_log_path


@pytest.fixture(autouse=True)
def cleanup_test_logger():
    yield
    logger = logging.getLogger('smi2assF')
    for handler in tuple(logger.handlers):
        if getattr(handler, '_smi2ass_app_handler', False):
            logger.removeHandler(handler)
            handler.close()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def test_log_path_uses_platform_user_log_directories(tmp_path):
    home = tmp_path / 'home'
    local = tmp_path / 'local'

    assert get_log_path(platform_name='darwin', home=home) == (
        home / 'Library' / 'Logs' / 'smi2assF' / 'app.log'
    )
    assert get_log_path(
        platform_name='win32', environ={'LOCALAPPDATA': str(local)}, home=home,
    ) == local / 'smi2assF' / 'Logs' / 'app.log'
    assert get_log_path(
        platform_name='linux', environ={'XDG_STATE_HOME': str(tmp_path / 'state')}, home=home,
    ) == tmp_path / 'state' / 'smi2assF' / 'app.log'
    assert get_log_path(platform_name='linux', environ={}, home=home) == (
        home / '.local' / 'state' / 'smi2assF' / 'app.log'
    )


def test_configured_logger_writes_utf8_rotating_log(tmp_path):
    path = tmp_path / 'logs' / 'app.log'
    logger = configure_app_logging(path)
    logger.error('Conversion failed: 자막 오류')

    for handler in logger.handlers:
        handler.flush()

    assert 'ERROR Conversion failed: 자막 오류' in path.read_text(encoding='utf-8')
    handlers = [handler for handler in logger.handlers if isinstance(handler, logging.handlers.RotatingFileHandler)]
    assert len(handlers) == 1
    assert handlers[0].maxBytes == 1_048_576
    assert handlers[0].backupCount == 3


def test_unavailable_log_destination_does_not_raise(tmp_path, monkeypatch):
    import smi2ass_app_logging

    def fail_handler(*args, **kwargs):
        raise OSError('log directory unavailable')

    monkeypatch.setattr(smi2ass_app_logging, '_BoundedRotatingFileHandler', fail_handler)
    logger = configure_app_logging(tmp_path / 'app.log')

    logger.error('conversion still completes')
    assert any(isinstance(handler, logging.NullHandler) for handler in logger.handlers)


def test_log_setup_failure_does_not_raise(tmp_path, monkeypatch):
    import smi2ass_app_logging

    def fail_path():
        raise RuntimeError('user home is unavailable')

    monkeypatch.setattr(smi2ass_app_logging, 'get_log_path', fail_path)
    logger = configure_app_logging()

    logger.error('conversion still completes')
    assert any(isinstance(handler, logging.NullHandler) for handler in logger.handlers)


def test_oversized_log_record_is_capped(tmp_path):
    path = tmp_path / 'logs' / 'app.log'
    logger = configure_app_logging(path)
    for _ in range(5):
        logger.error('%s', '자막오류😀' * (MAX_LOG_BYTES // 2))
    for handler in logger.handlers:
        handler.flush()

    log_files = [path, *(path.with_name(path.name + '.%d' % index) for index in range(1, 4))]
    assert all(log_file.stat().st_size <= MAX_LOG_BYTES for log_file in log_files if log_file.exists())


def test_conversion_skip_and_exception_are_logged_without_changing_summary(tmp_path):
    from smi2ass_gui_support import convert_smi_files

    path = tmp_path / 'logs' / 'app.log'
    logger = configure_app_logging(path)
    source = tmp_path / 'broken.smi'
    source.write_text('<SAMI><BODY>no cue</BODY></SAMI>', encoding='utf-8')

    summary = convert_smi_files([source])
    missing = tmp_path / 'missing.smi'
    exception_summary = convert_smi_files([missing])
    for handler in logger.handlers:
        handler.flush()

    assert (summary.total, summary.failed) == (1, 1)
    assert (exception_summary.total, exception_summary.failed) == (1, 1)
    contents = path.read_text(encoding='utf-8')
    assert str(source) in contents and 'NO_SYNC_CUES' in contents
    assert str(missing) in contents and 'FileNotFoundError' in contents


def test_conversion_without_output_or_diagnostic_logs_a_failure_reason(tmp_path):
    from smi2ass_gui_support import convert_smi_files

    path = tmp_path / 'logs' / 'app.log'
    logger = configure_app_logging(path)
    source = tmp_path / 'no-paragraph.smi'
    source.write_text('<SYNC Start=0></SYNC><SYNC Start=1000></SYNC>', encoding='utf-8')

    summary = convert_smi_files([source])
    for handler in logger.handlers:
        handler.flush()

    assert summary.failed == 1
    contents = path.read_text(encoding='utf-8')
    assert str(source) in contents and 'produced no ASS output' in contents


def test_worker_logs_each_scan_error(tmp_path, monkeypatch):
    import smi2ass_gui
    from smi2ass_gui_support import SmiScanResult

    path = tmp_path / 'logs' / 'app.log'
    logger = configure_app_logging(path)
    source = Path(tmp_path / 'locked-folder')
    error = PermissionError('access denied')
    monkeypatch.setattr(
        smi2ass_gui, 'scan_smi_files',
        lambda paths: SmiScanResult(files=(), errors=((source, error),)),
    )
    events = queue.Queue()

    smi2ass_gui.Smi2AssApp._convert_worker(events, (source,), False)
    for handler in logger.handlers:
        handler.flush()

    assert events.get_nowait() == ('empty', 1)
    contents = path.read_text(encoding='utf-8')
    assert str(source) in contents and 'PermissionError: access denied' in contents


def test_worker_exception_is_logged_and_still_completes_event(tmp_path, monkeypatch):
    import smi2ass_gui

    path = tmp_path / 'logs' / 'app.log'
    logger = configure_app_logging(path)
    source = Path(tmp_path / 'input.smi')

    def fail_scan(paths):
        raise RuntimeError('unexpected scanner failure')

    monkeypatch.setattr(smi2ass_gui, 'scan_smi_files', fail_scan)
    events = queue.Queue()

    smi2ass_gui.Smi2AssApp._convert_worker(events, (source,), False)
    for handler in logger.handlers:
        handler.flush()

    event = events.get_nowait()
    assert event[0] == 'error' and 'unexpected scanner failure' in event[-1]
    contents = path.read_text(encoding='utf-8')
    assert str(source) in contents and 'RuntimeError: unexpected scanner failure' in contents
