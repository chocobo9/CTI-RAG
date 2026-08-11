"""Read-only, deterministic projection into TRAIL's five-node graph schema."""

from .builder import BuildPolicy, DatasetManifest, SourceRoots, build_dataset

__all__ = ["BuildPolicy", "DatasetManifest", "SourceRoots", "build_dataset"]
