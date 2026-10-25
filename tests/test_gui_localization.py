from smi2ass_gui_support import detect_ui_language, localized_text
import pytest


def test_detect_ui_language_uses_korean_device_locale():
    assert detect_ui_language('ko_KR.UTF-8') == 'ko'


@pytest.mark.parametrize('device_locale', [
    'en_US.UTF-8', 'en-US', 'ja_JP.UTF-8', 'ja-JP', 'zh-CN', 'fr-FR',
])
def test_detect_ui_language_uses_english_for_other_device_locales(device_locale):
    assert detect_ui_language(device_locale) == 'en'


def test_localized_text_uses_korean_or_english_copy():
    assert localized_text('drop_hint', 'ko') == '.smi 파일을 여기에 놓으세요'
    assert localized_text('drop_hint', 'en') == 'Drop .smi files here'
    assert localized_text('overwrite', 'ko') == '기존 ASS 파일 덮어쓰기'
    assert localized_text('overwrite', 'en') == 'Overwrite existing ASS files'
    assert localized_text('language_suffix', 'ko') == '파일명에 언어 코드 표시'
    assert localized_text('language_suffix', 'en') == 'Include language code in filenames'


def test_gui_result_copy_preserves_all_six_counts():
    for language in ('ko', 'en'):
        result = localized_text('result_summary', language, total=12, outputs=34,
                                existing=56, warnings=67, failed=78, scan_errors=90)
        for count in ('12', '34', '56', '67', '78', '90'):
            assert count in result
        assert len(result.splitlines()) == 3


@pytest.mark.parametrize('name', ['ko-KR', 'ko_KR', 'Korean_Korea.949', 'KOREAN', ' ko-KR '])
def test_korean_locale_aliases_are_normalized(name):
    assert detect_ui_language(name) == 'ko'


@pytest.mark.parametrize('languages, process_locale, expected', [
    (('ko-KR', 'en-US'), 'C', 'ko'),
    (('en-US', 'ko-KR'), 'ko_KR', 'en'),
    (('ja-JP', 'ko-KR'), 'ko_KR', 'en'),
    (('', 'ko-KR'), 'C', 'ko'),
    ((), 'Korean_Korea', 'ko'),
])
def test_os_ui_language_precedes_region_and_process_locale(monkeypatch, languages, process_locale, expected):
    import smi2ass_gui_support as support
    monkeypatch.setattr(support, 'preferred_ui_languages', lambda: languages, raising=False)
    monkeypatch.setattr(support.locale, 'getlocale', lambda *args: (process_locale, None))
    assert detect_ui_language() == expected


@pytest.mark.parametrize('process_locale, expected', [
    ('ko_KR', 'ko'),
    ('fr_FR', 'en'),
])
def test_os_query_failure_falls_back_without_preventing_startup(monkeypatch, process_locale, expected):
    import smi2ass_gui_support as support
    def unavailable():
        raise OSError('native API unavailable')
    monkeypatch.setattr(support, 'preferred_ui_languages', unavailable, raising=False)
    monkeypatch.setattr(support.locale, 'getlocale', lambda *args: (process_locale, None))
    assert detect_ui_language() == expected


def test_empty_locales_use_language_environment_fallback(monkeypatch):
    import smi2ass_gui_support as support
    monkeypatch.setattr(support, 'preferred_ui_languages', lambda: (), raising=False)
    monkeypatch.setattr(support.locale, 'getlocale', lambda *args: (None, None))
    monkeypatch.delenv('LC_ALL', raising=False)
    monkeypatch.delenv('LC_MESSAGES', raising=False)
    monkeypatch.setenv('LANG', 'ko_KR.UTF-8')
    assert detect_ui_language() == 'ko'
