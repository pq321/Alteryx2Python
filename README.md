# Alteryx Migration Python

This repository is being structured as a constitution-driven Alteryx-to-Python migration framework.

Current priorities:

1. preserve Alteryx semantics before optimization
2. enforce a canonical IR between parsing and generation
3. keep tool semantics modular and metadata-driven
4. validate equivalence through tests, trace, and comparison layers

Canonical package root:

- `alteryx2python/`

Compatibility-only package:

- `alteryx_runtime/`

Current implemented slice:

- `Select` tool baseline implementation

Current architectural scaffolding introduced:

- IR models and validators
- runtime context, trace, and executor
- tool registry metadata
- comparison layer
- documentation and fixture layout

Important constraint:

- optimizer code exists only as disabled placeholders and is not part of canonical baseline migration
