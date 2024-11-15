import argparse

from struco.cfg import extract_cfg_from_ir, extract_ir


def main():  # noqa
    parser = argparse.ArgumentParser(description="Extract CFG from a C file")
    parser.add_argument("file_path", type=str, help="Path to the C file")
    parser.add_argument(
        "--cfg_format",
        type=str,
        help="The output format of the cfg either png or pdf",
        default="png",
    )
    args = parser.parse_args()
    ir_file_path, source_extension = extract_ir(args.file_path)
    if args.cfg_format.lower() not in ["png", "pdf"]:
        raise ValueError("Invalid cfg format. Must be either png or pdf")
    if ir_file_path:
        extract_cfg_from_ir(
            ir_file_path,
            source_file_extension=source_extension,
            file_option=args.cfg_format,
        )


if __name__ == "__main__":
    main()
