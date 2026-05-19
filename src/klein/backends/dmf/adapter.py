"""DMF backend adapter protocol and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class AdapterRunResult:
    ok: bool
    run_id: str
    trace: dict[str, Any]
    raw_events: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    hil_contract: dict[str, Any]
    hil_status: dict[str, Any]
    output_dir: Path | None = None
    error_code: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class DmfBackendAdapterProtocol(Protocol):
    def status(self) -> dict[str, Any]:
        ...

    def emergency_stop(self) -> dict[str, Any]:
        ...

    def reset(self) -> dict[str, Any]:
        ...

    def run_runbook_dry(self, runbook: dict[str, Any], *, output_dir: str | Path | None = None) -> AdapterRunResult:
        ...
