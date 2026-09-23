# Recoverable migration

The pre-migration inspection found an old v3 GUI runtime record for PID 26432, reviewer `lead`, and a running Python process with that PID. WMI process command-line access was unavailable; process listing and existing GUI runtime/session files were used. No old process was stopped and no file was moved out from under it.

The migration was copy-only. [migration.json](migration.json) identifies the dated archive under `../old_review/20260914_235744`. Its `manifest.json` lists original paths, sizes, SHA-256 values, environment versions and external large-source references. **527 files** were copied; every archive entry was read back and hash-checked, with no source changes detected during copying. Old code, launchers, plans, guides, catalog, dependency records, tests, runtime records, labels, journals and revisions are included. New `review` and `old_review` directories and transient locks were excluded from recursive snapshotting. Small imported Python runtime files were preserved under their original project-relative paths; large caches/checkpoints remain referenced in place.

Historical labels/journals/revisions remain at `../reviewers`. Existing shared queues remain at `../review_queues` if present. The browser reads these originals. Adoption occurs only through the replacement GUI, checks the historical file hash, retains a copy in the new journal history and records the original path/hash/revision. Scripts do not create historical approvals.

## Restore

Use the archive's `RESTORE.md`. Extract `snapshot.zip` into a separate empty root and compare entries with the manifest. Its paths are project-relative. Existing live annotation files must never be overwritten with a point-in-time archive. Close relevant writers before restoring code or launchers into the original location; first back up the replacement. The original v3 code is also still present at `../code` for recovery, but active launchers/documentation point only to `review`.

The replacement resolves its project root by validated marker files and its v3/review location, independent of working directory. The launcher activates `octa` and inserts explicit absolute import paths. Source and queue paths are validated against actual source/model identity. A dated archive is never overwritten by rerunning migration; `migrate.py` is a one-time copy/bootstrap tool and refuses to replace an existing new code tree.
