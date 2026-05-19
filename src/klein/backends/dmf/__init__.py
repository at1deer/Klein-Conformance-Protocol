"""Generic DMF backend adapter skeleton."""

from klein.backends.dmf.adapter import AdapterRunResult, DmfBackendAdapterProtocol
from klein.backends.dmf.config import (
    DmfAdapterError,
    DmfAdapterValidationResult,
    load_dmf_backend_adapter_config,
    validate_dmf_backend_adapter_config,
    validate_dmf_backend_adapter_status,
)
from klein.backends.dmf.dry_run import GenericDmfDryRunAdapter

__all__ = [
    "AdapterRunResult",
    "DmfAdapterError",
    "DmfAdapterValidationResult",
    "DmfBackendAdapterProtocol",
    "GenericDmfDryRunAdapter",
    "load_dmf_backend_adapter_config",
    "validate_dmf_backend_adapter_config",
    "validate_dmf_backend_adapter_status",
]
