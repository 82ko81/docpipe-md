# Sync provenance

## Relationship

`docpipe-md` is the standalone distribution of the reusable Docpipe conversion core.

Workspace-specific intake, classification, Raw/Ops/Wiki routing, project manifests, and operating policy stay in `82ko81/workspace`. They are deliberately not copied into this package.

## Current synchronization

- Source repository: `82ko81/workspace`
- Source branch: `docpipe/xlsx-renderer-and-manifest`
- Source feature commit: `388fc00ae7b4a69188af900e0f0d378b6fa38eb3`
- Source feature date: 2026-09-09
- Standalone synchronization date: 2026-09-21
- Previous standalone tip: `f25064bb6a278c5cce1aa424c97551197a8a598b`
- Previous standalone archive branch: `archive/standalone-2026-08-20`

## Core files synchronized from Workspace

- `docpipe/__init__.py`
- `docpipe/converters.py`
- `docpipe/policy.py`
- `docpipe/quality.py`
- `docpipe/route.py`
- `docpipe/sidecar.py`
- `docpipe/manifest.py`

The standalone CLI, packaging metadata, README, tests, and CI are maintained in this repository.

## Future synchronization rule

Do not infer the newest Docpipe from the newest `workspace/main` repository tip. Docpipe-specific work may live on a newer component branch. Compare component commits first, preserve the previous standalone tip on an archive branch, then sync the reusable core explicitly.
