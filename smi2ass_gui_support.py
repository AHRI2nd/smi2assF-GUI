import locale
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from smi2ass_os_language import preferred_ui_languages


SUPPORTED_SUFFIXES = {'.smi'}

UI_TEXT = {
    'ko': {
        'window_title': 'SMI to ASS 변환기',
        'drop_hint': '.smi 파일을 여기에 놓으세요',
        'drop_detail': '폴더도 넣을 수 있어요',
        'drop_ready': '놓으면 변환합니다',
        'status_scanning_title': '파일 확인 중…',
        'status_scanning_detail': '자막 파일을 찾고 있어요',
        'status_converting_title': '변환 중…',
        'status_converting_detail': '{count}개 파일을 변환하고 있어요',
        'status_done_title': '변환 완료',
        'status_failed_title': '파일을 처리하지 못했습니다',
        'status_partial_title': '일부 자막을 처리하지 못했습니다',
        'status_empty_title': '.smi 파일을 찾지 못했습니다',
        'status_scan_title': '파일을 읽지 못했습니다',
        'drop_again': '.smi 파일이나 폴더를 다시 놓으세요',
        'result_summary': '대상 {total} · ASS 생성 {outputs}\n기존 ASS 유지 {existing}\n경고 {warnings} · 오류 {failed} · 읽기 실패 {scan_errors}',
        'overwrite': '기존 ASS 파일 덮어쓰기',
        'language_suffix': '파일명에 언어 코드 표시',
        'status_busy_add': '변환이 끝날 때까지 기다려 주세요.',
        'status_no_files': '.smi 또는 .SMI 파일을 찾지 못했습니다.',
        'status_scan_errors': '{count}개 위치에서 파일을 읽지 못했습니다.',
        'status_converting': '{count}개 파일을 변환하고 있습니다…',
        'status_done': '완료: {total}개 파일 · ASS 생성 {outputs}개 · 기존 파일 유지 {existing}개 · 경고 {warnings}개 · 오류 {failed}개 · 읽기 실패 {scan_errors}개',
        'dialog_busy_title': '변환 중',
        'dialog_busy_message': '변환이 끝난 뒤 앱을 닫아 주세요.',
    },
    'en': {
        'window_title': 'SMI to ASS Converter',
        'drop_hint': 'Drop .smi files here',
        'drop_detail': 'Folders work too',
        'drop_ready': 'Drop to convert',
        'status_scanning_title': 'Checking files…',
        'status_scanning_detail': 'Looking for subtitle files',
        'status_converting_title': 'Converting…',
        'status_converting_detail': 'Processing {count} file(s)',
        'status_done_title': 'Conversion complete',
        'status_failed_title': 'Could not process files',
        'status_partial_title': 'Some captions could not be processed',
        'status_empty_title': 'No .smi files found',
        'status_scan_title': 'Could not read files',
        'drop_again': 'Drop .smi files or folders to try again',
        'result_summary': 'Files {total} · ASS {outputs}\nKept {existing}\nWarnings {warnings} · Errors {failed} · Unreadable {scan_errors}',
        'overwrite': 'Overwrite existing ASS files',
        'language_suffix': 'Include language code in filenames',
        'status_busy_add': 'Wait for the current conversion to finish.',
        'status_no_files': 'No .smi or .SMI files found.',
        'status_scan_errors': 'Could not read files from {count} location(s).',
        'status_converting': 'Converting {count} file(s)…',
        'status_done': 'Complete: {total} file(s) · created {outputs} ASS file(s) · kept {existing} existing file(s) · warnings {warnings} · errors {failed} · unreadable locations {scan_errors}',
        'dialog_busy_title': 'Conversion in progress',
        'dialog_busy_message': 'Wait for conversion to finish before closing the app.',
    },
}


def detect_ui_language(device_locale=None):
    """Use Korean for Korean device locales and English for all others."""
    candidates = [device_locale] if device_locale else []
    if not candidates:
        try:
            candidates.extend(preferred_ui_languages())
        except (OSError, AttributeError, ValueError):
            pass
        message_category = getattr(locale, 'LC_MESSAGES', None)
        if message_category is not None:
            try:
                candidates.append(locale.getlocale(message_category)[0])
            except (TypeError, ValueError):
                pass
        try:
            candidates.append(locale.getlocale()[0])
        except (TypeError, ValueError):
            pass
        candidates.extend((os.environ.get('LC_ALL'), os.environ.get('LC_MESSAGES'), os.environ.get('LANG')))

    for candidate in candidates:
        if candidate:
            language = candidate.strip().split('.', 1)[0].split('@', 1)[0]
            language = language.replace('-', '_').split('_', 1)[0].casefold()
            if language:
                return 'ko' if language in ('ko', 'korean') else 'en'
    return 'en'


def localized_text(key, language, **values):
    """Return a formatted UI message in the selected supported language."""
    messages = UI_TEXT['ko' if language == 'ko' else 'en']
    return messages[key].format(**values)


@dataclass(frozen=True)
class SmiConversionSummary:
    total: int
    outputs: int
    existing: int
    failed: int
    warnings: int = 0


def convert_smi_files(paths, overwrite=False, include_language_suffix=True):
    """Convert each dropped SMI file and collect a compact UI summary."""
    from smi2ass import convert_smi_file, has_conversion_problem

    output_claims = {}
    outputs = existing = failed = warnings = 0
    paths = tuple(paths)
    for path in paths:
        try:
            result = convert_smi_file(
                path, overwrite=overwrite, output_claims=output_claims,
                include_language_suffix=include_language_suffix,
            )
        except Exception:
            failed += 1
            continue
        outputs += len(result.outputs)
        existing += len(result.skipped_existing)
        warnings += sum(item.severity == 'warning' for item in result.diagnostics)
        if has_conversion_problem(result):
            failed += 1
    return SmiConversionSummary(
        total=len(paths), outputs=outputs, existing=existing, failed=failed, warnings=warnings,
    )


@dataclass(frozen=True)
class SmiScanResult:
    files: tuple
    errors: tuple


def scan_smi_files(paths):
    found = {}
    errors = []
    def add_candidate(candidate):
        if candidate.suffix.casefold() not in SUPPORTED_SUFFIXES:
            return
        try:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_file():
                raise OSError('Input is not a regular file')
        except (OSError, RuntimeError) as error:
            errors.append((candidate, error))
            return
        found[os.path.normcase(str(resolved))] = resolved

    for raw_path in paths:
        path = Path(raw_path)
        try:
            path = path.expanduser()
            mode = path.stat().st_mode
        except (OSError, RuntimeError) as error:
            errors.append((path, error))
            continue
        if stat.S_ISDIR(mode):
            def on_walk_error(error, root=path):
                errors.append((Path(error.filename or root), error))
            for directory, _, filenames in os.walk(path, onerror=on_walk_error):
                for filename in filenames:
                    add_candidate(Path(directory) / filename)
        elif stat.S_ISREG(mode):
            add_candidate(path)

    return SmiScanResult(
        files=tuple(sorted(found.values(), key=lambda item: str(item).casefold())),
        errors=tuple(errors),
    )


def collect_smi_files(paths):
    """Return supported subtitle files while preserving the legacy list API."""
    return list(scan_smi_files(paths).files)
