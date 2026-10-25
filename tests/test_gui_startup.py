import time

import pytest


pytest.importorskip('_tkinter', reason='The local Python build has no Tcl/Tk support.')

from smi2ass_gui import Smi2AssApp, main


def test_gui_starts_and_registers_its_drag_target():
    app = Smi2AssApp()
    try:
        app.root.update_idletasks()
        assert app.root.winfo_exists()
        assert app.drop_zone.winfo_exists()
        assert app.drop_zone.master.winfo_children() == [
            app.drop_zone, app.overwrite_checkbox, app.language_suffix_checkbox,
        ]
    finally:
        app.root.destroy()


@pytest.mark.parametrize('language, expected_title, expected_suffix', [
    ('ko', 'SMI to ASS 변환기', '파일명에 언어 코드 표시'),
    ('en', 'SMI to ASS Converter', 'Include language code in filenames'),
])
def test_gui_startup_applies_selected_language_to_visible_copy(
        monkeypatch, language, expected_title, expected_suffix):
    import smi2ass_gui
    monkeypatch.setattr(smi2ass_gui, 'detect_ui_language', lambda: language)
    app = Smi2AssApp()
    try:
        assert app.root.title() == expected_title
        assert app.language_suffix_checkbox.cget('text') == expected_suffix
        expected_hint = '.smi 파일을 여기에 놓으세요' if language == 'ko' else 'Drop .smi files here'
        assert app._state_copy()[0] == expected_hint
    finally:
        app._dispose()


def test_smoke_test_mode_starts_and_closes_the_window():
    assert main(['--smoke-test']) == 0


def test_adding_dropped_paths_starts_conversion_automatically(tmp_path):
    source = tmp_path / 'episode.smi'
    source.write_text(
        '<SYNC Start=0><P Class=KRCC>First cue\n'
        '<SYNC Start=1000><P Class=KRCC>&nbsp;',
        encoding='utf-8',
    )
    app = Smi2AssApp()
    try:
        assert app.add_paths([source]) == 1
        assert app.busy
        deadline = time.monotonic() + 3
        while app.busy and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.01)
        assert not app.busy
        assert (tmp_path / 'episode.kor.ass').is_file()
    finally:
        app.root.destroy()


def test_language_suffix_checkbox_controls_single_language_output_name(tmp_path):
    source = tmp_path / 'episode.smi'
    source.write_text(
        '<SYNC Start=0><P Class=KRCC>First cue\n'
        '<SYNC Start=1000><P Class=KRCC>&nbsp;',
        encoding='utf-8',
    )
    app = Smi2AssApp()
    try:
        assert app.language_suffix_checkbox.instate(['selected'])
        app.include_language_suffix.set(False)
        assert app.add_paths([source]) == 1
        deadline = time.monotonic() + 3
        while app.busy and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.01)
        assert not app.busy
        assert (tmp_path / 'episode.ass').is_file()
        assert not (tmp_path / 'episode.kor.ass').exists()
    finally:
        app.root.destroy()


def test_checkbox_preferences_load_at_start_and_save_on_change(monkeypatch):
    import smi2ass_gui
    saved = []
    monkeypatch.setattr(smi2ass_gui, 'load_preferences', lambda: {
        'overwrite_existing': True,
        'include_language_suffix': False,
    })
    monkeypatch.setattr(smi2ass_gui, 'save_preferences', lambda preferences: saved.append(preferences) or True)
    app = Smi2AssApp()
    try:
        assert app.overwrite_existing.get()
        assert not app.include_language_suffix.get()
        app.overwrite_existing.set(False)
        assert saved[-1] == {
            'overwrite_existing': False,
            'include_language_suffix': False,
        }
        app.include_language_suffix.set(True)
        assert saved[-1] == {
            'overwrite_existing': False,
            'include_language_suffix': True,
        }
    finally:
        app._dispose()


@pytest.mark.parametrize('include_valid, expected', [(False, 'failed'), (True, 'partial')])
def test_actual_gui_reports_empty_and_mixed_conversion_results(tmp_path, include_valid, expected):
    source = tmp_path / 'invalid.smi'
    source.write_text('<SAMI>No cue</SAMI>', encoding='utf-8')
    paths = [source]
    if include_valid:
        valid = tmp_path / 'valid.smi'
        valid.write_text('<SYNC Start=0><P Class=KRCC>Keep<SYNC Start=1000><P Class=KRCC>&nbsp;', encoding='utf-8')
        paths.append(valid)
    app = Smi2AssApp()
    try:
        app.add_paths(paths)
        deadline = time.monotonic() + 4
        while app.busy and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.01)
        assert not app.busy
        assert app.drop_state == expected
        assert app.state_values['failed'] == 1
        assert app.state_values['outputs'] == int(include_valid)
    finally:
        app.root.destroy()


def pump_until_finished(app):
    deadline = time.monotonic() + 4
    while app.busy and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.005)
    assert not app.busy


def test_slow_scan_keeps_heartbeat_running(tmp_path, monkeypatch):
    import smi2ass_gui
    source = tmp_path / 'cue.smi'
    source.write_text('<SYNC Start=0><P Class=KRCC>Keep<SYNC Start=1000><P Class=KRCC>&nbsp;')
    original = smi2ass_gui.scan_smi_files
    def slow_scan(paths):
        time.sleep(0.25)
        return original(paths)
    monkeypatch.setattr(smi2ass_gui, 'scan_smi_files', slow_scan)
    app = Smi2AssApp()
    beats = []
    try:
        app.root.after(10, lambda: beats.append(time.monotonic()))
        started = time.monotonic()
        assert app.add_paths([tmp_path]) == 1
        assert time.monotonic() - started < 0.15
        assert app.busy
        assert app.add_paths([source]) == 0
        pump_until_finished(app)
        assert beats[0] - started < 0.2
        assert app.state_values['outputs'] == 1
    finally:
        app._dispose()


def test_outer_worker_error_finishes_busy_state(tmp_path, monkeypatch):
    import smi2ass_gui
    source = tmp_path / 'cue.smi'
    source.write_text('fixture')
    def broken(paths, overwrite, include_language_suffix=True):
        raise RuntimeError('outer conversion failure')
    monkeypatch.setattr(smi2ass_gui, 'convert_smi_files', broken)
    app = Smi2AssApp()
    try:
        # Invoke the worker synchronously so the old uncaught error is observable.
        app.busy = True
        app._convert_worker(app.events, (source,), False, 0)
        app._poll_worker()
        if app.busy:
            pump_until_finished(app)
        assert app.drop_state == 'failed'
        assert app.state_values['failed'] == 1
        assert str(app.overwrite_checkbox.cget('state')) == 'normal'
    finally:
        app._dispose()


def test_invalid_drop_list_does_not_start_conversion():
    from types import SimpleNamespace
    app = Smi2AssApp()
    try:
        assert app._on_drop(SimpleNamespace(data='{unclosed')) == 'refuse_drop'
        assert not app.busy
    finally:
        app._dispose()


def test_destroy_during_scan_does_not_retain_tk_app(tmp_path, monkeypatch):
    import gc
    import threading
    import weakref
    import smi2ass_gui
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = smi2ass_gui.scan_smi_files
    def pending_scan(paths):
        entered.set()
        assert release.wait(3)
        try:
            return original(paths)
        finally:
            finished.set()
    monkeypatch.setattr(smi2ass_gui, 'scan_smi_files', pending_scan)
    app = Smi2AssApp()
    reference = weakref.ref(app)
    try:
        app.add_paths([tmp_path])
        assert entered.wait(2)
        app.root.destroy()
        del app
        gc.collect()
        assert reference() is None
    finally:
        release.set()
    assert finished.wait(3)
