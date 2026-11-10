"""Offline CLI: python -B -m bridge TOOL < arguments.json"""
import argparse
import json
import sys
from .api import DEFINITIONS, invoke
from .core import decode
from .paths import MAX_PACKAGE, BridgeError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', choices=DEFINITIONS)
    args = parser.parse_args()
    try:
        params = decode(sys.stdin.buffer.read(MAX_PACKAGE + 1))
        result = invoke(args.tool, params)
    except BridgeError as exc:
        result = {'ok': False, 'error': {'code': exc.code, 'message': str(exc)}}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    if not result['ok']:
        return 2
    outcome = result['result']
    if outcome.get('valid') is False or outcome.get('workspace_match') == 'FAIL':
        return 1
    if outcome.get('status') == 'RECEIVED_WITH_DISCREPANCIES':
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
