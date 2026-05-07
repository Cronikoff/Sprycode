"""Tests for Phase 95: Math Advanced Methods
- clz32, fround, imul, cbrt, expm1, log1p, log2, log10
- sinh, cosh, tanh, asinh, acosh, atanh, hypot
- sign, trunc, max/min with spread
"""
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


# ── Math.clz32 ────────────────────────────────────────────────────────────────

class TestMathClz32:
    def test_clz32_one(self):
        i = run('let v = Math.clz32(1)')
        assert val(i) == 31

    def test_clz32_two(self):
        i = run('let v = Math.clz32(2)')
        assert val(i) == 30

    def test_clz32_max(self):
        i = run('let v = Math.clz32(0x80000000)')
        assert val(i) == 0

    def test_clz32_zero(self):
        i = run('let v = Math.clz32(0)')
        assert val(i) == 32


# ── Math.fround ───────────────────────────────────────────────────────────────

class TestMathFround:
    def test_fround_1(self):
        i = run('let v = Math.fround(1)')
        assert val(i) == pytest.approx(1.0)

    def test_fround_1_337(self):
        i = run('let v = Math.fround(1.337)')
        # Should be closest float32 representation
        import struct
        expected = struct.unpack('f', struct.pack('f', 1.337))[0]
        assert val(i) == pytest.approx(expected, rel=1e-5)

    def test_fround_zero(self):
        i = run('let v = Math.fround(0)')
        assert val(i) == 0.0


# ── Math.imul ─────────────────────────────────────────────────────────────────

class TestMathImul:
    def test_imul_2_4(self):
        i = run('let v = Math.imul(2, 4)')
        assert val(i) == 8

    def test_imul_10_10(self):
        i = run('let v = Math.imul(10, 10)')
        assert val(i) == 100

    def test_imul_zero(self):
        i = run('let v = Math.imul(0, 5)')
        assert val(i) == 0

    def test_imul_negative(self):
        i = run('let v = Math.imul(-1, 5)')
        # 32-bit int multiply: -1 * 5 = -5 (mod 2^32)
        assert val(i) == -5 or val(i) == (2**32 - 5)


# ── Math.cbrt ─────────────────────────────────────────────────────────────────

class TestMathCbrt:
    def test_cbrt_27(self):
        i = run('let v = Math.cbrt(27)')
        assert val(i) == pytest.approx(3.0)

    def test_cbrt_8(self):
        i = run('let v = Math.cbrt(8)')
        assert val(i) == pytest.approx(2.0)

    def test_cbrt_1(self):
        i = run('let v = Math.cbrt(1)')
        assert val(i) == pytest.approx(1.0)

    def test_cbrt_negative(self):
        i = run('let v = Math.cbrt(-8)')
        assert val(i) == pytest.approx(-2.0)

    def test_cbrt_zero(self):
        i = run('let v = Math.cbrt(0)')
        assert val(i) == pytest.approx(0.0)


# ── Math.expm1 ────────────────────────────────────────────────────────────────

class TestMathExpm1:
    def test_expm1_zero(self):
        i = run('let v = Math.expm1(0)')
        assert val(i) == pytest.approx(0.0)

    def test_expm1_one(self):
        i = run('let v = Math.expm1(1)')
        assert val(i) == pytest.approx(math.e - 1)

    def test_expm1_small(self):
        i = run('let v = Math.expm1(0.001)')
        assert val(i) == pytest.approx(math.expm1(0.001))


# ── Math.log1p ────────────────────────────────────────────────────────────────

class TestMathLog1p:
    def test_log1p_zero(self):
        i = run('let v = Math.log1p(0)')
        assert val(i) == pytest.approx(0.0)

    def test_log1p_one(self):
        i = run('let v = Math.log1p(1)')
        assert val(i) == pytest.approx(math.log(2))

    def test_log1p_small(self):
        i = run('let v = Math.log1p(0.001)')
        assert val(i) == pytest.approx(math.log1p(0.001))


# ── Math.log2 ─────────────────────────────────────────────────────────────────

class TestMathLog2:
    def test_log2_8(self):
        i = run('let v = Math.log2(8)')
        assert val(i) == pytest.approx(3.0)

    def test_log2_1024(self):
        i = run('let v = Math.log2(1024)')
        assert val(i) == pytest.approx(10.0)

    def test_log2_one(self):
        i = run('let v = Math.log2(1)')
        assert val(i) == pytest.approx(0.0)

    def test_log2_two(self):
        i = run('let v = Math.log2(2)')
        assert val(i) == pytest.approx(1.0)


# ── Math.log10 ────────────────────────────────────────────────────────────────

class TestMathLog10:
    def test_log10_1000(self):
        i = run('let v = Math.log10(1000)')
        assert val(i) == pytest.approx(3.0)

    def test_log10_100(self):
        i = run('let v = Math.log10(100)')
        assert val(i) == pytest.approx(2.0)

    def test_log10_one(self):
        i = run('let v = Math.log10(1)')
        assert val(i) == pytest.approx(0.0)

    def test_log10_tenth(self):
        i = run('let v = Math.log10(0.1)')
        assert val(i) == pytest.approx(-1.0)


# ── Math.sinh ─────────────────────────────────────────────────────────────────

class TestMathSinh:
    def test_sinh_zero(self):
        i = run('let v = Math.sinh(0)')
        assert val(i) == pytest.approx(0.0)

    def test_sinh_one(self):
        i = run('let v = Math.sinh(1)')
        assert val(i) == pytest.approx(math.sinh(1))

    def test_sinh_negative(self):
        i = run('let v = Math.sinh(-1)')
        assert val(i) == pytest.approx(math.sinh(-1))


# ── Math.cosh ─────────────────────────────────────────────────────────────────

class TestMathCosh:
    def test_cosh_zero(self):
        i = run('let v = Math.cosh(0)')
        assert val(i) == pytest.approx(1.0)

    def test_cosh_one(self):
        i = run('let v = Math.cosh(1)')
        assert val(i) == pytest.approx(math.cosh(1))


# ── Math.tanh ─────────────────────────────────────────────────────────────────

class TestMathTanh:
    def test_tanh_zero(self):
        i = run('let v = Math.tanh(0)')
        assert val(i) == pytest.approx(0.0)

    def test_tanh_one(self):
        i = run('let v = Math.tanh(1)')
        assert val(i) == pytest.approx(math.tanh(1))

    def test_tanh_large(self):
        i = run('let v = Math.tanh(100)')
        assert val(i) == pytest.approx(1.0)


# ── Math.asinh ────────────────────────────────────────────────────────────────

class TestMathAsinh:
    def test_asinh_zero(self):
        i = run('let v = Math.asinh(0)')
        assert val(i) == pytest.approx(0.0)

    def test_asinh_one(self):
        i = run('let v = Math.asinh(1)')
        assert val(i) == pytest.approx(math.asinh(1))


# ── Math.acosh ────────────────────────────────────────────────────────────────

class TestMathAcosh:
    def test_acosh_one(self):
        i = run('let v = Math.acosh(1)')
        assert val(i) == pytest.approx(0.0)

    def test_acosh_two(self):
        i = run('let v = Math.acosh(2)')
        assert val(i) == pytest.approx(math.acosh(2))


# ── Math.atanh ────────────────────────────────────────────────────────────────

class TestMathAtanh:
    def test_atanh_zero(self):
        i = run('let v = Math.atanh(0)')
        assert val(i) == pytest.approx(0.0)

    def test_atanh_half(self):
        i = run('let v = Math.atanh(0.5)')
        assert val(i) == pytest.approx(math.atanh(0.5))


# ── Math.hypot ────────────────────────────────────────────────────────────────

class TestMathHypot:
    def test_hypot_3_4(self):
        i = run('let v = Math.hypot(3, 4)')
        assert val(i) == pytest.approx(5.0)

    def test_hypot_5_12(self):
        i = run('let v = Math.hypot(5, 12)')
        assert val(i) == pytest.approx(13.0)

    def test_hypot_single(self):
        i = run('let v = Math.hypot(5)')
        assert val(i) == pytest.approx(5.0)

    def test_hypot_three_args(self):
        i = run('let v = Math.hypot(1, 2, 2)')
        assert val(i) == pytest.approx(3.0)


# ── Math.sign ─────────────────────────────────────────────────────────────────

class TestMathSign:
    def test_sign_negative(self):
        i = run('let v = Math.sign(-5)')
        assert val(i) == -1

    def test_sign_positive(self):
        i = run('let v = Math.sign(5)')
        assert val(i) == 1

    def test_sign_zero(self):
        i = run('let v = Math.sign(0)')
        assert val(i) == 0

    def test_sign_negative_float(self):
        i = run('let v = Math.sign(-0.001)')
        assert val(i) == -1

    def test_sign_positive_float(self):
        i = run('let v = Math.sign(0.001)')
        assert val(i) == 1


# ── Math.trunc ────────────────────────────────────────────────────────────────

class TestMathTrunc:
    def test_trunc_positive(self):
        i = run('let v = Math.trunc(4.7)')
        assert val(i) == 4

    def test_trunc_negative(self):
        i = run('let v = Math.trunc(-4.7)')
        assert val(i) == -4

    def test_trunc_zero(self):
        i = run('let v = Math.trunc(0.9)')
        assert val(i) == 0

    def test_trunc_whole(self):
        i = run('let v = Math.trunc(5.0)')
        assert val(i) == 5

    def test_trunc_neg_small(self):
        i = run('let v = Math.trunc(-0.1)')
        assert val(i) == 0


# ── Math.max / Math.min with spread ──────────────────────────────────────────

class TestMathMaxMinSpread:
    def test_max_spread(self):
        i = run('let a = [1, 5, 3]; let v = Math.max(...a)')
        assert val(i) == 5

    def test_min_spread(self):
        i = run('let a = [1, 5, 3]; let v = Math.min(...a)')
        assert val(i) == 1

    def test_max_spread_negative(self):
        i = run('let a = [-3, -1, -5]; let v = Math.max(...a)')
        assert val(i) == -1

    def test_min_spread_large(self):
        i = run('let a = [100, 200, 50]; let v = Math.min(...a)')
        assert val(i) == 50

    def test_max_no_spread(self):
        i = run('let v = Math.max(3, 1, 4, 1, 5, 9)')
        assert val(i) == 9

    def test_min_no_spread(self):
        i = run('let v = Math.min(3, 1, 4, 1, 5, 9)')
        assert val(i) == 1
