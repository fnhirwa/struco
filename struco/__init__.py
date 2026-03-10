"""Struco: structural code representation extraction and analysis."""

from struco.cfg import (
    IRResult,
    Language,
    extract_cfg_from_ir,
    extract_ir,
    get_function_names,
)

__all__ = [
    "IRResult",
    "Language",
    "extract_cfg_from_ir",
    "extract_ir",
    "get_function_names",
]
