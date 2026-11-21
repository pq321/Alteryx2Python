# Execution Plan: Native Modular Phase 2 Compiler

## Execution Order Across Child Tasks

Execute and verify each child task sequentially as an independent, green-tested increment:

1. **Child 1 (`11-21-phase2-ir-optimizer`)**:
   - Build `alteryx2python/generator/ir_optimizer.py` with deterministic passes: passthrough/dead-anchor removal, general 1-row `TextInput + AppendFields` parameter folding, `Select` algebraic composition & dead-column pruning, `Formula`/`Filter` fusion, and macro classification (inline 1-call standard macros; extract N-call, Batch, and Iterative macros).
   - Validate that optimized IR preserves end-to-end execution results against unoptimized `WorkflowIR` across unit and property fixtures.
2. **Child 2 (`11-21-phase2-native-package`)**:
   - Build `config_extractor.py`, `vectorized_lowering.py`, and `package_compiler.py` emitting adaptive Python packages (`config.toml`, `pipeline.py`, `cli.py`, `io_utils.py`, optional `macros/` and `references/`).
   - Implement Option A data-driven semantic refinement loop.
   - Verify standalone subprocess execution (`python -I`), zero project imports, zero hardcoded paths/answers in `pipeline.py`, and config hot-swapping without recompilation.
3. **Child 3 (`11-21-phase2-boundary-delivery`)**:
   - Upgrade `parity/migration.py`, `parity/delivery.py`, `parity/presentation.py`, `cli.py`, `webapp/backend.py`, and `examples/python_pipeline_comparison/` (`compare.py`, `compare_app.py`) to emit and verify the modular Phase 2 package using external case configs and multi-case boundary differential checks (default + perturbed parameters + 0-row inputs).
   - Update `.trellis/spec/backend/readable-python.md` to codify the new config-decoupled package and boundary-equivalence contract.

## Validation Commands

```powershell
# Focused Phase 2 optimizer, package compiler, and parity delivery tests
.venv/Scripts/python.exe -m pytest tests/test_generator tests/test_parity_behavior -q

# Benchmark & Analytic App end-to-end verification
.venv/Scripts/python.exe -m examples.python_pipeline_comparison.compare_app reports/verify-modular-app
.venv/Scripts/python.exe examples/python_pipeline_comparison/compare.py reports/verify-modular-transactions

# Full repository regression + coverage gate (>= 80%)
.venv/Scripts/python.exe -m pytest

# Web editor TypeScript build & tests (when webapp integration lands in Child 3)
npm --prefix webapp test
```

## Risky Files and Rollback Points

- `alteryx2python/parity/delivery.py` and `alteryx2python/parity/migration.py`: Existing tests check `acceptance.json` keys (`native_vs_phase_one`, `phase_one_vs_phase_two`, `standalone_execution`). Preserve report schema compatibility while shifting Phase 2 artifact verification to boundary outputs + package entrypoints.
- `alteryx2python/generator/readable.py`: Avoid destructive in-place rewrite before Child 2 package compiler passes differential tests; keep clean adapter boundaries so rollback of any child task is isolated to its module.

## Review Gate Before `task.py start`

- Confirm parent + child `prd.md`, `design.md`, and `implement.md` align with user expectations.
- Start Child 1 (`python ./.trellis/scripts/task.py start 11-21-phase2-ir-optimizer`) only after artifact review approval.
