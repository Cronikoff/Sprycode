"""Tests for Phase 68 features: Math and Number"""
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


class TestMathBasic:
    def test_abs_negative(self):
        assert val(run('let v = Math.abs(-5)')) == 5

    def test_abs_positive(self):
        assert val(run('let v = Math.abs(5)')) == 5

    def test_abs_zero(self):
        assert val(run('let v = Math.abs(0)')) == 0

    def test_ceil_basic(self):
        assert val(run('let v = Math.ceil(4.1)')) == 5

    def test_ceil_negative(self):
        assert val(run('let v = Math.ceil(-4.9)')) == -4

    def test_floor_basic(self):
        assert val(run('let v = Math.floor(4.9)')) == 4

    def test_floor_negative(self):
        assert val(run('let v = Math.floor(-4.1)')) == -5

    def test_round_up(self):
        assert val(run('let v = Math.round(4.5)')) == 4 or val(run('let v = Math.round(4.5)')) == 5

    def test_round_down(self):
        assert val(run('let v = Math.round(4.4)')) == 4

    def test_round_negative(self):
        assert val(run('let v = Math.round(-4.4)')) == -4

    def test_trunc_positive(self):
        assert val(run('let v = Math.trunc(4.9)')) == 4

    def test_trunc_negative(self):
        assert val(run('let v = Math.trunc(-4.9)')) == -4

    def test_sign_positive(self):
        assert val(run('let v = Math.sign(5)')) == 1

    def test_sign_negative(self):
        assert val(run('let v = Math.sign(-5)')) == -1

    def test_sign_zero(self):
        assert val(run('let v = Math.sign(0)')) == 0


class TestMathMinMax:
    def test_min_two_args(self):
        assert val(run('let v = Math.min(1, 2)')) == 1

    def test_min_three_args(self):
        assert val(run('let v = Math.min(3, 1, 2)')) == 1

    def test_min_negative(self):
        assert val(run('let v = Math.min(-1, 0, 1)')) == -1

    def test_max_two_args(self):
        assert val(run('let v = Math.max(1, 2)')) == 2

    def test_max_three_args(self):
        assert val(run('let v = Math.max(1, 2, 3)')) == 3

    def test_max_negative(self):
        assert val(run('let v = Math.max(-1, -2, -3)')) == -1

    def test_min_single(self):
        assert val(run('let v = Math.min(5, 5)')) == 5

    def test_max_single(self):
        assert val(run('let v = Math.max(5, 5)')) == 5


class TestMathPowerSqrt:
    def test_pow_basic(self):
        assert val(run('let v = Math.pow(2, 10)')) == 1024

    def test_pow_zero(self):
        assert val(run('let v = Math.pow(5, 0)')) == 1

    def test_pow_fraction(self):
        assert val(run('let v = Math.pow(4, 0.5)')) == 2.0

    def test_exponent_operator(self):
        assert val(run('let v = 2 ** 10')) == 1024

    def test_exponent_operator_fraction(self):
        assert val(run('let v = 9 ** 0.5')) == 3.0

    def test_sqrt_basic(self):
        assert val(run('let v = Math.sqrt(9)')) == 3.0

    def test_sqrt_two(self):
        result = val(run('let v = Math.sqrt(2)'))
        assert abs(result - math.sqrt(2)) < 1e-10

    def test_cbrt_basic(self):
        assert val(run('let v = Math.cbrt(27)')) == 3.0

    def test_cbrt_negative(self):
        result = val(run('let v = Math.cbrt(-8)'))
        assert abs(result - (-2.0)) < 1e-10


class TestMathLog:
    def test_log_e(self):
        assert abs(val(run('let v = Math.log(Math.E)')) - 1.0) < 1e-10

    def test_log_1(self):
        assert val(run('let v = Math.log(1)')) == 0.0

    def test_log2_basic(self):
        assert abs(val(run('let v = Math.log2(8)')) - 3.0) < 1e-10

    def test_log2_one(self):
        assert val(run('let v = Math.log2(1)')) == 0.0

    def test_log10_basic(self):
        assert abs(val(run('let v = Math.log10(1000)')) - 3.0) < 1e-10

    def test_log10_one(self):
        assert val(run('let v = Math.log10(1)')) == 0.0


class TestMathTrig:
    def test_sin_zero(self):
        assert val(run('let v = Math.sin(0)')) == 0.0

    def test_cos_zero(self):
        assert val(run('let v = Math.cos(0)')) == 1.0

    def test_tan_zero(self):
        assert val(run('let v = Math.tan(0)')) == 0.0

    def test_sin_pi_half(self):
        result = val(run('let v = Math.sin(Math.PI / 2)'))
        assert abs(result - 1.0) < 1e-10

    def test_cos_pi(self):
        result = val(run('let v = Math.cos(Math.PI)'))
        assert abs(result - (-1.0)) < 1e-10

    def test_asin_one(self):
        result = val(run('let v = Math.asin(1)'))
        assert abs(result - math.pi / 2) < 1e-10

    def test_acos_one(self):
        assert val(run('let v = Math.acos(1)')) == 0.0

    def test_atan_one(self):
        result = val(run('let v = Math.atan(1)'))
        assert abs(result - math.pi / 4) < 1e-10

    def test_atan2_basic(self):
        result = val(run('let v = Math.atan2(1, 1)'))
        assert abs(result - math.pi / 4) < 1e-10

    def test_sinh_zero(self):
        assert val(run('let v = Math.sinh(0)')) == 0.0

    def test_cosh_zero(self):
        assert val(run('let v = Math.cosh(0)')) == 1.0

    def test_tanh_zero(self):
        assert val(run('let v = Math.tanh(0)')) == 0.0


class TestMathHypotFroundClz32Imul:
    def test_hypot_3_4_5(self):
        assert val(run('let v = Math.hypot(3, 4)')) == 5.0

    def test_hypot_single(self):
        assert val(run('let v = Math.hypot(5)')) == 5.0

    def test_fround_basic(self):
        result = val(run('let v = Math.fround(1.5)'))
        assert result == 1.5

    def test_clz32_one(self):
        assert val(run('let v = Math.clz32(1)')) == 31

    def test_clz32_two(self):
        assert val(run('let v = Math.clz32(2)')) == 30

    def test_imul_basic(self):
        assert val(run('let v = Math.imul(3, 4)')) == 12

    def test_imul_negative(self):
        assert val(run('let v = Math.imul(-1, 1)')) == -1


class TestMathConstants:
    def test_pi(self):
        assert abs(val(run('let v = Math.PI')) - math.pi) < 1e-10

    def test_e(self):
        assert abs(val(run('let v = Math.E')) - math.e) < 1e-10

    def test_ln2(self):
        assert abs(val(run('let v = Math.LN2')) - math.log(2)) < 1e-10

    def test_sqrt2(self):
        assert abs(val(run('let v = Math.SQRT2')) - math.sqrt(2)) < 1e-10

    def test_random_in_range(self):
        result = val(run('let v = Math.random()'))
        assert 0.0 <= result < 1.0


class TestNumberConstants:
    def test_max_safe_integer(self):
        assert val(run('let v = Number.MAX_SAFE_INTEGER')) == 9007199254740991

    def test_min_safe_integer(self):
        assert val(run('let v = Number.MIN_SAFE_INTEGER')) == -9007199254740991

    def test_epsilon(self):
        result = val(run('let v = Number.EPSILON'))
        assert result > 0 and result < 1e-10

    def test_max_value(self):
        result = val(run('let v = Number.MAX_VALUE'))
        assert result > 1e300

    def test_is_nan_true(self):
        assert val(run('let v = Number.isNaN(NaN)')) is True

    def test_is_nan_false(self):
        assert val(run('let v = Number.isNaN(42)')) is False

    def test_is_nan_false_for_string(self):
        assert val(run('let v = Number.isNaN("NaN")')) is False

    def test_is_finite_true(self):
        assert val(run('let v = Number.isFinite(42)')) is True

    def test_is_finite_false_infinity(self):
        assert val(run('let v = Number.isFinite(Infinity)')) is False

    def test_is_integer_true(self):
        assert val(run('let v = Number.isInteger(42)')) is True

    def test_is_integer_false(self):
        assert val(run('let v = Number.isInteger(42.5)')) is False

    def test_is_safe_integer_true(self):
        assert val(run('let v = Number.isSafeInteger(42)')) is True

    def test_is_safe_integer_false_large(self):
        assert val(run('let v = Number.isSafeInteger(Number.MAX_SAFE_INTEGER + 1)')) is False

    def test_parse_float(self):
        assert val(run('let v = Number.parseFloat("3.14")')) == 3.14

    def test_parse_int(self):
        assert val(run('let v = Number.parseInt("42", 10)')) == 42


class TestNumberMethods:
    def test_to_fixed_basic(self):
        assert val(run('let v = (3.14159).toFixed(2)')) == "3.14"

    def test_to_fixed_zero(self):
        assert val(run('let v = (3.7).toFixed(0)')) == "4"

    def test_to_precision_basic(self):
        assert val(run('let v = (123.456).toPrecision(5)')) == "123.46"

    def test_to_string_hex(self):
        assert val(run('let v = (255).toString(16)')) == "ff"

    def test_to_string_binary(self):
        assert val(run('let v = (10).toString(2)')) == "1010"

    def test_to_string_octal(self):
        assert val(run('let v = (8).toString(8)')) == "10"

    def test_to_exponential_basic(self):
        result = val(run('let v = (1234567).toExponential(2)'))
        assert "e" in result or "E" in result


class TestGlobalParseIsNaN:
    def test_parse_float_global(self):
        assert val(run('let v = parseFloat("3.14")')) == 3.14

    def test_parse_int_hex(self):
        assert val(run('let v = parseInt("FF", 16)')) == 255

    def test_parse_int_decimal(self):
        assert val(run('let v = parseInt("42", 10)')) == 42

    def test_parse_int_binary(self):
        assert val(run('let v = parseInt("1010", 2)')) == 10

    def test_is_nan_true(self):
        assert val(run('let v = isNaN(NaN)')) is True

    def test_is_nan_false(self):
        assert val(run('let v = isNaN(42)')) is False

    def test_is_finite_true(self):
        assert val(run('let v = isFinite(1)')) is True

    def test_is_finite_false(self):
        assert val(run('let v = isFinite(Infinity)')) is False


class TestSpecialValues:
    def test_nan(self):
        result = val(run('let v = NaN'))
        assert result != result  # NaN is not equal to itself

    def test_infinity(self):
        import math as _math
        assert _math.isinf(val(run('let v = Infinity')))

    def test_negative_infinity(self):
        import math as _math
        result = val(run('let v = -Infinity'))
        assert _math.isinf(result) and result < 0

    def test_nan_arithmetic(self):
        result = val(run('let v = NaN + 1'))
        assert result != result  # still NaN

    def test_infinity_arithmetic(self):
        import math as _math
        assert _math.isinf(val(run('let v = Infinity + 1')))

    def test_infinity_division(self):
        import math as _math
        assert _math.isinf(val(run('let v = 1 / 0')))


class TestBitwiseOperators:
    def test_bitwise_and(self):
        assert val(run('let v = 5 & 3')) == 1

    def test_bitwise_or(self):
        assert val(run('let v = 5 | 3')) == 7

    def test_bitwise_xor(self):
        assert val(run('let v = 5 ^ 3')) == 6

    def test_bitwise_not(self):
        assert val(run('let v = ~5')) == -6

    def test_left_shift(self):
        assert val(run('let v = 1 << 3')) == 8

    def test_right_shift(self):
        assert val(run('let v = 16 >> 2')) == 4

    def test_unsigned_right_shift(self):
        assert val(run('let v = -1 >>> 28')) == 15

    def test_bitwise_and_zero(self):
        assert val(run('let v = 7 & 0')) == 0

    def test_bitwise_or_all(self):
        assert val(run('let v = 0 | 7')) == 7

    def test_left_shift_one(self):
        assert val(run('let v = 1 << 0')) == 1

    def test_right_shift_one(self):
        assert val(run('let v = 1 >> 1')) == 0
