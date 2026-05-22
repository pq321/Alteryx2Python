# UV Company Source Backup

## Why This Exists

This repository was previously locked against a company Nexus mirror instead of public PyPI. That caused `uv` to fetch packages from the corporate registry during local development.

This backup note preserves the previous source details so a company-managed machine can restore that behavior later if needed.

## Previous Registry Source

- Registry: `https://it4it-nexus-tp-repo.swissbank.com/repository/public-lib-python-pypi/simple`

## What Was Previously True

- Existing entries in `uv.lock` were resolved against the company Nexus registry.
- TLS handshake failures against that Nexus host blocked `uv run pytest` and `uv sync` in the current environment.

## Why The Repo Does Not Default To Nexus-First

We tested a Nexus-first plus PyPI-fallback project configuration in this repository.

That setup did not work reliably for personal/off-network use, because `uv` treats a Nexus connection or TLS failure as a hard error instead of falling through to PyPI. In practice:

- if the package is unavailable on Nexus, fallback behavior can work
- if Nexus itself is unreachable or the TLS handshake fails, `uv` stops before PyPI fallback can help

So the repository default remains PyPI-first for portability.

## How To Restore Company Source Intentionally

If a company-managed machine should prefer the company mirror again, use one of these approaches explicitly instead of relying on stale lockfile state.

### One-off command

```powershell
uv lock --index https://it4it-nexus-tp-repo.swissbank.com/repository/public-lib-python-pypi/simple --default-index https://pypi.org/simple --native-tls
uv sync --index https://it4it-nexus-tp-repo.swissbank.com/repository/public-lib-python-pypi/simple --default-index https://pypi.org/simple --native-tls
```

### Local machine config

Keep the repository on PyPI defaults, and apply company-only index settings from a local, non-committed `uv.toml` or shell alias on the company machine.

### Native TLS hint

If the company mirror requires enterprise certificates installed in the Windows certificate store, try:

```powershell
uv lock --native-tls
uv sync --native-tls
```

That tells `uv` to use the platform trust store instead of bundled Mozilla roots.

## Current Project Default

The committed project default is public PyPI, with the company Nexus source documented here for explicit opt-in use on company-managed machines.
