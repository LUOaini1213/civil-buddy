"""Deterministic CAD preview geometry; optional dependencies load on demand."""

from .geometry import CAD3DError, build_model, export_glb, inspect_dxf

__all__ = ["CAD3DError", "inspect_dxf", "build_model", "export_glb"]
