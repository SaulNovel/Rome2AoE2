# Known verification baseline

On 2026-08-27 the clean Python 3.14.6 virtual environment ran 321 tests with 318 passed, 0 skipped, 2 failed, and 1 error:

```powershell
.\scripts\run_tests_windows.ps1
```

The inherited non-green items are:

| Result | Exact test | Cause/classification |
|---|---|---|
| failure | `Rome2ProductionVisualPolicyTests.Rome2ProductionVisualPolicyTests.test_exact_backend_diagnostic_options_preserve_v1_defaults` | Renderer-contract mismatch associated with the pre-existing modified contributor-layer/rendering work; not introduced by migration files. |
| failure | `WeaponReadabilityPolicyTests.WeaponReadabilityPolicyTests.test_runtime_preserves_fsr_and_native_lighting_variation` | Renderer-contract mismatch associated with the same pre-existing modified contributor-layer/rendering work; not introduced by migration files. |
| error | `Rome2SkinIntegrationAuditTests.SkinIntegrationAuditTests.test_structural_bug_is_corrected` | Integration-audit test defect/local generated-input dependency: it requires `build/local-integration/rome2/runtime-parity-proof/skin-integration-audit/report.json` but neither generates it nor skips when it is absent. |

Treat any different failure, error, or total as a new result requiring investigation. The test wrapper intentionally returns the unittest process's failing exit code; it does not filter or downgrade these items.
