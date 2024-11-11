# Extract LLVM IR and CFG from C/C++ and Python Source Code

This is a simple tool to extract LLVM IR from C/C++ and Python source code. It uses Clang to extract LLVM IR from C/C++ source code and uses Codon to extract LLVM IR from Python source code. It also extracts the control flow graph (CFG) from the LLVM IR.

The extracted CFG can be visualized as PDF or PNG files.

## Running the program

```bash
python3 main.py <source_file> --cfg_format <cfg_output_file_format>
```

## Contributors

- [Felix Hirwa Nshuti](https://github.com/fnhirwa)
- [Mellisa A. Gblinwon](https://github.com/MELISSAGBLINWON)
