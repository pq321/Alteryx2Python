# Implementation Plan: Multi-Case Boundary Differential Delivery & Integration

## Prerequisite Check

- Confirm `11-21-phase2-native-package` is implemented and passing tests before starting this task.

## Checklist

1. Record `original_source` and per-node staged input map in `parity/migration.py` / `parity/runner.py` (`manifest.json`).
2. Implement multi-case boundary differential verification in `alteryx2python/parity/delivery.py` (primary staged case + perturbed-parameter config case + 0-row input case, all executing the single un-staged compiled Phase 2 package via external config files).
3. Update `alteryx2python/parity/presentation.py` (`_deliver`), `alteryx2python/cli.py` (`readable`), and `webapp/backend.py` (`compile_workflow`) to surface the modular package (`pipeline.py` + `config.toml` + `manifest.json`).
4. Update `examples/python_pipeline_comparison/compare.py` and `compare_app.py` so `compare_app` compiles the app **once** and runs `defaults`, `alternate`, and `empty` via config overrides.
5. Update `.trellis/spec/backend/readable-python.md` and `docs/designer_delivery_demo.md`.
6. Run full backend + frontend test suites and benchmark comparisons.

## Validation Commands

```powershell
.venv/Scripts/python.exe -m pytest tests/test_parity_behavior tests/test_cli.py tests/test_webapp -q
.venv/Scripts/python.exe -m examples.python_pipeline_comparison.compare_app reports/seven-question-modular-check
.venv/Scripts/python.exe examples/python_pipeline_comparison/compare.py reports/transactions-modular-check
npm --prefix webapp test
.venv/Scripts/python.exe -m pytest
```
