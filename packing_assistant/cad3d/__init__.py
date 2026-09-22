"""Deterministic CAD preview geometry; optional dependencies load on demand."""

from .geometry import CAD3DError, analyze_document, build_model, export_glb, inspect_dxf

__all__ = ["CAD3DError", "inspect_dxf", "analyze_document", "build_model", "export_glb"]
