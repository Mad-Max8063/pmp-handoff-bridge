# PMP Handoff Bridge

Experimental native Hermes plugin for **inspect → prepare → verify → receive**.
It carries selected PMP state and evidence bytes across a handoff, detects drift,
and records reception without replacing the receiving project's canonical state.

This is executable validation and persistence, not a prompt wrapper. There is no
model, network client, server, database, background task, or runtime dependency on
the original PMP repository. It does not execute the task described in a handoff.

## Requirements and local quick start

- Python 3.12+ (host verification uses the version recorded in evidence).
- Hermes is optional for offline operation; native compatibility is a separate gate.
- No Python packages need to be installed for the bridge or offline tests.

From this directory in PowerShell:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/demo.py
```

The demo creates a new synthetic workspace under `.runtime/`, prepares a package,
verifies it, modifies one selected file, records the discrepancy, restores that
synthetic file, and receives the valid package. It preserves canonical memory.
It prints the run directory and receipt path. No agent/model is invoked.

## Tools

All tools require `workspace_path`, an absolute local directory identical to the
operator's process-level `PMP_BRIDGE_WORKSPACE`. Missing authorization fails closed.
Changing that variable is an operator action; a package cannot select its root.

| Native tool | Additional arguments | Effect |
| --- | --- | --- |
| `pmp_inspect` | none | Read canonical PMP, version, sections, structural errors |
| `pmp_prepare_handoff` | `files`, `objective`, `producer`, `project` | Append a self-contained JSON package |
| `pmp_verify_handoff` | `package_path`, optional `expected_sha256` | Check embedded bytes and compare local files |
| `pmp_receive_handoff` | same plus `receiver` | Append a receipt after package verification |

`files` is an explicit list, including `PROJECT_MEMORY.md`. Paths use `/`.
`producer`, `project` and `receiver` are declared metadata, not identity proofs.
`package_path` is relative to the authorized workspace. To transfer a package,
copy only that JSON file into the receiver's workspace, for example into
`.project-memory/bridge/inbox/`. Copying is an explicit operator step; the bridge
does not fetch URLs or extract files over local state.

Supply the SHA-256 returned by preparation through a separately trusted channel
as `expected_sha256` when available. Internal checksums detect inconsistency;
someone who can rewrite the whole package can also recompute them. An external
digest is only as trustworthy as the channel that delivered it.

### Offline CLI (same implementation as the native tools)

Select a disposable workspace created by the demo:

```powershell
$env:PMP_BRIDGE_WORKSPACE = 'C:\absolute\path\to\the\demo-workspace'
@{ workspace_path = $env:PMP_BRIDGE_WORKSPACE } |
    ConvertTo-Json -Compress |
    python -B -m bridge pmp_inspect

@{
    workspace_path = $env:PMP_BRIDGE_WORKSPACE
    files = @('PROJECT_MEMORY.md', 'task.txt', 'evidence.txt')
    objective = 'Review the bounded label task before continuing.'
    producer = 'operator-declared-producer'
    project = 'synthetic-label-task'
} | ConvertTo-Json -Compress | python -B -m bridge pmp_prepare_handoff
```

Use the returned `package_path` and `package_sha256` in a JSON argument object
for `pmp_verify_handoff`, then add `receiver` for `pmp_receive_handoff`.
The CLI reads bounded JSON from stdin; it never evaluates a command from JSON.
Exit codes: `0` successful/matching, `1` invalid inspected PMP or workspace drift,
`2` rejected input/filesystem/package. A drift receipt is still persisted with exit 1.

## Native Hermes setup and validation

Set `PMP_BRIDGE_WORKSPACE` to the absolute disposable fixture workspace you authorize. This variable is a local path, not a credential. Prepare a fresh isolated home:

```text
python -B scripts/install_local.py --home /absolute/path/to/new-hermes-home
```

The installer refuses an existing home. In that terminal set `HERMES_HOME` to the new home, set `PMP_BRIDGE_WORKSPACE`, then use your installed Hermes version's help before running:

```text
hermes plugins doctor /absolute/path/to/plugin --ci
hermes plugins validate /absolute/path/to/plugin --install-deps
```

The plugin has no Python dependencies. Hermes installation/authentication and the selected model are operator-managed. Agent inference can use the operator's existing model access; offline verification makes no model calls. Do not copy authentication files into a project or repository.

Documented native execution used Windows Hermes 0.21.6+607.gc573316 with a project-local clean OpenAI SDK, and Ubuntu/WSL2 Hermes 0.23.0 on a second notebook. The Windows SDK workaround is specific to that host; this repository does not patch or redistribute Hermes. See evidence/RESULTS.md. Compatibility on untested versions is not claimed.

## Package and receipt contract

`pmp-handoff-bridge/1` contains a SHA-256 of canonical JSON payload bytes; the
payload contains ID, UTC creation time, declared producer/project, objective,
PMP 0.2.2 snapshot, and files with relative paths, sizes, SHA-256 and base64 bytes.
The snapshot must match the embedded canonical memory. Unknown fields, duplicate
JSON keys, incompatible versions and ambiguous/colliding paths are rejected.
This transport is experimental and does not change PMP Core.

Package checks and workspace checks are independent:

- Invalid package: reject; do not create a successful reception receipt.
- Intact package, unchanged selected files: `RECEIVED`.
- Intact package, missing/modified/unsafe local files: `RECEIVED_WITH_DISCREPANCIES`.

Every receipt includes observed hashes, discrepancies, inherited next action,
pending review, timestamp and explicit false values for tests executed, identity
verified, truth verified and authority granted. It does not overwrite decisions,
constraints or canonical memory. Receipt data is also local, unsigned evidence.
PMP Evidence references remain inherited text; only selected bytes are checked.

## Boundaries

- 32 selected files; 256 KiB/file; 2 MiB total decoded bytes; 4 MiB JSON package.
- No recursive collection or command execution; no conversations collected.
- Reject absolute/UNC/drive paths, traversal, ADS, reserved Windows names,
  symlinks, junctions/reparse points and hardlinked files, including linked ancestors.
- Credential/runtime paths are denied; known secret patterns are rejected.
  This is not comprehensive secret detection: review the explicit selection.
- Exact byte hashes intentionally flag CRLF/LF changes; no hidden normalization.
- Exclusive writes preserve existing artifacts. An interrupted write can leave
  an invalid new artifact; this is not a multi-file crash-proof transaction.
- File checks mitigate accidental replacement but do not defend against an
  adversarial concurrent process racing filesystem operations. No OS sandbox claim.
- Structural validation is not semantic understanding, truth checking, general
  contradiction detection, complete PMP conformance, model identity, or freshness.
- The fixture's inherited report is explicitly synthetic. Actual tool evidence
  is produced by the check/demo runners, not asserted by the fixture.

## Results, provenance and distribution

See `evidence/RESULTS.md` for observed results and validation limits.
`PROVENANCE.md` identifies the two unchanged MIT source modules and origin hashes.
The 83-second demo follows prepare, verify, controlled drift, receipt, and restoration.

No paid API, service, global install, Git commit, push, PR, marketplace submission
or acceptance is part of this delivery. Local validation is not catalog approval.
Catalog publication later requires a reviewed public commit and human admission:
https://hermes-agent.nousresearch.com/docs/user-guide/features/plugin-catalog

Delete only a reviewed disposable `.runtime/<run>` directory to clean local runs.
Keep any evidence you need first. The plugin creates no cloud resources to clean.

## Public candidate evidence and disclosures

This candidate includes the 18 core tests and synthetic fixture. Native registration and recorded runs were verified on the development hosts; catalog CI on the eventual pinned public commit is still pending. The approved 83-second demo uses cropped Windows CLI footage and distinct historical Ubuntu/WSL2 evidence.

The plugin reads explicitly selected files inside the operator-authorized workspace, which is outside its own installation directory, and writes append-only packages/receipts under that workspace. It stores selected file bytes in packages: choose files that are safe to share. It does not read credential stores, send telemetry, contact network services, execute shell commands, self-update, patch Hermes, or start background tasks. Host plugin execution is not an OS sandbox. Receipts are unsigned local observations. Hashes do not certify agent identity, semantic truth, session freshness, or authorization.

The reviewed MIT parser and validator provenance is in PROVENANCE.md. Local developer runtime diagnostics and model runners are excluded from this candidate. PMP Core remains optional and unchanged.
