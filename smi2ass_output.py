"""Publish complete ASS files without exposing partial writes."""
import os
import secrets
import stat
from pathlib import Path
import tempfile


class UnsafeOutputPath(OSError):
    """An output entry is not an ordinary file."""


def validate_output(path: Path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode) or path.is_symlink() or path.is_junction():
        raise UnsafeOutputPath('Unsafe output entry: %s' % path)
    return True


def _get_creation_mode(directory: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, 'O_BINARY', 0)
    for _ in range(100):
        probe = directory / ('.smi2ass-mode-%s.tmp' % secrets.token_hex(8))
        try:
            descriptor = os.open(probe, flags, 0o666)
        except FileExistsError:
            continue
        try:
            return stat.S_IMODE(os.fstat(descriptor).st_mode)
        finally:
            try:
                os.close(descriptor)
            finally:
                probe.unlink(missing_ok=True)
    raise FileExistsError('Could not allocate a unique permission probe')


def _create_staging_file(path: Path):
    descriptor, name = tempfile.mkstemp(prefix='.smi2ass-', suffix='.tmp', dir=path.parent)
    return descriptor, Path(name)


def publish_ass(path: Path, contents: bytes, overwrite: bool) -> str:
    """Stage beside the destination, then atomically publish complete bytes."""
    exists = validate_output(path)
    if exists and not overwrite:
        return 'existing'
    existing_mode = None
    creation_mode = None
    if exists and overwrite and os.name != 'nt':
        existing_mode = stat.S_IMODE(path.lstat().st_mode)
    elif not exists and os.name != 'nt':
        creation_mode = _get_creation_mode(path.parent)
    fd, temporary = _create_staging_file(path)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        final_mode = existing_mode if existing_mode is not None else creation_mode
        if final_mode is not None:
            os.chmod(temporary, final_mode)
        validate_output(path)
        if overwrite:
            os.replace(temporary, path)
        else:
            try:
                if os.name == 'nt':
                    # Windows rename refuses an existing destination.
                    os.rename(temporary, path)
                else:
                    # Hard-link publication is atomic and never replaces an entry.
                    os.link(temporary, path)
            except FileExistsError:
                validate_output(path)
                return 'existing'
        return 'written'
    finally:
        temporary.unlink(missing_ok=True)
