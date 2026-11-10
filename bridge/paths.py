"""Bounded filesystem access, not an OS sandbox."""
import os
from pathlib import Path
import re
import stat

MAX_FILE = 256 * 1024
MAX_TOTAL = 2 * 1024 * 1024
MAX_PACKAGE = 4 * 1024 * 1024
MAX_FILES = 32
RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)', re.I)
DENIED_DIRS = {'.git', '.hermes', '.codex', '.ssh', '.aws', '.azure', '.venv', 'node_modules'}


class BridgeError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fail(code, message):
    raise BridgeError(code, message)


def relative(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        fail('UNSAFE_PATH', 'Expected a nonempty relative path of at most 240 characters.')
    if value.startswith('/') or '\\' in value or ':' in value:
        fail('UNSAFE_PATH', 'Absolute, drive, UNC, ADS and backslash paths are forbidden.')
    if any(p in ('', '.', '..') or p[-1:] in ('.', ' ') or RESERVED.match(p)
           or any(ord(c) < 32 or c in '<>"|?*' for c in p) for p in value.split('/')):
        fail('UNSAFE_PATH', 'Invalid path component.')
    return value


def no_links(path):
    for part in [*reversed(path.parents), path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            fail('LINK_REJECTED', 'Symlinks and Windows reparse points are forbidden.')
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            fail('LINK_REJECTED', 'Multiply linked files are forbidden.')


def workspace(value):
    configured = os.environ.get('PMP_BRIDGE_WORKSPACE', '')
    if not isinstance(value, str) or not value or not configured:
        fail('WORKSPACE_UNAUTHORIZED', 'Set PMP_BRIDGE_WORKSPACE explicitly for this process.')
    root, allowed = Path(value), Path(configured)
    if not root.is_absolute() or not allowed.is_absolute() or '..' in root.parts or '..' in allowed.parts:
        fail('WORKSPACE_UNAUTHORIZED', 'Workspace must be an absolute local directory.')
    if str(root).startswith(('\\\\', '//')) or str(allowed).startswith(('\\\\', '//')):
        fail('WORKSPACE_UNAUTHORIZED', 'Network roots are unsupported.')
    no_links(root)
    no_links(allowed)
    if not root.is_dir() or root.resolve() != allowed.resolve():
        fail('WORKSPACE_UNAUTHORIZED', 'Workspace differs from the operator-selected directory.')
    return root.resolve()


def path_for(root, name):
    relative(name)
    target = root.joinpath(*name.split('/'))
    no_links(target)
    if not target.resolve().is_relative_to(root):
        fail('UNSAFE_PATH', 'Path escapes the authorized root.')
    return target


def selected_file(name):
    relative(name)
    parts = name.lower().split('/')
    if (any(p in DENIED_DIRS or p.startswith('.env') for p in parts)
        or name.lower().startswith('.project-memory/bridge/')
        or parts[-1] in {'auth.json', 'credentials', 'credentials.json', 'id_rsa', 'id_ed25519'}
        or parts[-1].endswith(('.pem', '.key', '.p12', '.pfx'))):
        fail('SENSITIVE_PATH', 'Credential, runtime and bridge-output paths cannot be packaged.')


def read_file(root, name, limit=MAX_FILE):
    target = path_for(root, name)
    with target.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
            fail('UNSAFE_FILE', 'Only singly linked regular files are supported.')
        if info.st_size > limit:
            fail('SIZE_LIMIT', 'File exceeds the size limit.')
        no_links(target)
        current = target.stat()
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            fail('FILE_CHANGED', 'File changed while opening it.')
        data = stream.read(limit + 1)
        end = os.fstat(stream.fileno())
        if len(data) > limit:
            fail('SIZE_LIMIT', 'File exceeds the size limit.')
        if (info.st_size, info.st_mtime_ns) != (end.st_size, end.st_mtime_ns):
            fail('FILE_CHANGED', 'File changed while being read.')
        return data


def write_new(root, name, data):
    target = path_for(root, name)
    parent = root
    for component in name.split('/')[:-1]:
        parent = parent / component
        no_links(parent)
        parent.mkdir(exist_ok=True)
        no_links(parent)
    no_links(target)
    # Exclusive creation; interrupted artifacts are retained and fail verification.
    with target.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
