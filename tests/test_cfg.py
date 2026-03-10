# noqa
"""Tests for struco.cfg module."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from struco.cfg import (
    EXTENSION_TO_LANGUAGE,
    IRResult,
    Language,
    _convert_dot,
    _get_frontend_config,
    _run_frontend,
    _run_opt,
    extract_cfg_from_ir,
    extract_ir,
    get_function_names,
)


# Language enum and extension mapping
class TestLanguageMapping:
    def test_all_extensions_mapped(self):
        assert set(EXTENSION_TO_LANGUAGE.keys()) == {"c", "cpp", "cxx", "py"}

    def test_c_maps_to_c(self):
        assert EXTENSION_TO_LANGUAGE["c"] == Language.C

    def test_cpp_maps_to_cpp(self):
        assert EXTENSION_TO_LANGUAGE["cpp"] == Language.CPP

    def test_cxx_maps_to_cxx(self):
        assert EXTENSION_TO_LANGUAGE["cxx"] == Language.CXX

    def test_py_maps_to_python(self):
        assert EXTENSION_TO_LANGUAGE["py"] == Language.PYTHON


# Frontend config
class TestFrontendConfig:
    def test_c_uses_clang(self):
        config = _get_frontend_config(Language.C)
        assert config.command == "clang"
        assert "-S" in config.args
        assert "-emit-llvm" in config.args

    def test_cpp_uses_clangpp(self):
        config = _get_frontend_config(Language.CPP)
        assert config.command == "clang++"

    def test_cxx_uses_clangpp(self):
        config = _get_frontend_config(Language.CXX)
        assert config.command == "clang++"

    def test_python_uses_codon(self):
        config = _get_frontend_config(Language.PYTHON)
        assert config.command == "codon"
        assert "build" in config.args
        assert "-llvm" in config.args


# extract_ir validation
class TestExtractIRValidation:
    def test_unsupported_extension_raises(self, tmp_path: Path):
        bad_file = tmp_path / "hello.java"
        bad_file.touch()
        with pytest.raises(ValueError, match="Unsupported file extension"):
            extract_ir(bad_file)

    def test_missing_file_raises(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.c"
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            extract_ir(missing)

    def test_accepts_string_path(self, tmp_path: Path):
        """extract_ir should accept str paths, not just Path objects."""
        missing = tmp_path / "nonexistent.c"
        with pytest.raises(FileNotFoundError):
            extract_ir(str(missing))

    def test_path_with_multiple_dots(self, tmp_path: Path):
        """Regression: file_path.split('.') broke on paths like 'my.test.c'."""
        dotted = tmp_path / "my.test.c"
        dotted.touch()
        # Should not raise ValueError — the extension is correctly parsed as 'c'
        with patch("struco.cfg._run_frontend") as mock_run:
            mock_run.return_value = IRResult(
                ir_path=tmp_path / "my.test_c.ll", language=Language.C
            )
            result = extract_ir(dotted)
            assert result.language == Language.C


# _run_frontend
class TestRunFrontend:
    @patch("struco.cfg.subprocess.run")
    def test_c_file_produces_correct_output_name(self, mock_run: MagicMock, tmp_path: Path):
        source = tmp_path / "hello.c"
        source.write_text("int main() { return 0; }")

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        # Simulate the .ll file being created by the compiler
        expected_ll = tmp_path / "hello_c.ll"
        expected_ll.write_text("fake IR")

        ll_dir = tmp_path / "hello_c_ll_files"
        ll_dir.mkdir()

        result = _run_frontend(source, Language.C)

        assert result.language == Language.C
        assert result.ir_path.name == "hello_c.ll"
        assert result.ir_path.parent.name == "hello_c_ll_files"

    @patch("struco.cfg.subprocess.run")
    def test_subprocess_called_without_shell(self, mock_run: MagicMock, tmp_path: Path):
        source = tmp_path / "hello.c"
        source.write_text("int main() {}")
        expected_ll = tmp_path / "hello_c.ll"
        expected_ll.write_text("fake")
        (tmp_path / "hello_c_ll_files").mkdir()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        _run_frontend(source, Language.C)

        call_args = mock_run.call_args
        # First positional arg is the command list
        cmd = call_args[0][0]
        assert isinstance(cmd, list), "subprocess should receive a list, not a string"
        assert cmd[0] == "clang"
        # Verify shell=False (check=False is explicit, shell should not be True)
        assert call_args[1].get("shell") is not True

    @patch("struco.cfg.subprocess.run")
    def test_compiler_failure_raises_runtime_error(self, mock_run: MagicMock, tmp_path: Path):
        source = tmp_path / "bad.c"
        source.write_text("this is not valid c")

        mock_run.return_value = MagicMock(
            returncode=1, stderr="error: expected identifier", stdout=""
        )

        with pytest.raises(RuntimeError, match="Frontend compilation failed"):
            _run_frontend(source, Language.C)

    @patch("struco.cfg.subprocess.run")
    def test_python_file_uses_codon(self, mock_run: MagicMock, tmp_path: Path):
        source = tmp_path / "hello.py"
        source.write_text("print('hello')")
        expected_ll = tmp_path / "hello_py.ll"
        expected_ll.write_text("fake")
        (tmp_path / "hello_py_ll_files").mkdir()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        _run_frontend(source, Language.PYTHON)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "codon"

    @patch("struco.cfg.subprocess.run")
    def test_cpp_file_uses_clangpp(self, mock_run: MagicMock, tmp_path: Path):
        source = tmp_path / "hello.cpp"
        source.write_text("int main() {}")
        expected_ll = tmp_path / "hello_cpp.ll"
        expected_ll.write_text("fake")
        (tmp_path / "hello_cpp_ll_files").mkdir()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        _run_frontend(source, Language.CPP)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "clang++"


# IRResult dataclass-
class TestIRResult:
    def test_frozen(self):
        r = IRResult(ir_path=Path("/tmp/test.ll"), language=Language.C)
        with pytest.raises(AttributeError):
            r.ir_path = Path("/tmp/other.ll")  # type: ignore[misc]

    def test_equality(self):
        a = IRResult(ir_path=Path("/tmp/test.ll"), language=Language.C)
        b = IRResult(ir_path=Path("/tmp/test.ll"), language=Language.C)
        assert a == b


# get_function_names
SAMPLE_C_IR = textwrap.dedent("""\
    ; ModuleID = 'hello.c'
    source_filename = "hello.c"

    define dso_local i32 @main() #0 {
    entry:
      ret i32 0
    }

    define dso_local i32 @binary_search(i32* %arr, i32 %n, i32 %target) #0 {
    entry:
      ret i32 -1
    }

    declare i32 @printf(i8*, ...) #1
""")

SAMPLE_CPP_IR = textwrap.dedent("""\
    ; ModuleID = 'hello.cpp'
    source_filename = "hello.cpp"

    define dso_local i32 @_Z13binary_searchPiii(i32* %arr, i32 %n, i32 %target) #0 {
    entry:
      ret i32 -1
    }

    define dso_local i32 @main() #0 {
    entry:
      ret i32 0
    }
""")


class TestGetFunctionNames:
    def test_c_ir_extracts_functions(self, tmp_path: Path):
        ir_file = tmp_path / "hello_c.ll"
        ir_file.write_text(SAMPLE_C_IR)

        names = get_function_names(ir_file, Language.C)
        assert "main" in names
        assert "binary_search" in names
        # declare (not define) should not appear
        assert "printf" not in names

    def test_cpp_ir_extracts_mangled_names(self, tmp_path: Path):
        ir_file = tmp_path / "hello_cpp.ll"
        ir_file.write_text(SAMPLE_CPP_IR)

        names = get_function_names(ir_file, Language.CPP)
        assert "_Z13binary_searchPiii" in names
        assert "main" in names

    def test_missing_ir_file_raises(self, tmp_path: Path):
        missing = tmp_path / "missing.ll"
        with pytest.raises(FileNotFoundError, match="IR file not found"):
            get_function_names(missing, Language.C)

    def test_empty_ir_returns_empty_list(self, tmp_path: Path):
        ir_file = tmp_path / "empty.ll"
        ir_file.write_text("; empty module\n")

        names = get_function_names(ir_file, Language.C)
        assert names == []

    def test_python_ir_uses_simple_pattern(self, tmp_path: Path):
        ir_file = tmp_path / "hello_py.ll"
        ir_file.write_text(
            "define i64 @binary_search(i64* %arr, i64 %n, i64 %target) {\n"
            "entry:\n  ret i64 -1\n}\n"
        )

        names = get_function_names(ir_file, Language.PYTHON)
        assert "binary_search" in names


# _run_opt
class TestRunOpt:
    @patch("struco.cfg.subprocess.run")
    def test_success(self, mock_run: MagicMock, tmp_path: Path):
        ir_file = tmp_path / "test.ll"
        ir_file.write_text("fake")

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr="Writing '.main.dot'...\nWriting '.foo.dot'...\n",
            stdout="",
        )

        # Should not raise
        _run_opt(ir_file)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "opt"
        assert "-passes=dot-cfg" in cmd

    @patch("struco.cfg.subprocess.run")
    def test_failure_raises(self, mock_run: MagicMock, tmp_path: Path):
        ir_file = tmp_path / "test.ll"
        ir_file.write_text("fake")

        mock_run.return_value = MagicMock(
            returncode=1, stderr="error: expected instruction", stdout=""
        )

        with pytest.raises(RuntimeError, match="opt failed"):
            _run_opt(ir_file)


# _convert_dot
class TestConvertDot:
    @patch("struco.cfg.subprocess.run")
    def test_png_conversion(self, mock_run: MagicMock, tmp_path: Path):
        dot_file = tmp_path / ".main.dot"
        dot_file.write_text("digraph { a -> b }")
        output_dir = tmp_path / "images"
        output_dir.mkdir()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = _convert_dot(dot_file, output_dir, "png")

        assert result is not None
        assert result.name == "main.png"
        assert result.parent == output_dir

    @patch("struco.cfg.subprocess.run")
    def test_pdf_conversion(self, mock_run: MagicMock, tmp_path: Path):
        dot_file = tmp_path / ".foo.dot"
        dot_file.write_text("digraph { a -> b }")
        output_dir = tmp_path / "pdfs"
        output_dir.mkdir()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = _convert_dot(dot_file, output_dir, "pdf")

        assert result is not None
        assert result.name == "foo.pdf"

    @patch("struco.cfg.subprocess.run")
    def test_graphviz_failure_returns_none(self, mock_run: MagicMock, tmp_path: Path):
        dot_file = tmp_path / ".bad.dot"
        dot_file.write_text("not valid dot")
        output_dir = tmp_path / "images"
        output_dir.mkdir()

        mock_run.return_value = MagicMock(returncode=1, stderr="Error: syntax error", stdout="")

        result = _convert_dot(dot_file, output_dir, "png")
        assert result is None


# extract_cfg_from_ir validation
class TestExtractCfgValidation:
    def test_missing_ir_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="IR file not found"):
            extract_cfg_from_ir(tmp_path / "missing.ll")

    def test_invalid_format_raises(self, tmp_path: Path):
        ir_file = tmp_path / "test.ll"
        ir_file.write_text("fake")
        with pytest.raises(ValueError, match="Invalid output format"):
            extract_cfg_from_ir(ir_file, output_format="svg")

    def test_accepts_string_path(self, tmp_path: Path):
        ir_file = tmp_path / "test.ll"
        ir_file.write_text("fake")
        with pytest.raises(ValueError, match="Invalid output format"):
            extract_cfg_from_ir(str(ir_file), output_format="bmp")

    def test_accepts_language_as_string(self, tmp_path: Path):
        """Language parameter should accept raw strings like 'c', 'cpp'."""
        ir_file = tmp_path / "test.ll"
        ir_file.write_text(SAMPLE_C_IR)

        with (
            patch("struco.cfg._run_opt"),
            patch("struco.cfg.Path.cwd") as mock_cwd,
            patch("struco.cfg.Path.iterdir", return_value=iter([])),
        ):
            mock_cwd.return_value = tmp_path
            # Should not raise even though language is a string
            extract_cfg_from_ir(ir_file, language="c", output_format="png")


# Regression tests
class TestRegressions:
    def test_path_with_dots_in_directory(self, tmp_path: Path):
        """Paths like /home/user/my.project/src/hello.c must work."""
        dotted_dir = tmp_path / "my.project" / "src"
        dotted_dir.mkdir(parents=True)
        source = dotted_dir / "hello.c"
        source.write_text("int main() {}")

        # extract_ir should parse extension correctly
        with patch("struco.cfg._run_frontend") as mock_run:
            mock_run.return_value = IRResult(
                ir_path=dotted_dir / "hello_c.ll", language=Language.C
            )
            result = extract_ir(source)
            assert result.language == Language.C
            # Verify _run_frontend was called with resolved absolute path
            call_path = mock_run.call_args[0][0]
            assert call_path.is_absolute()

    def test_function_names_pattern_c_does_not_match_declarations(self, tmp_path: Path):
        """Regex should only match 'define', not 'declare'."""
        ir_file = tmp_path / "test.ll"
        ir_file.write_text(
            "declare i32 @printf(i8*, ...)\ndefine i32 @main() {\nentry:\n  ret i32 0\n}\n"
        )
        names = get_function_names(ir_file, Language.C)
        assert "printf" not in names
        assert "main" in names
