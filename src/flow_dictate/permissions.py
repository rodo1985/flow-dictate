"""macOS permission preflight checks for dictation workflows."""

from __future__ import annotations

from dataclasses import asdict
import sys
import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PermissionCheckResult:
    """Represent the result of one permission preflight check.

    Parameters:
        name: Human-friendly permission name.
        granted: Whether the permission is currently granted.
        state: Machine-readable status marker.
        details: Short explanatory details for logs and CLI output.
        remediation: Optional action guidance for users.

    Returns:
        PermissionCheckResult: Immutable permission check outcome.

    Raises:
        None.

    Example:
        >>> PermissionCheckResult(
        ...     name="Microphone",
        ...     granted=False,
        ...     state="denied",
        ...     details="Microphone permission denied.",
        ...     remediation="Enable Microphone access in System Settings.",
        ... )
    """

    name: str
    granted: bool
    state: str
    details: str
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class PermissionPreflightReport:
    """Bundle all permission checks used by the app startup preflight.

    Parameters:
        microphone: Microphone access check result.
        accessibility: Accessibility API access check result.
        input_monitoring: Input Monitoring access check result.

    Returns:
        PermissionPreflightReport: Immutable report of all preflight checks.

    Raises:
        None.

    Example:
        ``report = run_permission_preflight()``
    """

    microphone: PermissionCheckResult
    accessibility: PermissionCheckResult
    input_monitoring: PermissionCheckResult

    @property
    def all_required_granted(self) -> bool:
        """Return whether all required permissions are granted.

        Parameters:
            None.

        Returns:
            bool: ``True`` when every required permission is granted.

        Raises:
            None.

        Example:
            ``if report.all_required_granted: ...``
        """

        return (
            self.microphone.granted
            and self.accessibility.granted
            and self.input_monitoring.granted
        )


def run_permission_preflight(prompt: bool = False) -> PermissionPreflightReport:
    """Run macOS permission checks needed for global dictation behavior.

    Parameters:
        prompt: Whether checks may trigger system prompt dialogs when possible.

    Returns:
        PermissionPreflightReport: Full set of permission outcomes.

    Raises:
        None.

    Example:
        ``report = run_permission_preflight(prompt=True)``
    """

    return PermissionPreflightReport(
        microphone=check_microphone_permission(prompt=prompt),
        accessibility=check_accessibility_permission(prompt=prompt),
        input_monitoring=check_input_monitoring_permission(),
    )


def check_microphone_permission(prompt: bool = False) -> PermissionCheckResult:
    """Check microphone capture permission on macOS.

    Parameters:
        prompt: Whether to request permission when not yet determined.

    Returns:
        PermissionCheckResult: Microphone permission result.

    Raises:
        None.

    Example:
        ``result = check_microphone_permission(prompt=False)``
    """

    if sys.platform != "darwin":
        return PermissionCheckResult(
            name="Microphone",
            granted=False,
            state="unsupported",
            details="Microphone preflight is only implemented for macOS.",
            remediation="Run this app on macOS.",
        )

    try:
        from AVFoundation import (  # type: ignore[import-not-found]
            AVCaptureDevice,
            AVMediaTypeAudio,
        )
    except Exception as exc:  # pragma: no cover - depends on local environment.
        return PermissionCheckResult(
            name="Microphone",
            granted=False,
            state="error",
            details=f"Unable to import AVFoundation: {exc}",
            remediation="Install macOS framework dependencies and retry.",
        )

    # Status integers are Apple constants bridged by PyObjC.
    # 0: not determined, 1: restricted, 2: denied, 3: authorized.
    status = int(AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio))
    if status == 3:
        return PermissionCheckResult(
            name="Microphone",
            granted=True,
            state="granted",
            details="Microphone permission is granted.",
        )

    if status == 0 and prompt:
        request_result = _request_microphone_permission(AVCaptureDevice, AVMediaTypeAudio)
        if request_result:
            return PermissionCheckResult(
                name="Microphone",
                granted=True,
                state="granted",
                details="Microphone permission granted after prompt.",
            )

    if status == 0:
        return PermissionCheckResult(
            name="Microphone",
            granted=False,
            state="not_determined",
            details="Microphone permission has not been requested yet.",
            remediation="Run `flow-dictate doctor --prompt-permissions` to request access.",
        )

    if status == 1:
        return PermissionCheckResult(
            name="Microphone",
            granted=False,
            state="restricted",
            details="Microphone permission is restricted by system policy.",
            remediation="Check device management or parental control restrictions.",
        )

    return PermissionCheckResult(
        name="Microphone",
        granted=False,
        state="denied",
        details="Microphone permission is denied.",
        remediation=(
            "Enable Microphone for the Flow Dictate worker process "
            "(python3) in System Settings."
        ),
    )


def _request_microphone_permission(capture_device: object, media_type_audio: object) -> bool:
    """Request microphone permission and wait briefly for callback result.

    Parameters:
        capture_device: AVFoundation capture device class.
        media_type_audio: AVFoundation audio media type constant.

    Returns:
        bool: ``True`` if permission was granted.

    Raises:
        None.

    Example:
        Internal helper only.
    """

    event = threading.Event()
    result: dict[str, bool] = {"granted": False}

    def _completion(granted: bool) -> None:
        """Capture asynchronous prompt result and release waiters."""

        result["granted"] = bool(granted)
        event.set()

    capture_device.requestAccessForMediaType_completionHandler_(media_type_audio, _completion)
    event.wait(timeout=5.0)
    return result["granted"]


def check_accessibility_permission(prompt: bool = False) -> PermissionCheckResult:
    """Check Accessibility API permission for text injection automation.

    Parameters:
        prompt: Whether to show the system trust prompt.

    Returns:
        PermissionCheckResult: Accessibility permission result.

    Raises:
        None.

    Example:
        ``result = check_accessibility_permission(prompt=True)``
    """

    if sys.platform != "darwin":
        return PermissionCheckResult(
            name="Accessibility",
            granted=False,
            state="unsupported",
            details="Accessibility preflight is only implemented for macOS.",
            remediation="Run this app on macOS.",
        )

    try:
        from ApplicationServices import (  # type: ignore[import-not-found]
            AXIsProcessTrusted,
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
    except Exception as exc:  # pragma: no cover - depends on local environment.
        return PermissionCheckResult(
            name="Accessibility",
            granted=False,
            state="error",
            details=f"Unable to import ApplicationServices: {exc}",
            remediation="Install macOS framework dependencies and retry.",
        )

    if prompt:
        trusted = bool(
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})  # type: ignore[arg-type]
        )
    else:
        trusted = bool(AXIsProcessTrusted())

    if trusted:
        return PermissionCheckResult(
            name="Accessibility",
            granted=True,
            state="granted",
            details="Accessibility permission is granted.",
        )

    return PermissionCheckResult(
        name="Accessibility",
        granted=False,
        state="denied",
        details="Accessibility permission is not granted.",
        remediation=(
            "Enable Accessibility for the Flow Dictate worker process "
            "(python3) in System Settings."
        ),
    )


def check_input_monitoring_permission() -> PermissionCheckResult:
    """Check Input Monitoring permission using a listen-only event tap probe.

    Parameters:
        None.

    Returns:
        PermissionCheckResult: Input Monitoring permission result.

    Raises:
        None.

    Example:
        ``result = check_input_monitoring_permission()``
    """

    if sys.platform != "darwin":
        return PermissionCheckResult(
            name="Input Monitoring",
            granted=False,
            state="unsupported",
            details="Input Monitoring preflight is only implemented for macOS.",
            remediation="Run this app on macOS.",
        )

    try:
        import Quartz  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on local environment.
        return PermissionCheckResult(
            name="Input Monitoring",
            granted=False,
            state="error",
            details=f"Unable to import Quartz: {exc}",
            remediation="Install macOS framework dependencies and retry.",
        )

    def _event_callback(proxy: object, event_type: object, event: object, refcon: object) -> object:
        """Pass through events for event tap probing."""

        return event

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        _event_callback,
        None,
    )

    if tap is None:
        return PermissionCheckResult(
            name="Input Monitoring",
            granted=False,
            state="denied",
            details="Input Monitoring permission is not granted.",
            remediation=(
                "Enable Input Monitoring for the Flow Dictate worker process "
                "(python3) in System Settings."
            ),
        )

    Quartz.CFMachPortInvalidate(tap)
    return PermissionCheckResult(
        name="Input Monitoring",
        granted=True,
        state="granted",
        details="Input Monitoring permission is granted.",
    )


def format_preflight_report(report: PermissionPreflightReport) -> str:
    """Format preflight output as user-readable text for CLI printing.

    Parameters:
        report: Permission preflight report to render.

    Returns:
        str: Multi-line text suitable for terminal output.

    Raises:
        None.

    Example:
        ``print(format_preflight_report(report))``
    """

    lines = ["Permission preflight:"]
    for result in (report.microphone, report.accessibility, report.input_monitoring):
        status = "OK" if result.granted else "NEEDS ACTION"
        line = f"- {result.name}: {status} ({result.state}) - {result.details}"
        lines.append(line)
        if result.remediation:
            lines.append(f"  Fix: {result.remediation}")

    summary = (
        "All required permissions are granted."
        if report.all_required_granted
        else "One or more required permissions are missing."
    )
    lines.append(summary)
    return "\n".join(lines)


def preflight_report_to_dict(report: PermissionPreflightReport) -> dict[str, Any]:
    """Convert a permission preflight report to a JSON-serializable dictionary.

    Parameters:
        report: Permission preflight report to serialize.

    Returns:
        dict[str, Any]: Machine-readable permission result payload.

    Raises:
        None.

    Example:
        ``payload = preflight_report_to_dict(report)``
    """

    return {
        "all_required_granted": report.all_required_granted,
        "microphone": asdict(report.microphone),
        "accessibility": asdict(report.accessibility),
        "input_monitoring": asdict(report.input_monitoring),
    }
