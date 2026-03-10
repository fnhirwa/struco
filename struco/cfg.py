"""IR extraction and CFG generation from C/C++ and Python source files.

Uses Clang for C/C++, Codon for Python. Generates LLVM IR and extracts
Control Flow Graphs via LLVM's opt tool.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported source languages."""

    C = "c"
    CPP = "cpp"
    CXX = "cxx"
    PYTHON = "py"


EXTENSION_TO_LANGUAGE: dict[str, Language] = {
    "c": Language.C,
    "cpp": Language.CPP,
    "cxx": Language.CXX,
    "py": Language.PYTHON,
}

# Languages that use the C-family frontend (Clang)
_C_FAMILY = {Language.C, Language.CPP, Language.CXX}


@dataclass(frozen=True)
class IRResult:
    """Result of IR extraction.

    Attributes
    ----------
    ir_path : Path
        Absolute path to the generated .ll file.
    language : Language
        The source language that produced this IR.
    """

    ir_path: Path
    language: Language


@dataclass(frozen=True)
class FrontendConfig:
    """Configuration for a compiler frontend.

    Attributes
    ----------
    command : str
        The compiler executable name.
    args : list[str]
        Arguments to emit LLVM IR.
    """

    command: str
    args: list[str]


def _get_frontend_config(language: Language) -> FrontendConfig:
    """Return the compiler command and flags for a given language.

    Parameters
    ----------
    language : Language
        The source language.

    Returns
    -------
    FrontendConfig
        The compiler executable and arguments.
    """
    if language == Language.C:
        return FrontendConfig(
            command="clang",
            args=["-S", "-emit-llvm", "-Xclang", "-disable-O0-optnone"],
        )
    if language in {Language.CPP, Language.CXX}:
        return FrontendConfig(
            command="clang++",
            args=["-S", "-emit-llvm", "-Xclang", "-disable-O0-optnone"],
        )
    if language == Language.PYTHON:
        return FrontendConfig(
            command="codon",
            args=["build", "-release", "-llvm"],
        )
    msg = f"Unsupported language: {language}"
    raise ValueError(msg)


def _run_frontend(
    source_path: Path,
    language: Language,
) -> IRResult:
    """Compile a source file to LLVM IR using the appropriate frontend.

    Runs the compiler subprocess, places the .ll output in a dedicated
    directory alongside the source file, and returns the result.

    Parameters
    ----------
    source_path : Path
        Absolute path to the source file.
    language : Language
        The source language.

    Returns
    -------
    IRResult
        Path to the generated IR and the source language.

    Raises
    ------
    FileNotFoundError
        If the source file does not exist.
    RuntimeError
        If the compiler subprocess fails.
    """
    if not source_path.exists():
        msg = f"Source file not found: {source_path}"
        raise FileNotFoundError(msg)

    config = _get_frontend_config(language)

    # Build output path: e.g. /path/to/hello_c.ll
    stem = source_path.stem
    ext = source_path.suffix.lstrip(".")
    output_file = source_path.with_name(f"{stem}_{ext}.ll")

    # Build command
    cmd: list[str] = [config.command, *config.args, str(source_path), "-o", str(output_file)]

    logger.info("Running frontend: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.error("Frontend stderr: %s", result.stderr)
        msg = f"Frontend compilation failed for {source_path}: {result.stderr}"
        raise RuntimeError(msg)

    if result.stderr:
        logger.warning("Frontend warnings: %s", result.stderr)

    # Move .ll file into a dedicated directory
    ll_dir = source_path.parent / f"{stem}_{ext}_ll_files"
    ll_dir.mkdir(parents=True, exist_ok=True)

    dest = ll_dir / output_file.name
    output_file.rename(dest)

    logger.info("IR written to %s", dest)
    return IRResult(ir_path=dest, language=language)


def extract_ir(file_path: str | Path) -> IRResult:
    """Extract LLVM IR from a source file.

    Dispatches to the appropriate compiler frontend based on file extension.

    Parameters
    ----------
    file_path : str or Path
        Path to the source file (C, C++, or Python).

    Returns
    -------
    IRResult
        The path to the generated .ll file and the source language.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    FileNotFoundError
        If the source file does not exist.
    RuntimeError
        If compilation fails.
    """
    source_path = Path(file_path).resolve()
    ext = source_path.suffix.lstrip(".")

    language = EXTENSION_TO_LANGUAGE.get(ext)
    if language is None:
        supported = ", ".join(sorted(EXTENSION_TO_LANGUAGE.keys()))
        msg = f"Unsupported file extension '.{ext}'. Supported: {supported}"
        raise ValueError(msg)

    return _run_frontend(source_path, language)


# Regex patterns for extracting function names from LLVM IR
_FUNC_PATTERN_SIMPLE = re.compile(r"define\s+(?:\w+\s+)*@(\w+)\s*\(")

_FUNC_PATTERN_CPP = re.compile(
    r"define\s+"
    r"(?:(?:internal|private|available_externally|linkonce"
    r"|weak|common|appending|extern_weak|linkonce_odr|weak_odr|external)\s+)?"
    r"(?:(?:dso_local|dso_preemptable)\s+)?"
    r"(?:\w+\s+)*"
    r"@([\w$.]+)\s*\("
    r"[^)]*\)"
    r"(?:\s*(?:#\d+|![^\n]+|\{\s*[^}]*\}|\[[^\]]+\]|\w+\s*\([^)]*\)))*"
)


def _get_function_pattern(language: Language) -> re.Pattern[str]:
    """Return the regex pattern for function definitions in the given language's IR."""
    if language in {Language.CPP, Language.CXX}:
        return _FUNC_PATTERN_CPP
    return _FUNC_PATTERN_SIMPLE


def get_function_names(ir_path: Path, language: Language) -> list[str]:
    """Extract function names defined in an LLVM IR file.

    Parameters
    ----------
    ir_path : Path
        Path to the .ll file.
    language : Language
        The source language (affects regex pattern for C++ name mangling).

    Returns
    -------
    list[str]
        Function names found in the IR.

    Raises
    ------
    FileNotFoundError
        If the IR file does not exist.
    """
    if not ir_path.exists():
        msg = f"IR file not found: {ir_path}"
        raise FileNotFoundError(msg)

    pattern = _get_function_pattern(language)
    content = ir_path.read_text()
    functions = pattern.findall(content)
    logger.info("Found %d functions in %s", len(functions), ir_path.name)
    return functions


def _run_opt(ir_path: Path) -> None:
    """Run LLVM opt to generate .dot CFG files.

    The opt tool writes .dot files to the current working directory.
    We run it with cwd set to a temporary location to control output.

    Parameters
    ----------
    ir_path : Path
        Absolute path to the .ll file.

    Raises
    ------
    RuntimeError
        If opt fails.
    """
    cmd = ["opt", "-passes=dot-cfg", "-disable-output", str(ir_path)]
    logger.info("Running opt: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    # opt writes "Writing '<filename>'..." to stderr on success
    if result.returncode != 0:
        logger.error("opt stderr: %s", result.stderr)
        msg = f"opt failed for {ir_path}: {result.stderr}"
        raise RuntimeError(msg)

    if result.stderr:
        non_writing = [line for line in result.stderr.splitlines() if "Writing" not in line]
        if non_writing:
            logger.warning("opt warnings: %s", "\n".join(non_writing))


def _convert_dot(
    dot_path: Path,
    output_dir: Path,
    fmt: str = "png",
) -> Path | None:
    """Convert a .dot file to PNG or PDF using Graphviz dot.

    Parameters
    ----------
    dot_path : Path
        Path to the .dot file.
    output_dir : Path
        Directory to write the output image/PDF.
    fmt : str
        Output format, either "png" or "pdf".

    Returns
    -------
    Path or None
        Path to the output file, or None if conversion failed.
    """
    # .dot filenames from opt look like: .funcname.dot
    # Extract function name: strip leading dot and .dot extension
    func_name = dot_path.stem.lstrip(".")
    output_path = output_dir / f"{func_name}.{fmt}"

    cmd = ["dot", f"-T{fmt}", str(dot_path), "-o", str(output_path)]
    logger.info("Converting %s -> %s", dot_path.name, output_path.name)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        logger.error("Graphviz error for %s: %s", dot_path.name, result.stderr)
        return None

    return output_path


def extract_cfg_from_ir(
    ir_path: str | Path,
    language: Language | str = Language.C,
    output_format: str = "png",
) -> list[Path]:
    """Extract CFGs from an LLVM IR file and render as PNG or PDF.

    Parameters
    ----------
    ir_path : str or Path
        Path to the .ll file.
    language : Language or str
        Source language (affects function name extraction).
    output_format : str
        Output format: "png" or "pdf".

    Returns
    -------
    list[Path]
        Paths to the generated image/PDF files.

    Raises
    ------
    FileNotFoundError
        If the IR file does not exist.
    ValueError
        If output_format is not "png" or "pdf".
    RuntimeError
        If opt or graphviz fails.
    """
    ir_path = Path(ir_path).resolve()

    if not ir_path.exists():
        msg = f"IR file not found: {ir_path}"
        raise FileNotFoundError(msg)

    output_format = output_format.lower()
    if output_format not in {"png", "pdf"}:
        msg = f"Invalid output format '{output_format}'. Must be 'png' or 'pdf'."
        raise ValueError(msg)

    # Normalize language to enum
    if isinstance(language, str):
        language = EXTENSION_TO_LANGUAGE.get(language, Language.C)

    # Run opt — .dot files land in cwd
    original_cwd = Path.cwd()
    try:
        _run_opt(ir_path)
    finally:
        os.chdir(original_cwd)

    # Set up output directories
    cfg_dir = ir_path.parent / f"{ir_path.stem}_cfg"
    output_dir = cfg_dir / f"{output_format}s"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find expected .dot files based on function names
    function_names = get_function_names(ir_path, language)
    expected_dots = {f".{name}.dot" for name in function_names}

    outputs: list[Path] = []
    cwd = Path.cwd()

    for item in cwd.iterdir():
        if item.name in expected_dots:
            # Move .dot into cfg directory
            dest_dot = cfg_dir / item.name
            item.rename(dest_dot)

            # Convert to output format
            result = _convert_dot(dest_dot, output_dir, output_format)
            if result is not None:
                outputs.append(result)

    logger.info(
        "Generated %d CFG %s files in %s",
        len(outputs),
        output_format.upper(),
        output_dir,
    )
    return outputs


__all__ = [
    "Language",
    "IRResult",
    "extract_ir",
    "extract_cfg_from_ir",
    "get_function_names",
]
