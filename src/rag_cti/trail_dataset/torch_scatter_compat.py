"""Install a narrow ``torch_scatter.segment_csr`` fallback when unavailable."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import torch


def segment_csr(
    source: torch.Tensor, pointer: torch.Tensor, reduce: str = "sum"
) -> torch.Tensor:
    """Compatibility implementation backed by native ``torch.segment_reduce``."""

    normalized = "sum" if reduce == "add" else reduce
    if normalized not in {"sum", "mean", "max", "min"}:
        raise ValueError(f"unsupported segment reduction: {reduce}")
    return torch.segment_reduce(
        source,
        reduce=normalized,
        offsets=pointer.to(device=source.device, dtype=torch.long),
    )


def ensure_torch_scatter() -> bool:
    """Return True when the fallback was installed, False for the real package."""

    if importlib.util.find_spec("torch_scatter") is not None:
        return False
    module = ModuleType("torch_scatter")
    module.segment_csr = segment_csr  # type: ignore[attr-defined]
    sys.modules["torch_scatter"] = module
    return True

