"""Intermediate dataset contract helpers."""

from __future__ import annotations

from rag_cti.intermediate.contract import (
    CONTRACT_ID_LENGTH,
    CONTROLLED_VOCABULARIES,
    contract_id,
)
from rag_cti.intermediate.delivery import (
    DeliveryAssemblyError,
    DeliveryBuildResult,
    DeliveryRows,
    assemble_intermediate_delivery_package,
    build_intermediate_delivery_package,
)
from rag_cti.intermediate.infrastructure import (
    InfrastructureRawRef,
    InfrastructureRows,
    build_infrastructure_intermediate_package,
    transform_pdns_record,
    transform_vt_payload,
)
from rag_cti.intermediate.jsonl import write_jsonl
from rag_cti.intermediate.mitre import (
    MITRERawRef,
    MITRERows,
    build_mitre_intermediate_package,
    transform_mitre_object,
    transform_mitre_relationship,
)
from rag_cti.intermediate.otx import (
    OTXRows,
    RawRef,
    build_otx_intermediate_package,
    transform_otx_pulse,
)
from rag_cti.intermediate.otx_downstream import (
    OTXDownstreamProjectionResult,
    build_otx_downstream_projection,
    load_otx_raw_observations,
)
from rag_cti.intermediate.projections import (
    project_delivery_to_gnn_smoke,
    project_delivery_to_rag_smoke,
)
from rag_cti.intermediate.validation import ValidationMessage, ValidationResult, validate_delivery

__all__ = [
    "CONTRACT_ID_LENGTH",
    "CONTROLLED_VOCABULARIES",
    "DeliveryAssemblyError",
    "DeliveryBuildResult",
    "DeliveryRows",
    "InfrastructureRawRef",
    "InfrastructureRows",
    "MITRERawRef",
    "MITRERows",
    "OTXRows",
    "OTXDownstreamProjectionResult",
    "RawRef",
    "ValidationMessage",
    "ValidationResult",
    "assemble_intermediate_delivery_package",
    "build_intermediate_delivery_package",
    "build_infrastructure_intermediate_package",
    "build_mitre_intermediate_package",
    "build_otx_intermediate_package",
    "build_otx_downstream_projection",
    "contract_id",
    "project_delivery_to_gnn_smoke",
    "project_delivery_to_rag_smoke",
    "load_otx_raw_observations",
    "transform_mitre_object",
    "transform_mitre_relationship",
    "transform_otx_pulse",
    "transform_pdns_record",
    "transform_vt_payload",
    "validate_delivery",
    "write_jsonl",
]
