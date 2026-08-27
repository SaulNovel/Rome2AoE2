# Offline Rome II fixtures

Only metadata is tracked here. Proprietary payloads live in ignored `data/local-fixtures/`; the ignored private archive is `build/private-transfer/rome2aoe2-offline-fixtures.zip`. Never publish, upload, stage, or commit either payload location.

The exporter takes the known-working validated cache, refuses a missing/empty source, copies without changing it, records relative paths/sizes/SHA-256 identities, preserves path case, and creates a deterministic ZIP. The conservative cache is a closure superset shared by Principes and frozen Hastati; this avoids pretending ownership can be reconstructed more narrowly from the currently available reports. It also privately includes `_prepared/principes/static-unit.blend`, the approved canonical-manifest assembly used only for a one-frame offline Blender smoke. This derived file contains game geometry and remains proprietary/ignored like all payloads.

```powershell
py -3.14 scripts\export_offline_fixtures.py --source build\cache\rome2aoe2\assets-v1
py -3.14 scripts\verify_offline_fixtures.py
Get-FileHash build\private-transfer\rome2aoe2-offline-fixtures.zip -Algorithm SHA256
.venv\Scripts\python.exe scripts\run_blender_fast_smoke.py
```

Import validates archive paths before extraction, rejects duplicates, verifies every expected hash, rejects unexpected files, and will not overwrite an existing fixture tree unless `--replace` is explicit. It only writes beneath the requested ignored fixture destination and never writes tracked source paths.

Current private archive baseline: 10,331,024 bytes, SHA-256 `ccc2649bde2e00dd5b6df7f07f6674216f4abc7fccb775f3e589d27ff3e849c8`. It supersedes the raw-assets-only archive `a48f9c0944abf65a522bb890cd82e3e593d1eef591ae7a7439c96b833d9a15f9`; the sole logical addition is the hashed `_prepared/principes/static-unit.blend` offline smoke input.
