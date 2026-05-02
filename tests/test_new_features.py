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


# ---------------------------------------------------------------------------
# Compound assignment operators
# ---------------------------------------------------------------------------


class TestCompoundAssignment:
    def test_plus_eq(self):
        interp = run("var x = 10\nx += 5")
        assert interp.globals.get("x") == 15

    def test_minus_eq(self):
        interp = run("var x = 10\nx -= 3")
        assert interp.globals.get("x") == 7

    def test_star_eq(self):
        interp = run("var x = 4\nx *= 3")
        assert interp.globals.get("x") == 12

    def test_slash_eq(self):
        interp = run("var x = 10\nx /= 4")
        assert interp.globals.get("x") == 2.5

    def test_compound_chained(self):
        interp = run("var x = 10\nx += 5\nx -= 2\nx *= 3")
        assert interp.globals.get("x") == 39

    def test_compound_string_concat(self):
        interp = run('var s = "hello"\ns += " world"')
        assert interp.globals.get("s") == "hello world"

    def test_compound_in_loop(self):
        log_output = []
        run(
            "var total = 0\nfor i in [1, 2, 3, 4, 5] {\n    total += i\n}\nlog info total",
            log_output=log_output,
        )
        assert any("15" in line for line in log_output)


# ---------------------------------------------------------------------------
# Encode / Decode builtins in expression context
# ---------------------------------------------------------------------------


class TestEncodeDecodeExpressions:
    def test_encode_json_call_form(self):
        result = eval_expr('encode("json", {name: "Alice"})')
        import json
        assert json.loads(result) == {"name": "Alice"}

    def test_encode_base64_call_form(self):
        result = eval_expr('encode("base64", "hello")')
        import base64
        assert base64.b64decode(result).decode() == "hello"

    def test_decode_base64_call_form(self):
        result = eval_expr('decode("base64", "aGVsbG8=")')
        assert result == "hello"

    def test_encode_space_syntax(self):
        result = eval_expr('encode "base64" "hello"')
        import base64
        assert base64.b64decode(result).decode() == "hello"

    def test_encode_yaml(self):
        result = eval_expr('encode("yaml", {a: "1"})')
        assert "a:" in result
        assert "1" in result


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------


class TestYAMLParsing:
    def test_parse_yaml_simple(self):
        interp = run('let raw = "name: Alice"\nlet data = parse yaml raw')
        data = interp.globals.get("data")
        assert isinstance(data, dict)
        assert data.get("name") == "Alice"

    def test_parse_yaml_multiline(self):
        code = 'let raw = "name: Bob\\nage: 30"\nlet data = parse yaml raw'
        interp = run(code)
        data = interp.globals.get("data")
        assert isinstance(data, dict)
        assert data.get("name") == "Bob"

    def test_encode_decode_yaml_roundtrip(self):
        code = 'let obj = {key: "value", num: 42}\nlet yaml_str = encode("yaml", obj)\nlet back = parse yaml yaml_str'
        interp = run(code)
        back = interp.globals.get("back")
        assert isinstance(back, dict)
        assert back.get("key") == "value"


# ---------------------------------------------------------------------------
# str() and bool() built-ins
# ---------------------------------------------------------------------------


class TestBuiltinStrBool:
    def test_str_true(self):
        assert eval_expr("str(true)") == "true"

    def test_str_false(self):
        assert eval_expr("str(false)") == "false"

    def test_str_null(self):
        assert eval_expr("str(null)") == "null"

    def test_str_integer_float(self):
        assert eval_expr("str(42.0)") == "42"

    def test_str_real_float(self):
        assert eval_expr("str(3.14)") == "3.14"

    def test_bool_truthy(self):
        assert eval_expr("bool(1)") is True
        assert eval_expr("bool(42)") is True

    def test_bool_falsy(self):
        assert eval_expr("bool(0)") is False
        assert eval_expr("bool(0.0)") is False


# ---------------------------------------------------------------------------
# Auto-run main task
# ---------------------------------------------------------------------------


class TestAutoRunMain:
    def test_auto_run_main_no_top_level(self):
        log_output = []
        run('task main {\n    log info "ran"\n}', log_output=log_output)
        assert any("ran" in line for line in log_output)

    def test_auto_run_main_calls_helper(self):
        code = 'task helper {\n    log info "helper"\n}\ntask main {\n    helper()\n}'
        log_output = []
        run(code, log_output=log_output)
        assert any("helper" in line for line in log_output)

    def test_no_auto_run_when_top_level_code(self):
        """When there's top-level code, main is NOT auto-run."""
        log_output = []
        run('log info "top"\ntask main {\n    log info "main"\n}', log_output=log_output)
        # Only "top" should appear, not "main"
        messages = [line.split('] ')[-1] for line in log_output]
        assert "top" in messages
        assert "main" not in messages

    def test_no_auto_run_without_main(self):
        """If there's no main task, nothing is auto-run."""
        log_output = []
        run('task helper {\n    log info "helper"\n}', log_output=log_output)
        assert not any("helper" in line for line in log_output)


# ---------------------------------------------------------------------------
# http identifier accessible
# ---------------------------------------------------------------------------


class TestHttpAccessible:
    def test_http_is_accessible_as_identifier(self):
        interp = run("let h = http")
        h = interp.globals.get("h")
        assert h is not None

    def test_http_get_parses_as_call(self):
        """http.get 'url' should parse as a CallExpression."""
        from sprycode.lexer import Lexer
        from sprycode.parser import Parser
        from sprycode.ast_nodes import CallExpression, LetDeclaration
        code = 'let r = http.get "https://example.com"'
        tokens = Lexer(code).tokenize()
        prog = Parser(tokens).parse()
        let_decl = prog.body[0]
        assert isinstance(let_decl, LetDeclaration)
        assert isinstance(let_decl.value, CallExpression)

    def test_http_post_with_body_parses(self):
        from sprycode.lexer import Lexer
        from sprycode.parser import Parser
        from sprycode.ast_nodes import CallExpression, LetDeclaration
        code = 'let r = http.post "https://example.com" with {key: "val"}'
        tokens = Lexer(code).tokenize()
        prog = Parser(tokens).parse()
        let_decl = prog.body[0]
        assert isinstance(let_decl, LetDeclaration)
        assert isinstance(let_decl.value, CallExpression)
        assert len(let_decl.value.args) == 2


# ---------------------------------------------------------------------------
# f-strings
# ---------------------------------------------------------------------------


class TestFStrings:
    def test_basic_fstring(self):
        result = eval_expr('f"Hello {42}!"')
        assert result == "Hello 42!"

    def test_fstring_variable(self):
        interp = run('let name = "Alice"\nlet msg = f"Hello {name}!"')
        assert interp.globals.get("msg") == "Hello Alice!"

    def test_fstring_expression(self):
        interp = run('let x = 5\nlet s = f"x squared = {x * x}"')
        assert interp.globals.get("s") == "x squared = 25"

    def test_fstring_multiple_vars(self):
        interp = run('let a = "foo"\nlet b = "bar"\nlet s = f"{a} and {b}"')
        assert interp.globals.get("s") == "foo and bar"

    def test_fstring_no_interp(self):
        result = eval_expr('f"no interpolation"')
        assert result == "no interpolation"


# ---------------------------------------------------------------------------
# Triple-quoted strings
# ---------------------------------------------------------------------------


class TestTripleQuotedStrings:
    def test_triple_quoted_multiline(self):
        result = eval_expr('"""hello\nworld"""')
        assert result == "hello\nworld"

    def test_triple_quoted_single_line(self):
        result = eval_expr('"""just a string"""')
        assert result == "just a string"

    def test_triple_quoted_with_escapes(self):
        result = eval_expr('"""line1\\nline2"""')
        assert result == "line1\nline2"

    def test_triple_quoted_empty(self):
        result = eval_expr('""""""')
        assert result == ""


# ---------------------------------------------------------------------------
# Ternary expression
# ---------------------------------------------------------------------------


class TestTernaryExpression:
    def test_ternary_true(self):
        assert eval_expr("5 > 3 ? 1 : 0") == 1

    def test_ternary_false(self):
        assert eval_expr("1 > 3 ? 1 : 0") == 0

    def test_ternary_with_strings(self):
        assert eval_expr('"x" == "x" ? "yes" : "no"') == "yes"

    def test_ternary_nested(self):
        # Nested ternary using parentheses to disambiguate
        result = eval_expr("1 > 0 ? (2 > 1 ? 42 : 2) : 0")
        assert result == 42

    def test_ternary_in_expression(self):
        interp = run('let x = 10\nlet s = x >= 10 ? "big" : "small"')
        assert interp.globals.get("s") == "big"


# ---------------------------------------------------------------------------
# Null-coalescing operator ??
# ---------------------------------------------------------------------------


class TestNullCoalesce:
    def test_null_returns_fallback(self):
        assert eval_expr("null ?? 42") == 42

    def test_non_null_returns_value(self):
        assert eval_expr('"hello" ?? "fallback"') == "hello"

    def test_zero_is_not_null(self):
        assert eval_expr("0 ?? 99") == 0

    def test_empty_string_is_not_null(self):
        assert eval_expr('"" ?? "fallback"') == ""

    def test_chained_null_coalesce(self):
        assert eval_expr("null ?? null ?? 3") == 3


# ---------------------------------------------------------------------------
# in operator
# ---------------------------------------------------------------------------


class TestInOperator:
    def test_in_list_true(self):
        assert eval_expr('"b" in ["a", "b", "c"]') is True

    def test_in_list_false(self):
        assert eval_expr('"z" in ["a", "b", "c"]') is False

    def test_in_dict_true(self):
        assert eval_expr('"key" in {key: 1, other: 2}') is True

    def test_in_dict_false(self):
        assert eval_expr('"missing" in {key: 1}') is False

    def test_in_string(self):
        assert eval_expr('"ell" in "hello"') is True

    def test_not_in_list(self):
        log_output = []
        run(
            'let tags = ["a", "b"]\nif not "x" in tags {\n    log info "ok"\n}',
            log_output=log_output,
        )
        assert any("ok" in line for line in log_output)

    def test_in_expression_in_loop(self):
        log_output = []
        run(
            'let nums = [1, 2, 3, 4, 5]\nlet evens = [2, 4, 6]\nvar count = 0\nfor n in nums {\n    if n in evens {\n        count += 1\n    }\n}\nlog info count',
            log_output=log_output,
        )
        assert any("2" in line for line in log_output)


# ---------------------------------------------------------------------------
# Power operator **
# ---------------------------------------------------------------------------


class TestPowerOperator:
    def test_power_basic(self):
        assert eval_expr("2 ** 10") == 1024

    def test_power_zero(self):
        assert eval_expr("5 ** 0") == 1

    def test_power_one(self):
        assert eval_expr("7 ** 1") == 7

    def test_power_right_assoc(self):
        # 2 ** 3 ** 2 = 2 ** 9 = 512 (right-associative)
        assert eval_expr("2 ** 3 ** 2") == 512

    def test_sqrt_via_power(self):
        assert eval_expr("9 ** 0.5") == 3.0


# ---------------------------------------------------------------------------
# range() and sequence builtins
# ---------------------------------------------------------------------------


class TestSequenceBuiltins:
    def test_range_two_args(self):
        result = eval_expr("range(1, 5)")
        assert result == [1, 2, 3, 4]

    def test_range_one_arg(self):
        result = eval_expr("range(5)")
        assert result == [0, 1, 2, 3, 4]

    def test_range_step(self):
        result = eval_expr("range(0, 10, 2)")
        assert result == [0, 2, 4, 6, 8]

    def test_sorted_list(self):
        result = eval_expr("sorted([3, 1, 4, 1, 5, 9, 2, 6])")
        assert result[0] == 1

    def test_sum_list(self):
        assert eval_expr("sum([1, 2, 3, 4, 5])") == 15

    def test_any_true(self):
        assert eval_expr("any([false, true, false])") is True

    def test_any_false(self):
        assert eval_expr("any([false, false, false])") is False

    def test_all_true(self):
        assert eval_expr("all([true, true, true])") is True

    def test_all_false(self):
        assert eval_expr("all([true, false, true])") is False

    def test_zip(self):
        result = eval_expr("zip([1, 2, 3], [4, 5, 6])")
        assert result == [[1, 4], [2, 5], [3, 6]]

    def test_enumerate(self):
        result = eval_expr('enumerate(["a", "b", "c"])')
        assert result == [[0, "a"], [1, "b"], [2, "c"]]

    def test_unique(self):
        result = eval_expr("unique([1, 2, 2, 3, 1, 3])")
        assert result == [1, 2, 3]

    def test_flatten(self):
        result = eval_expr("flatten([[1, 2], [3, 4], [5]])")
        assert result == [1, 2, 3, 4, 5]

    def test_sqrt(self):
        assert eval_expr("sqrt(16)") == 4.0

    def test_pow_builtin(self):
        assert eval_expr("pow(2, 8)") == 256


# ---------------------------------------------------------------------------
# Array spread operator
# ---------------------------------------------------------------------------


class TestSpreadOperator:
    def test_spread_at_end(self):
        interp = run("let a = [3, 4, 5]\nlet b = [1, 2, ...a]")
        assert interp.globals.get("b") == [1, 2, 3, 4, 5]

    def test_spread_at_start(self):
        interp = run("let a = [1, 2]\nlet b = [...a, 3, 4]")
        assert interp.globals.get("b") == [1, 2, 3, 4]

    def test_spread_in_middle(self):
        interp = run("let a = [2, 3]\nlet b = [1, ...a, 4]")
        assert interp.globals.get("b") == [1, 2, 3, 4]

    def test_spread_empty(self):
        interp = run("let a = []\nlet b = [1, ...a, 2]")
        assert interp.globals.get("b") == [1, 2]

    def test_spread_concat_two(self):
        interp = run("let a = [1, 2]\nlet b = [3, 4]\nlet c = [...a, ...b]")
        assert interp.globals.get("c") == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Dict methods
# ---------------------------------------------------------------------------


class TestDictMethods:
    def test_dict_keys(self):
        interp = run("let d = {a: 1, b: 2, c: 3}\nlet k = d.keys")
        k = interp.globals.get("k")
        assert sorted(k) == ["a", "b", "c"]

    def test_dict_values(self):
        interp = run("let d = {a: 1, b: 2}\nlet v = d.values")
        v = interp.globals.get("v")
        assert sorted(v) == [1, 2]

    def test_dict_entries(self):
        interp = run("let d = {x: 10}\nlet e = d.entries")
        e = interp.globals.get("e")
        assert e == [["x", 10]]

    def test_dict_length(self):
        assert eval_expr("{a: 1, b: 2, c: 3}.length") == 3

    def test_dict_has(self):
        assert eval_expr('{key: 1}.has("key")') is True
        assert eval_expr('{key: 1}.has("missing")') is False

    def test_dict_merge(self):
        interp = run("let a = {x: 1}\nlet b = {y: 2}\nlet c = a.merge(b)")
        c = interp.globals.get("c")
        assert c == {"x": 1, "y": 2}

    def test_dict_set(self):
        interp = run("var d = {a: 1}\nd.set(\"b\", 2)")
        d = interp.globals.get("d")
        assert d.get("b") == 2

    def test_dict_delete(self):
        interp = run('var d = {a: 1, b: 2}\nd.delete("a")')
        d = interp.globals.get("d")
        assert "a" not in d


# ---------------------------------------------------------------------------
# Enhanced list methods
# ---------------------------------------------------------------------------


class TestEnhancedListMethods:
    def test_sort(self):
        interp = run("let nums = [3, 1, 2]\nlet s = nums.sort")
        assert interp.globals.get("s") == [1, 2, 3]

    def test_indexOf(self):
        assert eval_expr('["a", "b", "c"].indexOf("b")') == 1
        assert eval_expr('["a", "b", "c"].indexOf("z")') == -1

    def test_sum(self):
        assert eval_expr("[1, 2, 3, 4].sum") == 10

    def test_min(self):
        assert eval_expr("[5, 1, 3, 2].min") == 1

    def test_max(self):
        assert eval_expr("[5, 1, 3, 2].max") == 5

    def test_unique(self):
        result = eval_expr("[1, 2, 2, 3, 1].unique")
        assert result == [1, 2, 3]

    def test_flat(self):
        result = eval_expr("[[1, 2], [3, 4]].flat")
        assert result == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Enhanced string methods
# ---------------------------------------------------------------------------


class TestEnhancedStringMethods:
    def test_trimStart(self):
        assert eval_expr('"  hello  ".trimStart') == "hello  "

    def test_trimEnd(self):
        assert eval_expr('"  hello  ".trimEnd') == "  hello"

    def test_indexOf(self):
        assert eval_expr('"hello world".indexOf("world")') == 6

    def test_padStart(self):
        assert eval_expr('"42".padStart(5)') == "   42"

    def test_padEnd(self):
        assert eval_expr('"42".padEnd(5)') == "42   "

    def test_repeat(self):
        assert eval_expr('"ab".repeat(3)') == "ababab"

    def test_chars(self):
        result = eval_expr('"abc".chars')
        assert result == ["a", "b", "c"]

    def test_lines(self):
        result = eval_expr('"a\\nb\\nc".lines')
        assert result == ["a", "b", "c"]

    def test_isNotEmpty(self):
        assert eval_expr('"hello".isNotEmpty') is True
        assert eval_expr('"".isNotEmpty') is False

    def test_includes(self):
        assert eval_expr('"hello".includes("ell")') is True


# ---------------------------------------------------------------------------
# match statement
# ---------------------------------------------------------------------------


class TestMatchStatement:
    def test_match_first_arm(self):
        log_output = []
        run('match 1 {\n    1 => log info "one"\n    2 => log info "two"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("one" in l for l in log_output)

    def test_match_second_arm(self):
        log_output = []
        run('match 2 {\n    1 => log info "one"\n    2 => log info "two"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("two" in l for l in log_output)

    def test_match_wildcard(self):
        log_output = []
        run('match 99 {\n    1 => log info "one"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("other" in l for l in log_output)

    def test_match_string(self):
        log_output = []
        run('match "hello" {\n    "world" => log info "world"\n    "hello" => log info "hello"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("hello" in l for l in log_output)

    def test_match_no_match_no_crash(self):
        log_output = []
        run('match 5 {\n    1 => log info "one"\n    2 => log info "two"\n}', log_output=log_output)
        assert log_output == []

    def test_match_with_variable(self):
        # match is a statement, verified via log side-effects
        log_output = []
        run('let x = 3\nmatch x {\n    3 => log info "three"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("three" in l for l in log_output)


# ---------------------------------------------------------------------------
# repeat..until
# ---------------------------------------------------------------------------


class TestRepeatUntil:
    def test_basic_repeat(self):
        interp = run('var i = 0\nrepeat {\n    i += 1\n} until i >= 5')
        assert interp.globals.get("i") == 5

    def test_repeat_executes_body_at_least_once(self):
        interp = run('var x = 0\nrepeat {\n    x += 10\n} until x > 0')
        assert interp.globals.get("x") == 10

    def test_repeat_collects_values(self):
        log_output = []
        run('var i = 1\nrepeat {\n    log info i\n    i += 1\n} until i > 3', log_output=log_output)
        assert len([l for l in log_output if any(n in l for n in ["1", "2", "3"])]) >= 3

    def test_repeat_break(self):
        interp = run('var i = 0\nrepeat {\n    i += 1\n    if i == 3 {\n        break\n    }\n} until i >= 100')
        assert interp.globals.get("i") == 3


# ---------------------------------------------------------------------------
# List destructuring
# ---------------------------------------------------------------------------


class TestListDestructure:
    def test_basic(self):
        interp = run('let [a, b, c] = [10, 20, 30]')
        assert interp.globals.get("a") == 10
        assert interp.globals.get("b") == 20
        assert interp.globals.get("c") == 30

    def test_partial(self):
        interp = run('let [x, y] = [1, 2, 3]')
        assert interp.globals.get("x") == 1
        assert interp.globals.get("y") == 2

    def test_too_few_elements(self):
        interp = run('let [a, b, c] = [1, 2]')
        assert interp.globals.get("a") == 1
        assert interp.globals.get("c") is None

    def test_var_destructure_mutable(self):
        interp = run('var [a, b] = [1, 2]\na = 99')
        assert interp.globals.get("a") == 99

    def test_destructure_in_loop(self):
        log_output = []
        run('let pairs = [[1, "a"], [2, "b"]]\nfor pair in pairs {\n    let [n, s] = pair\n    log info s\n}', log_output=log_output)
        assert any("a" in l for l in log_output)
        assert any("b" in l for l in log_output)

    def test_rest_element(self):
        interp = run('let [first, ...rest] = [1, 2, 3, 4]')
        assert interp.globals.get("first") == 1
        assert interp.globals.get("rest") == [2, 3, 4]

    def test_rest_element_empty(self):
        interp = run('let [a, b, ...rest] = [1, 2]')
        assert interp.globals.get("a") == 1
        assert interp.globals.get("b") == 2
        assert interp.globals.get("rest") == []

    def test_rest_only(self):
        interp = run('let [...rest] = [10, 20, 30]')
        assert interp.globals.get("rest") == [10, 20, 30]

    def test_rest_mutable(self):
        interp = run('var [head, ...tail] = [1, 2, 3]\nhead = 99')
        assert interp.globals.get("head") == 99
        assert interp.globals.get("tail") == [2, 3]


# ---------------------------------------------------------------------------
# Object destructuring
# ---------------------------------------------------------------------------


class TestObjectDestructure:
    def test_basic(self):
        interp = run('let {name, age} = {name: "Alice", age: 30}')
        assert interp.globals.get("name") == "Alice"
        assert interp.globals.get("age") == 30

    def test_alias(self):
        interp = run('let {name: n, age: a} = {name: "Bob", age: 25}')
        assert interp.globals.get("n") == "Bob"
        assert interp.globals.get("a") == 25

    def test_missing_key(self):
        interp = run('let {x, y} = {x: 1}')
        assert interp.globals.get("x") == 1
        assert interp.globals.get("y") is None

    def test_partial(self):
        interp = run('let {name} = {name: "Carol", age: 40, city: "NYC"}')
        assert interp.globals.get("name") == "Carol"


# ---------------------------------------------------------------------------
# Object spread
# ---------------------------------------------------------------------------


class TestObjectSpread:
    def test_basic_spread(self):
        interp = run('let a = {x: 1, y: 2}\nlet b = {...a, z: 3}')
        b = interp.globals.get("b")
        assert b == {"x": 1, "y": 2, "z": 3}

    def test_spread_override(self):
        interp = run('let a = {x: 1, y: 2}\nlet b = {...a, x: 99}')
        b = interp.globals.get("b")
        assert b["x"] == 99

    def test_spread_multiple(self):
        interp = run('let a = {x: 1}\nlet b = {y: 2}\nlet c = {...a, ...b, z: 3}')
        c = interp.globals.get("c")
        assert c == {"x": 1, "y": 2, "z": 3}

    def test_spread_empty(self):
        interp = run('let a = {}\nlet b = {...a, x: 5}')
        b = interp.globals.get("b")
        assert b == {"x": 5}


# ---------------------------------------------------------------------------
# for k in dict
# ---------------------------------------------------------------------------


class TestForInDict:
    def test_iterates_keys(self):
        log_output = []
        run('let d = {a: 1, b: 2, c: 3}\nfor k in d {\n    log info k\n}', log_output=log_output)
        keys = [l.split("] ")[-1] for l in log_output]
        assert sorted(keys) == ["a", "b", "c"]

    def test_count_keys(self):
        interp = run('let d = {x: 10, y: 20}\nvar n = 0\nfor k in d {\n    n += 1\n}')
        assert interp.globals.get("n") == 2

    def test_access_values(self):
        log_output = []
        run('let d = {score: 100}\nfor k in d {\n    log info d.score\n}', log_output=log_output)
        assert any("100" in l for l in log_output)


# ---------------------------------------------------------------------------
# assert statement
# ---------------------------------------------------------------------------


class TestAssertStatement:
    def test_passes(self):
        log_output = []
        run('assert 1 == 1\nlog info "ok"', log_output=log_output)
        assert any("ok" in l for l in log_output)

    def test_fails(self):
        import pytest
        with pytest.raises(Exception, match="Assertion failed"):
            run('assert 1 == 2')

    def test_fails_with_message(self):
        import pytest
        with pytest.raises(Exception, match="expected positive"):
            run('assert -1 > 0, "expected positive"')

    def test_assert_in_function(self):
        import pytest
        with pytest.raises(Exception):
            run('fn validate(x) {\n    assert x > 0, "must be positive"\n}\nvalidate(-1)')


# ---------------------------------------------------------------------------
# import statement
# ---------------------------------------------------------------------------


class TestImportStatement:
    def test_import_pi(self):
        interp = run('import { pi } from "math"')
        import math
        assert abs(interp.globals.get("pi") - math.pi) < 1e-9

    def test_import_e(self):
        interp = run('import { e } from "math"')
        import math
        assert abs(interp.globals.get("e") - math.e) < 1e-9

    def test_import_unknown_module_no_crash(self):
        # Should log a warning but not raise
        run('import "nonexistent_module"')


# ---------------------------------------------------------------------------
# reduce pipeline
# ---------------------------------------------------------------------------


class TestReducePipeline:
    def test_sum(self):
        interp = run('let total = [1, 2, 3, 4, 5] |> reduce (acc, x) => acc + x')
        assert interp.globals.get("total") == 15

    def test_product(self):
        interp = run('let product = [1, 2, 3, 4] |> reduce (acc, x) => acc * x')
        assert interp.globals.get("product") == 24

    def test_with_init(self):
        interp = run('let total = [1, 2, 3] |> reduce 10 (acc, x) => acc + x')
        assert interp.globals.get("total") == 16

    def test_with_init_zero(self):
        interp = run('let total = [5, 5, 5] |> reduce 0 (acc, x) => acc + x')
        assert interp.globals.get("total") == 15

    def test_string_join(self):
        interp = run('let s = ["a", "b", "c"] |> reduce "" (acc, x) => acc + x')
        assert interp.globals.get("s") == "abc"


# ---------------------------------------------------------------------------
# str.match regex
# ---------------------------------------------------------------------------


class TestStrMatch:
    def test_find_digits(self):
        result = eval_expr('"hello123".match("[0-9]+")')
        assert result == ["123"]

    def test_no_match_returns_none(self):
        result = eval_expr('"hello".match("[0-9]+")')
        assert result is None

    def test_multiple_matches(self):
        result = eval_expr('"a1b2c3".match("[0-9]")')
        assert result == ["1", "2", "3"]

    def test_match_letters(self):
        result = eval_expr('"123abc456".match("[a-z]+")')
        assert result == ["abc"]


# ---------------------------------------------------------------------------
# env() and format() builtins
# ---------------------------------------------------------------------------


class TestEnvAndFormat:
    def test_env_missing_key_returns_none(self):
        result = eval_expr('env("__SPRYCODE_NONEXISTENT_KEY_XYZ__")')
        assert result is None

    def test_env_with_default(self):
        result = eval_expr('env("__SPRYCODE_NONEXISTENT_KEY_XYZ__") ?? "default"')
        assert result == "default"

    def test_format_basic(self):
        result = eval_expr('format("Hello {}!", "World")')
        assert result == "Hello World!"

    def test_format_number(self):
        result = eval_expr('format("{:.2f}", 3.14159)')
        assert result == "3.14"

    def test_format_multiple(self):
        result = eval_expr('format("{} + {} = {}", 1, 2, 3)')
        assert result == "1 + 2 = 3"


# ---------------------------------------------------------------------------
# Multi-param lambda
# ---------------------------------------------------------------------------


class TestMultiParamLambda:
    def test_in_function_call(self):
        interp = run('fn apply(f, a, b) { return f(a, b) }\nlet r = apply((x, y) => x + y, 3, 4)')
        assert interp.globals.get("r") == 7

    def test_multiply(self):
        interp = run('fn apply(f, a, b) { return f(a, b) }\nlet r = apply((x, y) => x * y, 5, 6)')
        assert interp.globals.get("r") == 30

    def test_compare(self):
        interp = run('fn apply(f, a, b) { return f(a, b) }\nlet r = apply((x, y) => x > y, 10, 5)')
        assert interp.globals.get("r") is True


# ---------------------------------------------------------------------------
# helper for direct expression eval
# (eval_expr already defined above)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# SpryLambda closures
# ---------------------------------------------------------------------------


class TestLambdaClosures:
    def test_single_param_with_parens(self):
        interp = run("let f = (x) => x * x\nlet r = f(5)")
        assert interp.globals.get("r") == 25

    def test_compose_closures(self):
        code = (
            "fn compose(f, g) { return (x) => f(g(x)) }\n"
            "let double = (x) => x * 2\n"
            "let inc = (x) => x + 1\n"
            "let doubleInc = compose(double, inc)\n"
            "let r = doubleInc(5)"
        )
        interp = run(code)
        assert interp.globals.get("r") == 12

    def test_closure_in_loop(self):
        code = (
            "var fns = []\n"
            "for i in [10, 20, 30] {\n"
            "    let fi = (x) => x + i\n"
            "    fns.push(fi)\n"
            "}\n"
            "let r = fns[0](5)"
        )
        interp = run(code)
        assert interp.globals.get("r") == 15

    def test_multi_param_with_parens(self):
        interp = run("let add = (a, b) => a + b\nlet r = add(3, 4)")
        assert interp.globals.get("r") == 7

    def test_returned_lambda_captures_scope(self):
        code = (
            "fn makeAdder(n) { return (x) => x + n }\n"
            "let add5 = makeAdder(5)\n"
            "let r = add5(10)"
        )
        interp = run(code)
        assert interp.globals.get("r") == 15


# ---------------------------------------------------------------------------
# Method chaining — zero-arg methods callable with ()
# ---------------------------------------------------------------------------


class TestMethodChaining:
    def test_trim_as_call(self):
        interp = run('let s = "  hello  ".trim()')
        assert interp.globals.get("s") == "hello"

    def test_upper_as_call(self):
        interp = run('let s = "hello".upper()')
        assert interp.globals.get("s") == "HELLO"

    def test_lower_as_call(self):
        interp = run('let s = "HELLO".lower()')
        assert interp.globals.get("s") == "hello"

    def test_trim_then_upper(self):
        interp = run('let s = "  hello  ".trim().toUpper()')
        assert interp.globals.get("s") == "HELLO"

    def test_trim_then_lower(self):
        interp = run('let s = "  HELLO  ".trim().toLower()')
        assert interp.globals.get("s") == "hello"

    def test_sort_as_call(self):
        interp = run("let s = [3, 1, 4, 1, 5].sort()")
        assert interp.globals.get("s") == [1, 1, 3, 4, 5]

    def test_dict_keys_as_call(self):
        interp = run("let d = {a: 1, b: 2, c: 3}\nlet k = d.keys()")
        k = interp.globals.get("k")
        assert sorted(k) == ["a", "b", "c"]

    def test_dict_values_as_call(self):
        interp = run("let d = {a: 1, b: 2}\nlet v = d.values()")
        v = interp.globals.get("v")
        assert sorted(v) == [1, 2]

    def test_trim_then_split(self):
        interp = run('let parts = "  a,b,c  ".trim().split(",")')
        assert interp.globals.get("parts") == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Log rendering (true/false/null)
# ---------------------------------------------------------------------------


class TestLogRendering:
    def test_log_true(self):
        log_output = []
        run("log info true", log_output=log_output)
        assert any("true" in l for l in log_output)
        assert not any("True" in l for l in log_output)

    def test_log_false(self):
        log_output = []
        run("log info false", log_output=log_output)
        assert any("false" in l for l in log_output)
        assert not any("False" in l for l in log_output)

    def test_log_null(self):
        log_output = []
        run("log info null", log_output=log_output)
        assert any("null" in l for l in log_output)
        assert not any("None" in l for l in log_output)

    def test_log_bool_expr(self):
        log_output = []
        run("log info (1 == 1)", log_output=log_output)
        assert any("true" in l for l in log_output)

    def test_list_includes_renders_true(self):
        log_output = []
        run("log info [1, 2, 3].includes(2)", log_output=log_output)
        assert any("true" in l for l in log_output)
        assert not any("True" in l for l in log_output)


# ---------------------------------------------------------------------------
# New list HOF methods
# ---------------------------------------------------------------------------


class TestListHOFMethods:
    def test_map_with_lambda(self):
        interp = run("let d = [1, 2, 3].map(x => x * 2)")
        assert interp.globals.get("d") == [2, 4, 6]

    def test_filter_with_lambda(self):
        interp = run("let d = [1, 2, 3, 4].filter(x => x % 2 == 0)")
        assert interp.globals.get("d") == [2, 4]

    def test_find_with_lambda(self):
        interp = run("let x = [1, 2, 3, 4].find(x => x > 2)")
        assert interp.globals.get("x") == 3

    def test_find_not_found(self):
        interp = run("let x = [1, 2, 3].find(x => x > 10)")
        assert interp.globals.get("x") is None

    def test_every_all_true(self):
        interp = run("let b = [2, 4, 6].every(x => x % 2 == 0)")
        assert interp.globals.get("b") is True

    def test_every_some_false(self):
        interp = run("let b = [2, 3, 6].every(x => x % 2 == 0)")
        assert interp.globals.get("b") is False

    def test_some_at_least_one(self):
        interp = run("let b = [1, 3, 5, 4].some(x => x % 2 == 0)")
        assert interp.globals.get("b") is True

    def test_some_none_match(self):
        interp = run("let b = [1, 3, 5].some(x => x % 2 == 0)")
        assert interp.globals.get("b") is False

    def test_reduce_no_init(self):
        interp = run("let s = [1, 2, 3, 4].reduce((acc, x) => acc + x)")
        assert interp.globals.get("s") == 10

    def test_reduce_with_init(self):
        interp = run("let s = [1, 2, 3, 4].reduce(0, (acc, x) => acc + x)")
        assert interp.globals.get("s") == 10

    def test_reduce_product(self):
        interp = run("let p = [1, 2, 3, 4].reduce(1, (acc, x) => acc * x)")
        assert interp.globals.get("p") == 24

    def test_flat_map(self):
        interp = run("let d = [[1, 2], [3, 4]].flatMap(x => x)")
        assert interp.globals.get("d") == [1, 2, 3, 4]

    def test_flat_map_transform(self):
        interp = run("let d = [1, 2, 3].flatMap(x => [x, x * 2])")
        assert interp.globals.get("d") == [1, 2, 2, 4, 3, 6]

    def test_chained_map_filter(self):
        interp = run(
            "let r = [1, 2, 3, 4, 5, 6].filter(x => x % 2 == 0).map(x => x * 10)"
        )
        assert interp.globals.get("r") == [20, 40, 60]


# ---------------------------------------------------------------------------
# String method aliases and new methods
# ---------------------------------------------------------------------------


class TestStringMethodAliases:
    def test_toUpper(self):
        assert eval_expr('"hello".toUpper') == "HELLO"

    def test_toUpper_call(self):
        interp = run('let s = "hello".toUpper()')
        assert interp.globals.get("s") == "HELLO"

    def test_toLower(self):
        assert eval_expr('"HELLO".toLower') == "hello"

    def test_toLower_call(self):
        interp = run('let s = "HELLO".toLower()')
        assert interp.globals.get("s") == "hello"

    def test_padLeft(self):
        assert eval_expr('"5".padLeft(3, "0")') == "005"

    def test_padLeft_default_space(self):
        assert eval_expr('"5".padLeft(4)') == "   5"

    def test_padRight(self):
        assert eval_expr('"5".padRight(3, "0")') == "500"

    def test_padRight_default_space(self):
        assert eval_expr('"5".padRight(4)') == "5   "


# ---------------------------------------------------------------------------
# Number methods
# ---------------------------------------------------------------------------


class TestNumberMethods:
    def test_toFixed(self):
        assert eval_expr("(3.14159).toFixed(2)") == "3.14"

    def test_toFixed_zero(self):
        assert eval_expr("(3.14159).toFixed(0)") == "3"

    def test_toFixed_default(self):
        result = eval_expr("(3.14159).toFixed")
        # property access returns lambda
        assert callable(result)

    def test_toStr(self):
        assert eval_expr("(42.0).toStr()") == "42"

    def test_toInt(self):
        assert eval_expr("(3.9).toInt") == 3

    def test_abs(self):
        assert eval_expr("(-5).abs") == 5
        assert eval_expr("(5).abs") == 5
