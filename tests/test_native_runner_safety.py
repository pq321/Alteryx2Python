from pathlib import Path

import pytest

from alteryx2python import native_runner


def _runner(
    tmp_path, monkeypatch, *, returncode=0, stdout="", stderr="", write_output=True
):
    exe = tmp_path / "engine.exe"
    exe.write_text("x")
    workflow = tmp_path / "flow.yxmd"
    workflow.write_text("workflow")
    output = tmp_path / "out.yxdb"

    def fake_run(args, **kwargs):
        if write_output:
            output.write_bytes(b"new")
        return type(
            "Completed",
            (),
            {"returncode": returncode, "stdout": stdout, "stderr": stderr},
        )()

    monkeypatch.setattr(native_runner.subprocess, "run", fake_run)
    return native_runner.EngineCmdRunner(str(exe)), workflow, output


def test_existing_output_is_preserved_but_cannot_be_used_as_success(
    tmp_path, monkeypatch
):
    runner, workflow, output = _runner(tmp_path, monkeypatch, write_output=False)
    output.write_bytes(b"old")
    result = runner.run(workflow, output)
    assert output.read_bytes() == b"old"
    assert not result.ok


def test_nonzero_engine_return_with_partial_output_fails(tmp_path, monkeypatch):
    runner, workflow, output = _runner(tmp_path, monkeypatch, returncode=2)
    result = runner.run(workflow, output)
    assert not result.ok
    assert result.status == "failed"


def test_license_failure_is_blocked(tmp_path, monkeypatch):
    runner, workflow, output = _runner(
        tmp_path, monkeypatch, stdout="License feature is not licensed"
    )
    result = runner.run(workflow, output)
    assert result.status == "blocked"
    assert not result.ok


def test_timeout_is_blocked(tmp_path, monkeypatch):
    runner, workflow, output = _runner(tmp_path, monkeypatch)

    def timeout(*args, **kwargs):
        raise native_runner.subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(native_runner.subprocess, "run", timeout)
    result = runner.run(workflow, output)
    assert result.status == "blocked"


def test_designer_backend_never_launches_gui(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        native_runner.subprocess, "run", lambda *a, **k: calls.append(a)
    )
    result = native_runner.DesignerCliRunner(str(tmp_path / "AlteryxGui.exe")).run(
        tmp_path / "flow.yxmd", tmp_path / "out.yxdb"
    )
    assert result.status == "blocked"
    assert calls == []


def test_auto_does_not_fallback_to_designer(monkeypatch):
    class Missing:
        name = "engine-cmd"

        def available(self):
            return False

    monkeypatch.setattr(native_runner, "EngineCmdRunner", lambda: Missing())
    monkeypatch.setattr(
        native_runner,
        "DesignerCliRunner",
        lambda: (_ for _ in ()).throw(AssertionError("GUI fallback")),
    )
    result = native_runner.run_native(Path("flow.yxmd"), Path("out.yxdb"))
    assert result.status == "blocked"
