import ctypes
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('names', [('ko-KR', 'en-US'), ('en-US', 'ko-KR')])
def test_windows_native_language_buffer_preserves_preference_order(monkeypatch, names):
    from smi2ass_os_language import windows_ui_languages
    payload = '\0'.join(names) + '\0\0'
    def preferred(flags, count, buffer, size):
        assert flags == 8
        ctypes.cast(count, ctypes.POINTER(ctypes.c_uint32))[0] = len(names)
        if buffer is None:
            ctypes.cast(size, ctypes.POINTER(ctypes.c_uint32))[0] = len(payload)
        else:
            for index, char in enumerate(payload):
                buffer[index] = char
        return 1
    dll = SimpleNamespace(GetUserPreferredUILanguages=preferred)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *args, **kwargs: dll, raising=False)
    assert windows_ui_languages() == names


@pytest.mark.parametrize('language_id, expected', [
    (0x0412, ('ko',)),
    (0x0409, ('en',)),
    (0x0804, ('en',)),
])
def test_windows_query_failure_uses_actual_ui_language_fallback(monkeypatch, language_id, expected):
    from smi2ass_os_language import windows_ui_languages
    def preferred(*args):
        return 0
    def default():
        return language_id
    dll = SimpleNamespace(GetUserPreferredUILanguages=preferred, GetUserDefaultUILanguage=default)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *args, **kwargs: dll, raising=False)
    assert windows_ui_languages() == expected


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires macOS user preferences')
def test_macos_native_languages_match_os_preferences():
    import re
    import subprocess
    from smi2ass_os_language import macos_ui_languages
    result = subprocess.run(['/usr/bin/defaults', 'read', '-g', 'AppleLanguages'],
                            capture_output=True, text=True, check=True, timeout=10)
    expected = tuple(re.findall(r'"([^"]+)"', result.stdout))
    assert expected
    assert macos_ui_languages() == expected
    from smi2ass_gui_support import detect_ui_language
    first_language = expected[0].strip().replace('_', '-').split('-', 1)[0].casefold()
    assert detect_ui_language() == ('ko' if first_language in ('ko', 'korean') else 'en')


@pytest.mark.skipif(sys.platform != 'win32', reason='Requires Windows user preferences')
def test_windows_native_language_selection_matches_os_preferences():
    from smi2ass_gui_support import detect_ui_language
    from smi2ass_os_language import preferred_ui_languages
    languages = preferred_ui_languages()
    assert languages
    first_language = languages[0].strip().replace('_', '-').split('-', 1)[0].casefold()
    assert detect_ui_language() == ('ko' if first_language in ('ko', 'korean') else 'en')
