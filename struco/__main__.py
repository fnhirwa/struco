import argparse

from struco.cfg import extract_cfg_from_ir, extract_ir


def main():  # noqa
    parser = argparse.ArgumentParser(description="Extract CFG from a C file")
    parser.add_argument("file_path", type=str, help="Path to the C file")
    args = parser.parse_args()
    ir_file_path, source_extension = extract_ir(args.file_path)
    if ir_file_path:
        extract_cfg_from_ir(ir_file_path, source_file_extension=source_extension)


if __name__ == "__main__":
    main()
