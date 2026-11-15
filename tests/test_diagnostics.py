"""Self-test reporting, without running an AI inference."""

from __future__ import annotations

from pathlib import Path

from stickinator.diagnostics import run_self_test


def test_reports_packages_and_succeeds(tmp_path: Path) -> None:
    report = tmp_path / "report.txt"

    exit_code = run_self_test(report_path=report)

    text = report.read_text()
    assert exit_code == 0
    assert "self-test OK" in text
    assert "rembg" in text
    assert "onnxruntime providers" in text
