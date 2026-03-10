"""CLI entry point for struco.

Usage:
    python -m struco <file_path> [--cfg_format png|pdf] [-v]
"""

from __future__ import annotations

import argparse
import logging
import sys

from struco.cfg import extract_cfg_from_ir, extract_ir


def main() -> int:
    """Run IR extraction and CFG generation from the command line."""
    parser = argparse.ArgumentParser(
        description="Extract LLVM IR and CFG from C, C++, and Python source files.",
    )
    parser.add_argument(
        "file_path",
        type=str,
        help="Path to the source file (.c, .cpp, .cxx, or .py)",
    )
    parser.add_argument(
        "--cfg_format",
        type=str,
        choices=["png", "pdf"],
        default="png",
        help="Output format for CFG visualization (default: png)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s | %(levelname)s | %(message)s",
    )

    try:
        ir_result = extract_ir(args.file_path)
        outputs = extract_cfg_from_ir(
            ir_result.ir_path,
            language=ir_result.language,
            output_format=args.cfg_format,
        )
        for path in outputs:
            print(path)  # noqa: T201
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
