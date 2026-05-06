"""Tests for Phase 90: Bitwise and Numeric"""
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


def test_bitwise_and():
    assert val(run('let v = 5 & 3;')) == 1


def test_bitwise_or():
    assert val(run('let v = 5 | 3;')) == 7


def test_bitwise_xor():
    assert val(run('let v = 5 ^ 3;')) == 6


def test_bitwise_not():
    assert val(run('let v = ~5;')) == -6


def test_left_shift():
    assert val(run('let v = 1 << 4;')) == 16


def test_signed_right_shift():
    assert val(run('let v = 16 >> 2;')) == 4


def test_unsigned_right_shift():
    assert val(run('let v = -1 >>> 0;')) == 4294967295


def test_unsigned_right_shift_positive():
    assert val(run('let v = 32 >>> 2;')) == 8


def test_or_assign():
    assert val(run('let x = 4; x |= 1; let v = x;')) == 5


def test_and_assign():
    assert val(run('let x = 7; x &= 3; let v = x;')) == 3


def test_xor_assign():
    assert val(run('let x = 5; x ^= 3; let v = x;')) == 6


def test_left_shift_assign():
    assert val(run('let x = 1; x <<= 4; let v = x;')) == 16


def test_right_shift_assign():
    assert val(run('let x = 16; x >>= 2; let v = x;')) == 4


def test_number_max_safe_integer():
    assert val(run('let v = Number.MAX_SAFE_INTEGER;')) == 2**53 - 1


def test_number_min_safe_integer():
    assert val(run('let v = Number.MIN_SAFE_INTEGER;')) == -(2**53 - 1)


def test_number_max_value():
    v = val(run('let v = Number.MAX_VALUE;'))
    assert v > 0


def test_number_epsilon():
    v = val(run('let v = Number.EPSILON;'))
    assert v > 0
    assert v < 0.001


def test_number_positive_infinity():
    import math as _math
    v = val(run('let v = Number.POSITIVE_INFINITY;'))
    assert _math.isinf(v) and v > 0


def test_number_negative_infinity():
    import math as _math
    v = val(run('let v = Number.NEGATIVE_INFINITY;'))
    assert _math.isinf(v) and v < 0


def test_number_nan():
    v = val(run('let v = Number.NaN;'))
    assert math.isnan(v)


def test_integer_arithmetic():
    assert val(run('let v = 1000000 * 1000000;')) == 1000000000000


def test_float_arithmetic_imprecision():
    # 0.1 + 0.2 !== 0.3 in floating point
    v = val(run('let v = (0.1 + 0.2 === 0.3);'))
    assert v is False


def test_float_round_pattern():
    v = val(run('let v = Math.round((0.1 + 0.2) * 10) / 10;'))
    assert v == pytest.approx(0.3)


def test_bitwise_and_zero():
    assert val(run('let v = 0 & 7;')) == 0


def test_bitwise_or_zero():
    assert val(run('let v = 0 | 7;')) == 7


def test_bitwise_xor_same():
    assert val(run('let v = 5 ^ 5;')) == 0


def test_bitwise_not_zero():
    assert val(run('let v = ~0;')) == -1


def test_bitwise_not_neg1():
    assert val(run('let v = ~(-1);')) == 0


def test_left_shift_zero():
    assert val(run('let v = 5 << 0;')) == 5


def test_right_shift_zero():
    assert val(run('let v = 16 >> 0;')) == 16


def test_number_is_safe_integer():
    assert val(run('let v = Number.isSafeInteger(42);')) is True


def test_number_is_safe_integer_false():
    assert val(run('let v = Number.isSafeInteger(9007199254740992);')) is False


def test_number_is_integer():
    assert val(run('let v = Number.isInteger(42);')) is True


def test_number_is_integer_float():
    assert val(run('let v = Number.isInteger(42.5);')) is False


def test_number_is_finite():
    assert val(run('let v = Number.isFinite(42);')) is True


def test_number_is_nan():
    assert val(run('let v = Number.isNaN(NaN);')) is True


def test_number_is_nan_number():
    assert val(run('let v = Number.isNaN(42);')) is False


def test_power_of_two():
    assert val(run('let v = 2 ** 10;')) == 1024


def test_bitwise_compound_chain():
    assert val(run('let x = 0; x |= 1; x |= 2; x |= 4; let v = x;')) == 7


def test_bitwise_flag_check():
    assert val(run('let flags = 6; let v = (flags & 2) !== 0;')) is True


def test_floor_div_bitwise():
    # Bitwise OR with 0 truncates to 32-bit int (floor for positive)
    assert val(run('let v = (7 / 2 | 0);')) == 3
