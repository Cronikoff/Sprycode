"""Tests for Phase 89: Type Coercion"""
from __future__ import annotations
from typing import Any
import math
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


def test_unary_plus_string():
    assert val(run('let v = +"42";')) == 42


def test_unary_plus_empty_string():
    assert val(run('let v = +"";')) == 0


def test_unary_plus_null():
    assert val(run('let v = +null;')) == 0


def test_unary_plus_undefined():
    result = val(run('let v = +undefined;'))
    assert math.isnan(result)


def test_unary_plus_true():
    assert val(run('let v = +true;')) == 1


def test_unary_plus_false():
    assert val(run('let v = +false;')) == 0


def test_unary_plus_nan_string():
    result = val(run('let v = +"abc";'))
    assert math.isnan(result)


def test_double_bang_zero():
    assert val(run('let v = !!0;')) is False


def test_double_bang_one():
    assert val(run('let v = !!1;')) is True


def test_double_bang_empty_string():
    assert val(run('let v = !!"";')) is False


def test_double_bang_nonempty_string():
    assert val(run('let v = !!"x";')) is True


def test_double_bang_null():
    assert val(run('let v = !!null;')) is False


def test_double_bang_undefined():
    assert val(run('let v = !!undefined;')) is False


def test_string_concat_with_number():
    assert val(run('let v = "" + 1;')) == "1"


def test_number_plus_string():
    assert val(run('let v = 1 + "";')) == "1"


def test_left_to_right_addition():
    assert val(run('let v = 1 + 2 + "3";')) == "33"


def test_string_then_numbers():
    assert val(run('let v = "3" + 1 + 2;')) == "312"


def test_null_plus_number():
    assert val(run('let v = null + 1;')) == 1


def test_undefined_plus_number():
    result = val(run('let v = undefined + 1;'))
    assert math.isnan(result)


def test_boolean_zero():
    assert val(run('let v = Boolean(0);')) is False


def test_boolean_empty_string():
    assert val(run('let v = Boolean("");')) is False


def test_boolean_null():
    assert val(run('let v = Boolean(null);')) is False


def test_boolean_array_truthy():
    assert val(run('let v = Boolean([]);')) is True


def test_boolean_object_truthy():
    assert val(run('let v = Boolean({});')) is True


def test_boolean_nonzero():
    assert val(run('let v = Boolean(42);')) is True


def test_number_from_string():
    assert val(run('let v = Number("42");')) == 42


def test_number_from_true():
    assert val(run('let v = Number(true);')) == 1


def test_number_from_null():
    assert val(run('let v = Number(null);')) == 0


def test_number_from_false():
    assert val(run('let v = Number(false);')) == 0


def test_string_from_number():
    assert val(run('let v = String(42);')) == "42"


def test_string_from_null():
    assert val(run('let v = String(null);')) == "null"


def test_string_from_undefined():
    assert val(run('let v = String(undefined);')) == "undefined"


def test_string_from_true():
    assert val(run('let v = String(true);')) == "true"


def test_string_from_false():
    assert val(run('let v = String(false);')) == "false"


def test_null_equals_undefined():
    assert val(run('let v = (null == undefined);')) is True


def test_null_not_strict_equal_undefined():
    assert val(run('let v = (null === undefined);')) is False


def test_zero_equals_false():
    assert val(run('let v = (0 == false);')) is True


def test_empty_string_equals_false():
    assert val(run('let v = ("" == false);')) is True


def test_one_equals_true():
    assert val(run('let v = (1 == true);')) is True


def test_null_not_equals_false():
    assert val(run('let v = (null == false);')) is False


def test_null_not_equals_zero():
    assert val(run('let v = (null == 0);')) is False


def test_string_number_equals():
    assert val(run('let v = ("42" == 42);')) is True


def test_strict_equal_no_coerce():
    assert val(run('let v = ("42" === 42);')) is False


def test_boolean_nonzero_string():
    assert val(run('let v = Boolean("hello");')) is True


def test_number_from_float_string():
    assert val(run('let v = Number("3.14");')) == pytest.approx(3.14)


def test_double_bang_nonzero():
    assert val(run('let v = !!42;')) is True


def test_double_bang_nonempty_string():
    assert val(run('let v = !!"hello";')) is True


def test_string_concat_bool():
    assert val(run('let v = "val: " + true;')) == "val: true"


def test_template_coerces_number():
    assert val(run('let n = 42; let v = `${n}`;')) == "42"


def test_number_from_whitespace_string():
    assert val(run('let v = Number("  42  ");')) == 42
