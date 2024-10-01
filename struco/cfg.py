import os
import subprocess
import re


def extract_c_ir(file_path, output_path=None, file_extension="c"):
    if not os.path.exists(file_path):
        print("File does not exist")
        return None
    if file_extension == "c":
        ir_cmd = f"clang -S -emit-llvm -Xclang -disable-O0-optnone {file_path}"
    if file_extension in ["cpp", "cxx"]:
        ir_cmd = f"clang++ -S -emit-llvm -Xclang -disable-O0-optnone {file_path}"
    file_name = file_path.split("/")[-1]
    output_file = file_name.split(".")[0] + ".ll"
    if output_path:
        output_file = output_path + "/" + output_file
    else:
        file_path, file_extension = file_path.split(".")
        output_file = f"{file_path}_{file_extension}.ll"

    ir_cmd += " -o " + output_file

    ir_process = subprocess.Popen(
        ir_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout_ir, stderr_ir = ir_process.communicate()
    if stderr_ir:
        print("Error: ", stderr_ir)
        return None
    print(stdout_ir)
    # create a directory for ll files
    source_file_dir_name = os.path.dirname(file_path)
    source_file_name = os.path.basename(file_path)

    ll_file_dir_name = f"{source_file_name}_{file_extension}_ll_files"
    ll_files_dir = os.path.join(source_file_dir_name, ll_file_dir_name)
    os.makedirs(ll_files_dir, exist_ok=True)
    # move the output_file to ll_files_dir
    file_name = output_file.split("/")[-1]
    new_out_file = os.path.join(ll_files_dir, file_name)
    os.rename(output_file, new_out_file)
    return str(new_out_file), file_extension


def extract_py_ir(file_path, output_path=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError("File does not exist")
    ir_cmd = f"codon build -release -llvm {file_path}"
    file_name = file_path.split("/")[-1]
    output_file = file_name.split(".")[0] + ".ll"
    if output_path:
        output_file = output_path + "/" + output_file
    else:
        file_path, file_extension = file_path.split(".")
        output_file = f"{file_path}_{file_extension}.ll"
    ir_cmd += " -o " + output_file

    ir_process = subprocess.Popen(
        ir_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout_ir, stderr_ir = ir_process.communicate()
    if stderr_ir:
        print("Error: ", stderr_ir)
        return None
    print(stdout_ir)
    # create a directory for ll files
    source_file_dir_name = os.path.dirname(file_path)
    source_file_name = os.path.basename(file_path)

    ll_file_dir_name = f"{source_file_name}_{file_extension}_ll_files"
    ll_files_dir = os.path.join(source_file_dir_name, ll_file_dir_name)
    os.makedirs(ll_files_dir, exist_ok=True)
    # move the output_file to ll_files_dir
    file_name = output_file.split("/")[-1]
    new_out_file = os.path.join(ll_files_dir, file_name)
    os.rename(output_file, new_out_file)
    return str(new_out_file), file_extension


def extract_ir(file_path, output_path=None):
    file_extension = file_path.split(".")[-1]
    if file_extension == "c":
        return extract_c_ir(file_path, output_path=output_path, file_extension="c")
    elif file_extension in ["cpp", "cxx"]:
        return extract_c_ir(file_path, output_path=output_path, file_extension="cpp")
    elif file_extension == "py":
        return extract_py_ir(file_path, output_path)
    else:
        print("Unsupported file type")
        return None


def get_function_names_for_dot_cfg(ir_file_path, source_file_extension="c"):
    if not os.path.exists(ir_file_path):
        print("File does not exist")
        return None
    if source_file_extension == "c":
        function_pattern_c = re.compile(r"define\s+\w+\s+@(\w+)\s*\(")
    if source_file_extension in ["cpp", "cxx"]:
        pattern = r"""define\s+(?:(?:internal|private|available_externally|linkonce|weak|common|appending|extern_weak|linkonce_odr|weak_odr|external)\s+)?(?:(?:dso_local|dso_preemptable)\s+)?(?:\w+\s+)*@([\w$.]+)\s*\([^)]*\)(?:\s*(?:#\d+|![^\n]+|\{\s*[^}]*\}|\[[^\]]+\]|\w+\s*\([^)]*\)))*"""
        function_pattern_c = re.compile(pattern)
    if source_file_extension == "py":
        function_pattern_c = re.compile(r"define\s+\w+\s+@(\w+)\s*\(")
    with open(ir_file_path, "r") as ir_file:
        content = ir_file.read()
        functions = function_pattern_c.findall(content)
    function_names = [f".{fname}.dot" for fname in functions]
    return function_names


def extract_cfg_from_ir(ir_file_path, file_option="png", source_file_extension="c"):
    if not os.path.exists(ir_file_path):
        print("File does not exist")
        return None

    # Use the full path to the IR file
    cmd = ["opt", "-passes=dot-cfg", "-disable-output", ir_file_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stderr and not all(
            "Writing" in line for line in result.stderr.splitlines()
        ):
            print("Error:", result.stderr)
            return None

        print(result.stdout)

    except Exception as e:
        print(f"Exception occurred: {e}")
        return None

    try:
        # Use the full path to the directory
        cfg_dir_name = os.path.basename(ir_file_path).split(".")[0] + "_cfg"
        cfg_files_dir = os.path.join(os.path.dirname(ir_file_path), cfg_dir_name)
        if file_option == "png":
            final_cfg_files_dir = os.path.join(cfg_files_dir, "images")
        else:
            final_cfg_files_dir = os.path.join(cfg_files_dir, "pdfs")

        os.makedirs(cfg_files_dir, exist_ok=True)
        os.makedirs(final_cfg_files_dir, exist_ok=True)
        # move .dot file from function names to cfg_files_dir
        function_names = get_function_names_for_dot_cfg(
            ir_file_path, source_file_extension=source_file_extension
        )
        for file in os.listdir(os.getcwd()):
            if os.path.basename(file) in function_names:
                dot_file = os.path.join(cfg_files_dir, file)
                os.rename(file, dot_file)
                convert_cfg_to_png_pdf(final_cfg_files_dir, dot_file, file_option)

    except Exception as e:
        print(f"Exception occurred: {e}")
        return None
    return function_names


def convert_cfg_to_png_pdf(final_cfg_files_dir, dot_file, file_option="png"):
    try:
        if file_option == "png":
            png_file = os.path.join(
                final_cfg_files_dir, dot_file.split(".")[1] + ".png"
            )
            cmd = ["dot", "-Tpng", dot_file, "-o", png_file]
            res = subprocess.run(cmd)
            if res.returncode != 0:
                print("Error converting .dot to .png")
                return None
        else:
            pdf_file = os.path.join(
                final_cfg_files_dir, dot_file.split(".")[1] + ".pdf"
            )
            cmd = ["dot", "-Tpdf", dot_file, "-o", pdf_file]
            res = subprocess.run(cmd)
            if res.returncode != 0:
                print("Error converting .dot to .pdf")
                return None
    except Exception as e:
        print(f"Exception occurred: {e}")
        return None

__all__ = ["extract_ir", "extract_cfg_from_ir"]