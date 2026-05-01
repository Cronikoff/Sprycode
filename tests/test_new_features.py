"""
Tests for new SpryCode features:
- for / while loops
- break / continue
- pipeline filter / map / each correctness
- create file statement
- compress / extract operations
- test blocks and expect assertions
- string methods
- list methods
- sleep statement
- schedule statement
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.permissions import PermissionSet
from sprycode.runtime.stdlib import SpryLogger, SpryResult


def run(source: str, permissions: PermissionSet | None = None, log_output: list | None = None) -> Interpreter:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    log_out = log_output if log_output is not None else []
    logger = SpryLogger(output=log_out)
    perms = permissions or PermissionSet()
    interp = Interpreter(logger=logger, permissions=perms)
    interp.run(program)
    return interp


def eval_expr(source: str) -> object:
    full = f"let __result = {source}"
    interp = run(full)
    return interp.globals.get("__result")


# ---------------------------------------------------------------------------
# For loops
# ---------------------------------------------------------------------------


class TestForLoop:
    def test_basic_for_loop(self):
        source = """
var total = 0
let nums = [1, 2, 3, 4, 5]
for n in nums {
    total = total + n
}
"""
        interp = run(source)
        assert interp.globals.get("total") == 15

    def test_for_loop_string(self):
        source = """
var count = 0
let items = ["a", "b", "c"]
for item in items {
    count = count + 1
}
"""
        interp = run(source)
        assert interp.globals.get("count") == 3

    def test_for_loop_variable_scope(self):
        """Loop variable should be accessible inside body."""
        source = """
var last = ""
let items = ["x", "y", "z"]
for item in items {
    last = item
}
"""
        interp = run(source)
        assert interp.globals.get("last") == "z"

    def test_for_loop_break(self):
        source = """
var found = false
let items = [1, 2, 3, 4, 5]
for n in items {
    if n == 3 {
        found = true
        break
    }
}
"""
        interp = run(source)
        assert interp.globals.get("found") is True

    def test_for_loop_continue(self):
        source = """
var total = 0
let nums = [1, 2, 3, 4, 5]
for n in nums {
    if n == 3 {
        continue
    }
    total = total + n
}
"""
        interp = run(source)
        # Sum of 1+2+4+5 = 12 (skip 3)
        assert interp.globals.get("total") == 12

    def test_for_loop_empty_list(self):
        source = """
var count = 0
let items = []
for item in items {
    count = count + 1
}
"""
        interp = run(source)
        assert interp.globals.get("count") == 0

    def test_for_loop_non_iterable_raises(self):
        source = """
for x in 42 {
    let y = x
}
"""
        with pytest.raises((SpryRuntimeError, Exception)):
            run(source)


# ---------------------------------------------------------------------------
# While loops
# ---------------------------------------------------------------------------


class TestWhileLoop:
    def test_basic_while(self):
        source = """
var count = 0
while count < 5 {
    count = count + 1
}
"""
        interp = run(source)
        assert interp.globals.get("count") == 5

    def test_while_false_never_runs(self):
        source = """
var ran = false
while false {
    ran = true
}
"""
        interp = run(source)
        assert interp.globals.get("ran") is False

    def test_while_break(self):
        source = """
var count = 0
while true {
    count = count + 1
    if count == 3 {
        break
    }
}
"""
        interp = run(source)
        assert interp.globals.get("count") == 3

    def test_while_continue(self):
        source = """
var count = 0
var total = 0
while count < 5 {
    count = count + 1
    if count == 3 {
        continue
    }
    total = total + count
}
"""
        interp = run(source)
        # 1 + 2 + 4 + 5 = 12 (skip when count==3)
        assert interp.globals.get("total") == 12


# ---------------------------------------------------------------------------
# Pipeline filter / map / each
# ---------------------------------------------------------------------------


class TestPipelineOperations:
    def test_pipeline_filter(self):
        source = """
let nums = [1, 2, 3, 4, 5, 6]
let evens = nums |> filter n => n % 2 == 0
"""
        interp = run(source)
        assert interp.globals.get("evens") == [2, 4, 6]

    def test_pipeline_map(self):
        source = """
let nums = [1, 2, 3]
let doubled = nums |> map n => n * 2
"""
        interp = run(source)
        assert interp.globals.get("doubled") == [2, 4, 6]

    def test_pipeline_each_is_side_effect(self):
        """each should not transform the list — value should pass through unchanged."""
        log_output = []
        source = """
let nums = [1, 2, 3]
let result = nums |> each n => log info n
"""
        interp = run(source, log_output=log_output)
        # result should be the original list (each is side-effect only)
        assert interp.globals.get("result") == [1, 2, 3]
        assert len(log_output) == 3

    def test_pipeline_filter_then_map(self):
        source = """
let nums = [1, 2, 3, 4, 5]
let result = nums |> filter n => n > 2 |> map n => n * 10
"""
        interp = run(source)
        assert interp.globals.get("result") == [30, 40, 50]

    def test_pipeline_map_strings(self):
        source = """
let words = ["hello", "world"]
let uppers = words |> map w => w.upper
"""
        interp = run(source)
        assert interp.globals.get("uppers") == ["HELLO", "WORLD"]


# ---------------------------------------------------------------------------
# Create file statement
# ---------------------------------------------------------------------------


class TestCreateStatement:
    def test_create_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = str(Path(tmpdir) / "new.txt")
            source = f"""
allow filesystem.write "{tmpdir}"
create file "{filepath}" with "created content"
"""
            run(source)
            assert Path(filepath).exists()
            assert Path(filepath).read_text() == "created content"

    def test_create_file_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = str(Path(tmpdir) / "empty.txt")
            source = f"""
allow filesystem.write "{tmpdir}"
create file "{filepath}"
"""
            run(source)
            assert Path(filepath).exists()
            assert Path(filepath).read_text() == ""

    def test_create_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folderpath = str(Path(tmpdir) / "newdir")
            source = f"""
allow filesystem.write "{tmpdir}"
create folder "{folderpath}"
"""
            run(source)
            assert Path(folderpath).is_dir()


# ---------------------------------------------------------------------------
# Compress / extract operations
# ---------------------------------------------------------------------------


class TestCompressExtract:
    def test_compress_and_extract_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "source"
            src_dir.mkdir()
            (src_dir / "file1.txt").write_text("hello")
            (src_dir / "file2.txt").write_text("world")
            archive = str(Path(tmpdir) / "archive.zip")
            extract_dir = str(Path(tmpdir) / "extracted")

            source = f"""
allow filesystem.read "{tmpdir}"
allow filesystem.write "{tmpdir}"
compress folder "{src_dir}" to "{archive}"
extract "{archive}" to "{extract_dir}"
"""
            run(source)
            assert Path(extract_dir).exists()


# ---------------------------------------------------------------------------
# Test blocks and expect assertions
# ---------------------------------------------------------------------------


class TestBlocks:
    def test_basic_test_block_passes(self):
        log_output = []
        source = """
test "simple truth" {
    expect true
}
"""
        interp = run(source, log_output=log_output)
        assert any("PASS" in line for line in log_output)

    def test_expect_false_fails(self):
        with pytest.raises(AssertionError):
            run("""
test "should fail" {
    expect false
}
""")

    def test_expect_not_false(self):
        log_output = []
        run("""
test "expect not false" {
    expect not false
}
""", log_output=log_output)
        assert any("PASS" in line for line in log_output)

    def test_expect_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "file.txt"
            f.write_text("hi")
            source = f"""
test "file exists" {{
    expect exists "{f}"
}}
"""
            log_output = []
            run(source, log_output=log_output)
            assert any("PASS" in line for line in log_output)

    def test_expect_not_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = str(Path(tmpdir) / "missing.txt")
            source = f"""
test "file does not exist" {{
    expect not exists "{missing}"
}}
"""
            log_output = []
            run(source, log_output=log_output)
            assert any("PASS" in line for line in log_output)

    def test_expect_denied(self):
        """expect denied block should catch PermissionError."""
        log_output = []
        perms = PermissionSet()
        perms.enable_secure_mode()
        # In secure mode, reading without allow should raise PermissionError
        source = """
test "permission denied" {
    expect denied {
        read file "/secret/file.txt"
    }
}
"""
        run(source, permissions=perms, log_output=log_output)
        assert any("PASS" in line for line in log_output)

    def test_expect_rollback(self):
        log_output = []
        source = """
test "rollback on error" {
    expect rollback {
        let x = 1 / 0
    }
}
"""
        run(source, log_output=log_output)
        assert any("PASS" in line for line in log_output)


# ---------------------------------------------------------------------------
# String methods
# ---------------------------------------------------------------------------


class TestStringMethods:
    def test_upper(self):
        assert eval_expr('"hello".upper') == "HELLO"

    def test_lower(self):
        assert eval_expr('"HELLO".lower') == "hello"

    def test_trim(self):
        assert eval_expr('"  hello  ".trim') == "hello"

    def test_length(self):
        assert eval_expr('"hello".length') == 5

    def test_is_empty_false(self):
        assert eval_expr('"hello".isEmpty') is False

    def test_is_empty_true(self):
        assert eval_expr('"".isEmpty') is True

    def test_split(self):
        interp = run('let parts = "a,b,c".split(",")')
        assert interp.globals.get("parts") == ["a", "b", "c"]

    def test_contains_true(self):
        interp = run('let has = "hello world".contains("world")')
        assert interp.globals.get("has") is True

    def test_contains_false(self):
        interp = run('let has = "hello world".contains("xyz")')
        assert interp.globals.get("has") is False

    def test_starts_with_true(self):
        interp = run('let ok = "hello".startsWith("hel")')
        assert interp.globals.get("ok") is True

    def test_starts_with_false(self):
        interp = run('let ok = "hello".startsWith("world")')
        assert interp.globals.get("ok") is False

    def test_ends_with_true(self):
        interp = run('let ok = "hello".endsWith("llo")')
        assert interp.globals.get("ok") is True

    def test_replace(self):
        interp = run('let r = "hello world".replace("world", "SpryCode")')
        assert interp.globals.get("r") == "hello SpryCode"


# ---------------------------------------------------------------------------
# List methods
# ---------------------------------------------------------------------------


class TestListMethods:
    def test_length(self):
        assert eval_expr("[1, 2, 3].length") == 3

    def test_first(self):
        assert eval_expr("[10, 20, 30].first") == 10

    def test_last(self):
        assert eval_expr("[10, 20, 30].last") == 30

    def test_is_empty_false(self):
        assert eval_expr("[1].isEmpty") is False

    def test_is_empty_true(self):
        assert eval_expr("[].isEmpty") is True

    def test_includes_true(self):
        interp = run("let has = [1, 2, 3].includes(2)")
        assert interp.globals.get("has") is True

    def test_includes_false(self):
        interp = run("let has = [1, 2, 3].includes(99)")
        assert interp.globals.get("has") is False

    def test_join(self):
        interp = run('let s = ["a", "b", "c"].join(",")')
        assert interp.globals.get("s") == "a,b,c"

    def test_reverse(self):
        interp = run("let r = [1, 2, 3].reverse")
        assert interp.globals.get("r") == [3, 2, 1]

    def test_push_and_length(self):
        source = """
var items = [1, 2]
items.push(3)
let size = items.length
"""
        interp = run(source)
        assert interp.globals.get("size") == 3


# ---------------------------------------------------------------------------
# Sleep statement
# ---------------------------------------------------------------------------


class TestSleepStatement:
    def test_sleep_zero(self):
        """sleep 0 should not error."""
        run("sleep 0")

    def test_sleep_expression(self):
        """sleep with a variable should work."""
        run("let delay = 0\nsleep delay")


# ---------------------------------------------------------------------------
# Schedule statement
# ---------------------------------------------------------------------------


class TestScheduleStatement:
    def test_schedule_logs(self):
        log_output = []
        run('schedule daily at "02:00"', log_output=log_output)
        assert any("schedule" in line.lower() or "daily" in line.lower() for line in log_output)
