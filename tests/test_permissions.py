"""Tests for permission preflight reporting helpers."""

from __future__ import annotations

from flow_dictate.permissions import (
    PermissionCheckResult,
    PermissionPreflightReport,
    check_accessibility_permission,
    check_input_monitoring_permission,
    check_microphone_permission,
    format_preflight_report,
)


def test_non_macos_checks_report_unsupported(monkeypatch) -> None:
    """Verify permission checks return ``unsupported`` on non-macOS platforms.

    Parameters:
        monkeypatch: Pytest fixture for temporary attribute patching.

    Returns:
        None.

    Raises:
        AssertionError: If state mapping for non-macOS is incorrect.

    Example:
        ``pytest -k test_non_macos_checks_report_unsupported``
    """

    import flow_dictate.permissions as permissions_module

    monkeypatch.setattr(permissions_module.sys, "platform", "linux")

    mic = check_microphone_permission()
    ax = check_accessibility_permission()
    input_monitoring = check_input_monitoring_permission()

    assert mic.state == "unsupported"
    assert ax.state == "unsupported"
    assert input_monitoring.state == "unsupported"


def test_format_preflight_report_includes_summary_and_remediation() -> None:
    """Verify report formatting includes actionable remediation text.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If formatted report omits expected content.

    Example:
        ``pytest -k test_format_preflight_report_includes_summary_and_remediation``
    """

    report = PermissionPreflightReport(
        microphone=PermissionCheckResult(
            name="Microphone",
            granted=True,
            state="granted",
            details="Microphone permission is granted.",
        ),
        accessibility=PermissionCheckResult(
            name="Accessibility",
            granted=False,
            state="denied",
            details="Accessibility permission is not granted.",
            remediation="Enable Accessibility in System Settings.",
        ),
        input_monitoring=PermissionCheckResult(
            name="Input Monitoring",
            granted=False,
            state="denied",
            details="Input Monitoring permission is not granted.",
            remediation="Enable Input Monitoring in System Settings.",
        ),
    )

    output = format_preflight_report(report)
    assert "Permission preflight:" in output
    assert "Accessibility: NEEDS ACTION" in output
    assert "Fix: Enable Accessibility in System Settings." in output
    assert "One or more required permissions are missing." in output
