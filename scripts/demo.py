"""Offline executable demo; creates only a new disposable workspace in this project."""
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from bridge.api import invoke
from bridge.core import digest, encode


def main():
    root = PROJECT / '.runtime' / ('demo-' + uuid.uuid4().hex[:12])
    root.mkdir(parents=True)
    for name in ('PROJECT_MEMORY.md', 'task.txt', 'evidence.txt'):
        shutil.copyfile(PROJECT / 'fixtures' / name, root / name)
    previous = os.environ.get('PMP_BRIDGE_WORKSPACE')
    os.environ['PMP_BRIDGE_WORKSPACE'] = str(root)
    steps = []

    def call(name, **params):
        outcome = invoke(name, {'workspace_path': str(root), **params})
        if not outcome['ok']:
            raise RuntimeError(outcome)
        steps.append({'tool': name, 'result': outcome['result']})
        return outcome['result']

    try:
        before = (root / 'PROJECT_MEMORY.md').read_bytes()
        call('pmp_inspect')
        package = call('pmp_prepare_handoff', files=['PROJECT_MEMORY.md', 'task.txt', 'evidence.txt'],
                       objective='Transfer the bounded label task for review.', producer='demo-producer', project='synthetic-label-task')
        params = {'package_path': package['package_path'], 'expected_sha256': package['package_sha256']}
        assert call('pmp_verify_handoff', **params)['workspace_match'] == 'PASS'
        original = (root / 'task.txt').read_bytes()
        (root / 'task.txt').write_bytes(b'Changed after handoff\n')
        assert call('pmp_verify_handoff', **params)['workspace_match'] == 'FAIL'
        changed = call('pmp_receive_handoff', receiver='demo-receiver', **params)
        assert changed['status'] == 'RECEIVED_WITH_DISCREPANCIES'
        (root / 'task.txt').write_bytes(original)
        received = call('pmp_receive_handoff', receiver='demo-receiver', **params)
        assert received['status'] == 'RECEIVED'
        assert (root / 'PROJECT_MEMORY.md').read_bytes() == before
        report = {'status': 'PASS', 'mode': 'offline-direct-tools', 'hermes_runtime_exercised': False,
                  'model_calls': 0, 'network_calls': 0, 'canonical_preserved': True,
                  'canonical_sha256': digest(before), 'steps': steps}
        (root / 'demo-report.json').write_bytes(encode(report))
        print(json.dumps({'status': 'PASS', 'run_directory': str(root),
                          'steps': len(steps), 'receipt_path': received['receipt_path'],
                          'hermes_runtime_exercised': False}, indent=2))
        return 0
    finally:
        if previous is None:
            os.environ.pop('PMP_BRIDGE_WORKSPACE', None)
        else:
            os.environ['PMP_BRIDGE_WORKSPACE'] = previous


if __name__ == '__main__':
    raise SystemExit(main())
