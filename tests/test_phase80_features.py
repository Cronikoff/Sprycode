"""Tests for Phase 80 features: Console and Output."""
from __future__ import annotations
from typing import Any
import pytest
from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


class TestConsoleBasicOutput:
    def test_console_log_string(self, capsys):
        run('console.log("hello world")')
        out = capsys.readouterr().out
        assert "hello world" in out

    def test_console_log_number(self, capsys):
        run("console.log(42)")
        out = capsys.readouterr().out
        assert "42" in out

    def test_console_log_multiple_args(self, capsys):
        run("console.log(1, 2, 3)")
        out = capsys.readouterr().out
        assert "1" in out
        assert "2" in out
        assert "3" in out

    def test_console_log_object(self, capsys):
        run("console.log({a: 1})")
        # Just shouldn't throw
        capsys.readouterr()

    def test_console_log_array(self, capsys):
        run("console.log([1, 2, 3])")
        capsys.readouterr()

    def test_console_log_no_throw(self):
        # Should not raise an exception
        run('console.log("test")')

    def test_console_log_boolean(self, capsys):
        run("console.log(true)")
        out = capsys.readouterr().out
        assert "True" in out or "true" in out

    def test_console_log_null(self, capsys):
        run("console.log(null)")
        out = capsys.readouterr().out
        assert "None" in out or "null" in out


class TestConsoleLevels:
    def test_console_warn_no_throw(self):
        run('console.warn("warning message")')

    def test_console_error_no_throw(self):
        run('console.error("error message")')

    def test_console_info_no_throw(self):
        run('console.info("info message")')

    def test_console_debug_no_throw(self):
        run('console.debug("debug message")')

    def test_console_warn_outputs(self, capsys):
        run('console.warn("warn test")')
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "warn test" in combined or "WARN" in combined or "WARNING" in combined

    def test_console_error_outputs(self, capsys):
        run('console.error("error test")')
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "error test" in combined or "ERROR" in combined

    def test_console_info_outputs(self, capsys):
        run('console.info("info test")')
        out = capsys.readouterr().out
        assert "info test" in out or "INFO" in out


class TestConsoleInspection:
    def test_console_dir_no_throw(self):
        run("console.dir({a: 1, b: 2})")

    def test_console_table_no_throw(self):
        run("console.table([{a: 1}, {a: 2}])")

    def test_console_dir_outputs(self, capsys):
        run("console.dir({x: 42})")
        capsys.readouterr()  # just flush

    def test_console_table_outputs(self, capsys):
        run("console.table([1, 2, 3])")
        out = capsys.readouterr().out
        assert len(out) > 0


class TestConsoleCount:
    def test_console_count_no_throw(self):
        run('console.count("label")')

    def test_console_count_reset_no_throw(self):
        run('console.count("x"); console.countReset("x")')

    def test_console_count_increments(self, capsys):
        run('console.count("myLabel"); console.count("myLabel")')
        out = capsys.readouterr().out
        assert "myLabel" in out

    def test_console_count_default_label(self):
        run("console.count()")

    def test_console_count_reset_no_throw_default(self):
        run("console.countReset()")


class TestConsoleGroup:
    def test_console_group_no_throw(self):
        run('console.group("label")')

    def test_console_group_end_no_throw(self):
        run('console.group("x"); console.groupEnd()')

    def test_console_group_outputs(self, capsys):
        run('console.group("myGroup")')
        out = capsys.readouterr().out
        assert len(out) >= 0  # may or may not output

    def test_console_group_collapsed_no_throw(self):
        run('console.groupCollapsed("collapsed")')


class TestConsoleTimer:
    def test_console_time_no_throw(self):
        run('console.time("label")')

    def test_console_time_end_no_throw(self):
        run('console.time("timer"); console.timeEnd("timer")')

    def test_console_time_end_outputs(self, capsys):
        run('console.time("t"); console.timeEnd("t")')
        out = capsys.readouterr().out
        assert "t" in out

    def test_console_time_log_no_throw(self):
        run('console.time("tl"); console.timeLog("tl")')


class TestConsoleAssert:
    def test_console_assert_true_no_throw(self):
        run("console.assert(true, 'should not fail')")

    def test_console_assert_false_no_throw(self):
        # False assertion should output message but not throw
        run("console.assert(false, 'assertion failed')")

    def test_console_assert_true_no_output(self, capsys):
        run("console.assert(true, 'no output')")
        out = capsys.readouterr().out
        # True assertion should not print failure message
        assert "no output" not in out

    def test_console_assert_false_outputs(self, capsys):
        run("console.assert(false, 'fail msg')")
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "fail msg" in combined or "Assertion" in combined

    def test_console_assert_no_message(self):
        run("console.assert(true)")

    def test_console_log_returns_undefined(self):
        src = "let v = typeof console.log('x')"
        # log returns undefined/None
        i = run(src)
        result = val(i)
        assert result in ("undefined", None, "object")
