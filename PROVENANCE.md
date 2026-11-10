# Provenance

Plugin code is an independent experimental implementation by Max Devs Solutions,
licensed under the included MIT license. It is not a modification to PMP Core.

The following files are copied unchanged from the MIT project
https://github.com/Mad-Max8063/project-memory-protocol-public at commit
`7cf5533276740a34e6f5f36d75258f17aaa705cc`:

| Origin | Destination | SHA-256 of copied bytes |
| --- | --- | --- |
| scripts/markdown_sections.py | bridge/vendor/markdown_sections.py | 896c139cbcca0f04bf3c12bf510909c1ebe71ffff5a40678c4f9662c26378b0a |
| scripts/validate_memory.py | bridge/vendor/validate_memory.py | 5f53349fa4c4e61ace8ed1003f7c9b7e8e4f56da38d97e93449fc3c743a362af |

The included LICENSE preserves the original copyright notice:
Copyright (c) 2026 Matías Maximiliano Bernal / Max Devs Solutions.

The historical `experiments/hermes-pmp/adapter.py` was inspected for conventions
but was not copied: its task execution and canonical-memory mutations are outside
this plugin's scope. No historical transcripts, archives or private evidence are
included. The second reference checkout and its untracked reports were untouched.

Hermes API references inspected for this implementation:

- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- https://hermes-agent.nousresearch.com/docs/user-guide/features/plugin-catalog

The local install stamp declares `0.21.6+607.gc573316`, source commit
`c57331677d7fc46298a7159cf3a650853f0966c5`. This is installation metadata,
not proof the runtime started successfully. Actual CLI probe results, launcher
hash, and any guard failures are recorded separately under `evidence/`.
