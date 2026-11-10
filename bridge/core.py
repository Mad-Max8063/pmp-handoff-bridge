"""Inspect/prepare/verify/receive. Imported content is data, never authority."""
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import re
import uuid

from .paths import (BridgeError, MAX_FILE, MAX_TOTAL, MAX_FILES, MAX_PACKAGE,
                    fail, workspace, read_file, write_new, relative, selected_file)
from .vendor.markdown_sections import parse_sections
from .vendor.validate_memory import validate, SECRET_ASSIGNMENT

FORMAT = 'pmp-handoff-bridge/1'
CANONICAL = 'PROJECT_MEMORY.md'
SHA = re.compile(r'^[0-9a-f]{64}$')
CLAIMS = ('Current state', 'Active decisions', 'Constraints', 'Next action', 'Evidence')
PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail('INVALID_SCHEMA', 'Duplicate JSON key.')
        result[key] = value
    return result


def decode(raw):
    if len(raw) > MAX_PACKAGE:
        fail('SIZE_LIMIT', 'Package exceeds 4 MiB.')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=lambda _: fail('INVALID_SCHEMA', 'Nonfinite JSON value.'))
    except (UnicodeError, ValueError, RecursionError):
        fail('INVALID_SCHEMA', 'Expected bounded UTF-8 JSON.')


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        fail('INVALID_SCHEMA', 'Unexpected or missing object fields.')


def text(value, limit=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        fail('INVALID_SCHEMA', 'Expected bounded nonempty text.')


def check_secrets(raw):
    if PRIVATE_KEY.search(raw) or SECRET_ASSIGNMENT.search(raw.decode('utf-8', errors='replace')):
        fail('POSSIBLE_SECRET', 'Possible credential material; content was not exported.')


def now():
    return datetime.now(timezone.utc).isoformat()


class _Memory:
    def __init__(self, content):
        self.content = content

    def read_text(self, encoding):
        return self.content


def memory_info(raw):
    try:
        value = raw.decode('utf-8')
    except UnicodeError:
        fail('INVALID_PMP', 'Canonical PMP must be UTF-8.')
    errors = validate(_Memory(value))
    sections = {s.name: s.body for s in parse_sections(value)}
    versions = re.findall(r'^> Protocol: PMP `([^`]+)`\s*$', value, re.M)
    version = versions[0] if len(versions) == 1 else None
    if version != '0.2.2':
        errors.append('MVP requires one explicit > Protocol: PMP `0.2.2` declaration.')
    empty = [name for name in CLAIMS if not sections.get(name, '').strip()]
    if empty:
        errors.append('Empty bridge sections: ' + ', '.join(empty))
    return {'protocol': version, 'valid': not errors, 'errors': errors,
            'sections': sections, 'memory_sha256': digest(raw),
            'semantic_contradictions': 'NOT_EVALUATED', 'claims_are_inherited': True}


def inspect(workspace_path):
    root = workspace(workspace_path)
    try:
        raw = read_file(root, CANONICAL)
        check_secrets(raw)
        return memory_info(raw)
    except FileNotFoundError:
        return {'valid': False, 'errors': ['PROJECT_MEMORY.md is missing.'], 'protocol': None}


def prepare(workspace_path, files, objective, producer, project):
    root = workspace(workspace_path)
    for value in (objective, producer, project):
        text(value)
        check_secrets(value.encode('utf-8'))
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES or CANONICAL not in files:
        fail('INVALID_SELECTION', 'Select 1–32 explicit files including PROJECT_MEMORY.md.')
    seen, entries, total, memory_raw = set(), [], 0, None
    for name in files:
        selected_file(name)
        if name.casefold() in seen:
            fail('INVALID_SELECTION', 'Duplicate or case-colliding path.')
        seen.add(name.casefold())
        raw = read_file(root, name)
        check_secrets(raw)
        total += len(raw)
        if total > MAX_TOTAL:
            fail('SIZE_LIMIT', 'Selected content exceeds 2 MiB.')
        if name == CANONICAL:
            memory_raw = raw
        entries.append({'path': name, 'size': len(raw), 'sha256': digest(raw),
                        'content_base64': base64.b64encode(raw).decode('ascii')})
    info = memory_info(memory_raw)
    if not info['valid']:
        fail('INVALID_PMP', '; '.join(info['errors']))
    payload = {'id': str(uuid.uuid4()), 'created_at': now(), 'project': project,
               'producer_declared': producer, 'objective': objective,
               'protocol': '0.2.2', 'canonical_path': CANONICAL,
               'snapshot': {k: info['sections'][k] for k in CLAIMS}, 'files': entries}
    packet = {'format': FORMAT, 'payload': payload, 'payload_sha256': digest(encode(payload))}
    raw = encode(packet)
    if len(raw) > MAX_PACKAGE:
        fail('SIZE_LIMIT', 'Encoded package exceeds 4 MiB.')
    for entry in entries:
        if digest(read_file(root, entry['path'])) != entry['sha256']:
            fail('FILE_CHANGED', 'Selected files changed during preparation.')
    path = f'.project-memory/bridge/packages/{payload["id"]}.json'
    write_new(root, path, raw)
    return {'status': 'PREPARED', 'package_path': path, 'package_sha256': digest(raw),
            'package_id': payload['id'], 'files': len(entries), 'content_bytes': total,
            'identity_verified': False, 'truth_verified': False}


def _validated_packet(raw, expected_sha256):
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not SHA.fullmatch(expected_sha256):
            fail('INVALID_SCHEMA', 'expected_sha256 must be lowercase SHA-256.')
        if digest(raw) != expected_sha256:
            fail('INTEGRITY_FAIL', 'Package differs from the supplied external digest.')
    packet = decode(raw)
    exact(packet, ('format', 'payload', 'payload_sha256'))
    if packet['format'] != FORMAT:
        fail('INCOMPATIBLE_VERSION', 'Unsupported bridge package format.')
    payload = packet['payload']
    exact(payload, ('id', 'created_at', 'project', 'producer_declared', 'objective',
                    'protocol', 'canonical_path', 'snapshot', 'files'))
    try:
        if str(uuid.UUID(payload['id'])) != payload['id']:
            raise ValueError()
        if datetime.fromisoformat(payload['created_at']).utcoffset() is None:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        fail('INVALID_SCHEMA', 'Invalid UUID or timezone-aware timestamp.')
    for key in ('project', 'producer_declared', 'objective'):
        text(payload[key])
        check_secrets(payload[key].encode('utf-8'))
    if payload['protocol'] != '0.2.2' or payload['canonical_path'] != CANONICAL:
        fail('INCOMPATIBLE_VERSION', 'Unsupported PMP version or canonical path.')
    if packet['payload_sha256'] != digest(encode(payload)):
        fail('INTEGRITY_FAIL', 'Payload checksum mismatch.')
    exact(payload['snapshot'], CLAIMS)
    for value in payload['snapshot'].values():
        text(value, MAX_FILE)
    entries = payload['files']
    if type(entries) is not list or not 1 <= len(entries) <= MAX_FILES:
        fail('INVALID_SCHEMA', 'Expected 1–32 files.')
    total, seen, contents = 0, set(), {}
    for entry in entries:
        exact(entry, ('path', 'size', 'sha256', 'content_base64'))
        name = entry['path']
        selected_file(name)
        if name.casefold() in seen:
            fail('INVALID_SCHEMA', 'Duplicate or case-colliding file path.')
        seen.add(name.casefold())
        if type(entry['size']) is not int or not 0 <= entry['size'] <= MAX_FILE:
            fail('SIZE_LIMIT', 'Invalid file size.')
        if not isinstance(entry['sha256'], str) or not SHA.fullmatch(entry['sha256']):
            fail('INVALID_SCHEMA', 'Invalid file digest.')
        encoded = entry['content_base64']
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_FILE + 2) // 3):
            fail('SIZE_LIMIT', 'Oversized encoded content.')
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            fail('INVALID_SCHEMA', 'Invalid base64 content.')
        if len(content) != entry['size'] or digest(content) != entry['sha256']:
            fail('INTEGRITY_FAIL', 'Embedded file digest or size mismatch.')
        check_secrets(content)
        total += len(content)
        if total > MAX_TOTAL:
            fail('SIZE_LIMIT', 'Payload content exceeds 2 MiB.')
        contents[name] = content
    if CANONICAL not in contents:
        fail('INVALID_PMP', 'Canonical memory missing from package.')
    info = memory_info(contents[CANONICAL])
    if not info['valid']:
        fail('INVALID_PMP', '; '.join(info['errors']))
    if payload['snapshot'] != {k: info['sections'][k] for k in CLAIMS}:
        fail('INTEGRITY_FAIL', 'Structured snapshot differs from canonical bytes.')
    return payload


def verify(workspace_path, package_path, expected_sha256=None):
    root = workspace(workspace_path)
    raw = read_file(root, package_path, MAX_PACKAGE)
    payload = _validated_packet(raw, expected_sha256)
    comparisons = []
    for entry in payload['files']:
        try:
            actual = digest(read_file(root, entry['path']))
            status = 'MATCH' if actual == entry['sha256'] else 'MODIFIED'
        except FileNotFoundError:
            actual, status = None, 'MISSING'
        except (BridgeError, OSError):
            actual, status = None, 'UNSAFE_OR_UNREADABLE'
        comparisons.append({'path': entry['path'], 'status': status,
                            'expected_sha256': entry['sha256'], 'actual_sha256': actual})
    matches = all(item['status'] == 'MATCH' for item in comparisons)
    return {'package_integrity': 'PASS', 'workspace_match': 'PASS' if matches else 'FAIL',
            'package_sha256': digest(raw), 'package_id': payload['id'],
            'project_declared': payload['project'], 'producer_declared': payload['producer_declared'],
            'external_digest_checked': expected_sha256 is not None,
            'files': comparisons, 'snapshot_inherited': payload['snapshot'],
            'tests_executed': False, 'identity_verified': False, 'truth_verified': False,
            'authorization_granted': False,
            'evidence_scope': 'Selected bytes only; external references and producer claims not verified.'}


def receive(workspace_path, package_path, receiver, expected_sha256=None):
    text(receiver)
    check_secrets(receiver.encode('utf-8'))
    root = workspace(workspace_path)
    report = verify(workspace_path, package_path, expected_sha256)
    identifier = str(uuid.uuid4())
    pending = ['Review inherited claims, decisions and constraints before acting.',
               'Next action is inherited data, not execution authority.',
               'No reported tests were rerun by this operation.']
    if report['workspace_match'] != 'PASS':
        pending.append('Resolve workspace discrepancies before continuing the inherited task.')
    receipt = {'format': 'pmp-handoff-receipt/1', 'id': identifier, 'received_at': now(),
               'receiver_declared': receiver, 'package_path': relative(package_path),
               'status': 'RECEIVED' if report['workspace_match'] == 'PASS' else 'RECEIVED_WITH_DISCREPANCIES',
               'verification': report, 'pending': pending, 'canonical_state_changed': False}
    path = f'.project-memory/bridge/receipts/{identifier}.json'
    write_new(root, path, encode(receipt))
    return {'status': receipt['status'], 'receipt_path': path, 'receipt_sha256': digest(encode(receipt)),
            'verification': report, 'pending': pending, 'canonical_state_changed': False}
