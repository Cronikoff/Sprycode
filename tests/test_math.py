"""
Tests for the math and stats expansion.

Covers:
 - math.* constants (TAU, PHI, SQRT2, LN2, LOG2E, LOG10E, EPSILON, NAN, INFINITY)
 - Logarithms/exponentials: ln, logN, exp, expm1, log1p
 - Trigonometry: asin, acos, atan, atan2, sinh, cosh, tanh, asinh, acosh, atanh, sec, csc, cot, hypot
 - Angle conversion: degToRad, radToDeg, toRadians, toDegrees
 - Roots: cbrt, nthRoot
 - Rounding utilities: roundTo, toSF, frac, trunc, sign
 - Number predicates: isEven, isOdd, isInteger, isFinite, isNaN, isBetween
 - Integer utilities: intDiv, mod, clamp, lerp
 - Number theory: gcd, lcm, factorial, fibonacci, isPrime, isPerfect,
                  primes, primeFactors, combination, permutation, bernoulli,
                  divisors, totient
 - Digit utilities: digits, sumDigits, reverseDigits, isPalindrome
 - Statistics on math.*: mean, median, mode, variance, stdDev, range,
                         percentile, quartiles, correlation, dot, normalize, sum, product
 - Algebra solvers: math.quadratic, math.linearSolve
 - Sequences: arithmetic, geometric, sumAP, sumGP, sumInfGP
 - Geometry: circleArea, circumference, triangleArea, heronArea, distance, slope, midpoint
 - stats namespace mirrors
 - End-to-end mathematical programs (quadratic, compound interest, AP/GP sums)
"""

import math as _math
import pytest

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.runtime.stdlib import SpryLogger


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    out: list[str] = []
    interp = Interpreter(logger=SpryLogger(output=out))
    interp.run(program)
    return interp


def approx(val: float, expected: float, rel: float = 1e-9) -> bool:
    if expected == 0:
        return abs(val) < 1e-12
    return abs(val - expected) / abs(expected) < rel


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


class TestMathConstants:
    def test_pi(self):
        i = run("let v = math.PI")
        assert approx(i.globals.get("v"), _math.pi)

    def test_e(self):
        i = run("let v = math.E")
        assert approx(i.globals.get("v"), _math.e)

    def test_tau(self):
        i = run("let v = math.TAU")
        assert approx(i.globals.get("v"), _math.tau)

    def test_phi(self):
        i = run("let v = math.PHI")
        assert approx(i.globals.get("v"), (1 + _math.sqrt(5)) / 2)

    def test_sqrt2(self):
        i = run("let v = math.SQRT2")
        assert approx(i.globals.get("v"), _math.sqrt(2))

    def test_sqrt1_2(self):
        i = run("let v = math.SQRT1_2")
        assert approx(i.globals.get("v"), _math.sqrt(0.5))

    def test_ln2(self):
        i = run("let v = math.LN2")
        assert approx(i.globals.get("v"), _math.log(2))

    def test_ln10(self):
        i = run("let v = math.LN10")
        assert approx(i.globals.get("v"), _math.log(10))

    def test_log2e(self):
        i = run("let v = math.LOG2E")
        assert approx(i.globals.get("v"), _math.log2(_math.e))

    def test_log10e(self):
        i = run("let v = math.LOG10E")
        assert approx(i.globals.get("v"), _math.log10(_math.e))

    def test_epsilon(self):
        i = run("let v = math.EPSILON")
        assert i.globals.get("v") == 2.220446049250313e-16

    def test_inf(self):
        import math
        i = run("let v = math.INF")
        assert math.isinf(i.globals.get("v"))

    def test_infinity_alias(self):
        import math
        i = run("let v = math.INFINITY")
        assert math.isinf(i.globals.get("v"))

    def test_nan(self):
        import math
        i = run("let v = math.NAN")
        assert math.isnan(i.globals.get("v"))


# ─────────────────────────────────────────────────────────────────────────────
# Logarithms & Exponentials
# ─────────────────────────────────────────────────────────────────────────────


class TestLogarithmsExponentials:
    def test_ln_one(self):
        i = run("let v = math.ln(1)")
        assert i.globals.get("v") == 0.0

    def test_ln_e(self):
        i = run("let v = math.ln(math.E)")
        assert approx(i.globals.get("v"), 1.0)

    def test_log_base_10(self):
        i = run("let v = math.log(100, 10)")
        assert approx(i.globals.get("v"), 2.0)

    def test_log2_eight(self):
        i = run("let v = math.log2(8)")
        assert approx(i.globals.get("v"), 3.0)

    def test_log10_thousand(self):
        i = run("let v = math.log10(1000)")
        assert approx(i.globals.get("v"), 3.0)

    def test_logN(self):
        i = run("let v = math.logN(8, 2)")
        assert approx(i.globals.get("v"), 3.0)

    def test_logN_base_10(self):
        i = run("let v = math.logN(100, 10)")
        assert approx(i.globals.get("v"), 2.0)

    def test_exp_zero(self):
        i = run("let v = math.exp(0)")
        assert i.globals.get("v") == 1.0

    def test_exp_one(self):
        i = run("let v = math.exp(1)")
        assert approx(i.globals.get("v"), _math.e)

    def test_expm1_zero(self):
        i = run("let v = math.expm1(0)")
        assert i.globals.get("v") == 0.0

    def test_log1p_zero(self):
        i = run("let v = math.log1p(0)")
        assert i.globals.get("v") == 0.0

    def test_log1p_identity(self):
        # log1p(e-1) ≈ 1
        i = run("let v = math.log1p(math.E - 1)")
        assert approx(i.globals.get("v"), 1.0)

    def test_nested_log_pow(self):
        # log2(2^8) == 8
        i = run("let v = math.logN(math.pow(2, 8), 2)")
        assert approx(i.globals.get("v"), 8.0)


# ─────────────────────────────────────────────────────────────────────────────
# Trigonometry
# ─────────────────────────────────────────────────────────────────────────────


class TestTrigonometry:
    def test_sin_zero(self):
        i = run("let v = math.sin(0)")
        assert i.globals.get("v") == 0.0

    def test_cos_zero(self):
        i = run("let v = math.cos(0)")
        assert i.globals.get("v") == 1.0

    def test_tan_zero(self):
        i = run("let v = math.tan(0)")
        assert i.globals.get("v") == 0.0

    def test_sin_pi_half(self):
        i = run("let v = math.sin(math.PI / 2)")
        assert approx(i.globals.get("v"), 1.0)

    def test_cos_pi(self):
        i = run("let v = math.cos(math.PI)")
        assert approx(i.globals.get("v"), -1.0)

    def test_asin_zero(self):
        i = run("let v = math.asin(0)")
        assert i.globals.get("v") == 0.0

    def test_acos_one(self):
        i = run("let v = math.acos(1)")
        assert i.globals.get("v") == 0.0

    def test_atan_zero(self):
        i = run("let v = math.atan(0)")
        assert i.globals.get("v") == 0.0

    def test_atan2_origin(self):
        i = run("let v = math.atan2(0, 1)")
        assert i.globals.get("v") == 0.0

    def test_atan2_quadrant1(self):
        i = run("let v = math.atan2(1, 1)")
        assert approx(i.globals.get("v"), _math.pi / 4)

    def test_sinh_zero(self):
        i = run("let v = math.sinh(0)")
        assert i.globals.get("v") == 0.0

    def test_cosh_zero(self):
        i = run("let v = math.cosh(0)")
        assert i.globals.get("v") == 1.0

    def test_tanh_zero(self):
        i = run("let v = math.tanh(0)")
        assert i.globals.get("v") == 0.0

    def test_asinh_zero(self):
        i = run("let v = math.asinh(0)")
        assert i.globals.get("v") == 0.0

    def test_acosh_one(self):
        i = run("let v = math.acosh(1)")
        assert i.globals.get("v") == 0.0

    def test_atanh_zero(self):
        i = run("let v = math.atanh(0)")
        assert i.globals.get("v") == 0.0

    def test_sec_zero(self):
        i = run("let v = math.sec(0)")
        assert i.globals.get("v") == 1.0

    def test_csc_pi_half(self):
        i = run("let v = math.csc(math.PI / 2)")
        assert approx(i.globals.get("v"), 1.0)

    def test_cot_pi_quarter(self):
        i = run("let v = math.cot(math.PI / 4)")
        assert approx(i.globals.get("v"), 1.0)

    def test_hypot_3_4(self):
        i = run("let v = math.hypot(3, 4)")
        assert i.globals.get("v") == 5.0

    def test_hypot_3d(self):
        # 3-D hypot
        i = run("let v = math.hypot(1, 2, 2)")
        assert i.globals.get("v") == 3.0

    def test_pythagorean_identity(self):
        i = run("let a = math.sin(1.2)\nlet b = math.cos(1.2)\nlet v = a*a + b*b")
        assert approx(i.globals.get("v"), 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Angle conversions
# ─────────────────────────────────────────────────────────────────────────────


class TestAngleConversion:
    def test_deg_to_rad_180(self):
        i = run("let v = math.degToRad(180)")
        assert approx(i.globals.get("v"), _math.pi)

    def test_deg_to_rad_90(self):
        i = run("let v = math.degToRad(90)")
        assert approx(i.globals.get("v"), _math.pi / 2)

    def test_rad_to_deg_pi(self):
        i = run("let v = math.radToDeg(math.PI)")
        assert approx(i.globals.get("v"), 180.0)

    def test_to_radians_alias(self):
        i = run("let v = math.toRadians(360)")
        assert approx(i.globals.get("v"), _math.tau)

    def test_to_degrees_alias(self):
        i = run("let v = math.toDegrees(math.TAU)")
        assert approx(i.globals.get("v"), 360.0)

    def test_round_trip(self):
        i = run("let v = math.radToDeg(math.degToRad(45))")
        assert approx(i.globals.get("v"), 45.0)


# ─────────────────────────────────────────────────────────────────────────────
# Roots
# ─────────────────────────────────────────────────────────────────────────────


class TestRoots:
    def test_sqrt(self):
        i = run("let v = math.sqrt(16)")
        assert i.globals.get("v") == 4.0

    def test_cbrt_positive(self):
        i = run("let v = math.cbrt(27)")
        assert approx(i.globals.get("v"), 3.0)

    def test_cbrt_negative(self):
        i = run("let v = math.cbrt(-8)")
        assert approx(i.globals.get("v"), -2.0)

    def test_nth_root_cube(self):
        i = run("let v = math.nthRoot(27, 3)")
        assert approx(i.globals.get("v"), 3.0)

    def test_nth_root_square(self):
        i = run("let v = math.nthRoot(25, 2)")
        assert approx(i.globals.get("v"), 5.0)

    def test_nth_root_fifth(self):
        i = run("let v = math.nthRoot(32, 5)")
        assert approx(i.globals.get("v"), 2.0)

    def test_pow(self):
        i = run("let v = math.pow(2, 10)")
        assert i.globals.get("v") == 1024


# ─────────────────────────────────────────────────────────────────────────────
# Arithmetic utilities
# ─────────────────────────────────────────────────────────────────────────────


class TestArithmeticUtils:
    def test_abs_negative(self):
        i = run("let v = math.abs(-7)")
        assert i.globals.get("v") == 7

    def test_floor(self):
        i = run("let v = math.floor(3.9)")
        assert i.globals.get("v") == 3

    def test_ceil(self):
        i = run("let v = math.ceil(3.1)")
        assert i.globals.get("v") == 4

    def test_round(self):
        i = run("let v = math.round(3.5)")
        assert i.globals.get("v") == 4

    def test_round_to(self):
        i = run("let v = math.roundTo(3.14159, 2)")
        assert i.globals.get("v") == 3.14

    def test_to_sf_three(self):
        i = run("let v = math.toSF(12345, 3)")
        assert i.globals.get("v") == 12300.0

    def test_trunc(self):
        i = run("let v = math.trunc(3.9)")
        assert i.globals.get("v") == 3

    def test_frac(self):
        i = run("let v = math.frac(3.75)")
        assert approx(i.globals.get("v"), 0.75)

    def test_sign_positive(self):
        i = run("let v = math.sign(5)")
        assert i.globals.get("v") == 1

    def test_sign_negative(self):
        i = run("let v = math.sign(-5)")
        assert i.globals.get("v") == -1

    def test_sign_zero(self):
        i = run("let v = math.sign(0)")
        assert i.globals.get("v") == 0

    def test_clamp_above(self):
        i = run("let v = math.clamp(15, 0, 10)")
        assert i.globals.get("v") == 10

    def test_clamp_below(self):
        i = run("let v = math.clamp(-5, 0, 10)")
        assert i.globals.get("v") == 0

    def test_lerp_half(self):
        i = run("let v = math.lerp(0, 10, 0.5)")
        assert i.globals.get("v") == 5.0

    def test_lerp_full(self):
        i = run("let v = math.lerp(0, 100, 1.0)")
        assert i.globals.get("v") == 100.0

    def test_int_div(self):
        i = run("let v = math.intDiv(10, 3)")
        assert i.globals.get("v") == 3

    def test_mod(self):
        i = run("let v = math.mod(10, 3)")
        assert i.globals.get("v") == 1

    def test_is_even(self):
        i = run("let v = math.isEven(4)")
        assert i.globals.get("v") is True

    def test_is_odd(self):
        i = run("let v = math.isOdd(7)")
        assert i.globals.get("v") is True

    def test_is_integer_int(self):
        i = run("let v = math.isInteger(5)")
        assert i.globals.get("v") is True

    def test_is_integer_float_whole(self):
        i = run("let v = math.isInteger(5.0)")
        assert i.globals.get("v") is True

    def test_is_integer_float_frac(self):
        i = run("let v = math.isInteger(5.5)")
        assert i.globals.get("v") is False

    def test_is_between_inside(self):
        i = run("let v = math.isBetween(5, 0, 10)")
        assert i.globals.get("v") is True

    def test_is_between_outside(self):
        i = run("let v = math.isBetween(15, 0, 10)")
        assert i.globals.get("v") is False

    def test_is_finite(self):
        i = run("let v = math.isFinite(42)")
        assert i.globals.get("v") is True

    def test_is_nan(self):
        i = run("let v = math.isNaN(math.NAN)")
        assert i.globals.get("v") is True

    def test_min_two(self):
        i = run("let v = math.min(3, 7)")
        assert i.globals.get("v") == 3

    def test_max_two(self):
        i = run("let v = math.max(3, 7)")
        assert i.globals.get("v") == 7

    def test_min_list(self):
        i = run("let v = math.min([5, 1, 3, 2])")
        assert i.globals.get("v") == 1

    def test_max_list(self):
        i = run("let v = math.max([5, 1, 3, 2])")
        assert i.globals.get("v") == 5

    def test_sum_list(self):
        i = run("let v = math.sum([1, 2, 3, 4, 5])")
        assert i.globals.get("v") == 15

    def test_product_list(self):
        i = run("let v = math.product([1, 2, 3, 4])")
        assert i.globals.get("v") == 24


# ─────────────────────────────────────────────────────────────────────────────
# Number theory
# ─────────────────────────────────────────────────────────────────────────────


class TestNumberTheory:
    def test_gcd(self):
        i = run("let v = math.gcd(12, 8)")
        assert i.globals.get("v") == 4

    def test_gcd_coprime(self):
        i = run("let v = math.gcd(7, 13)")
        assert i.globals.get("v") == 1

    def test_lcm(self):
        i = run("let v = math.lcm(4, 6)")
        assert i.globals.get("v") == 12

    def test_lcm_coprime(self):
        i = run("let v = math.lcm(5, 7)")
        assert i.globals.get("v") == 35

    def test_factorial_five(self):
        i = run("let v = math.factorial(5)")
        assert i.globals.get("v") == 120

    def test_factorial_zero(self):
        i = run("let v = math.factorial(0)")
        assert i.globals.get("v") == 1

    def test_fibonacci_zero(self):
        i = run("let v = math.fibonacci(0)")
        assert i.globals.get("v") == 0

    def test_fibonacci_one(self):
        i = run("let v = math.fibonacci(1)")
        assert i.globals.get("v") == 1

    def test_fibonacci_ten(self):
        i = run("let v = math.fibonacci(10)")
        assert i.globals.get("v") == 55

    def test_fibonacci_fifteen(self):
        i = run("let v = math.fibonacci(15)")
        assert i.globals.get("v") == 610

    def test_is_prime_true(self):
        i = run("let v = math.isPrime(7)")
        assert i.globals.get("v") is True

    def test_is_prime_false(self):
        i = run("let v = math.isPrime(4)")
        assert i.globals.get("v") is False

    def test_is_prime_two(self):
        i = run("let v = math.isPrime(2)")
        assert i.globals.get("v") is True

    def test_is_prime_one(self):
        i = run("let v = math.isPrime(1)")
        assert i.globals.get("v") is False

    def test_is_perfect_six(self):
        i = run("let v = math.isPerfect(6)")
        assert i.globals.get("v") is True

    def test_is_perfect_twenty_eight(self):
        i = run("let v = math.isPerfect(28)")
        assert i.globals.get("v") is True

    def test_is_perfect_false(self):
        i = run("let v = math.isPerfect(10)")
        assert i.globals.get("v") is False

    def test_primes_up_to_ten(self):
        i = run("let v = math.primes(10)")
        assert i.globals.get("v") == [2, 3, 5, 7]

    def test_primes_up_to_twenty(self):
        i = run("let v = math.primes(20)")
        assert i.globals.get("v") == [2, 3, 5, 7, 11, 13, 17, 19]

    def test_prime_factors_twelve(self):
        i = run("let v = math.primeFactors(12)")
        assert i.globals.get("v") == [2, 2, 3]

    def test_prime_factors_prime(self):
        i = run("let v = math.primeFactors(7)")
        assert i.globals.get("v") == [7]

    def test_combination(self):
        i = run("let v = math.combination(5, 2)")
        assert i.globals.get("v") == 10

    def test_combination_zero(self):
        i = run("let v = math.combination(5, 0)")
        assert i.globals.get("v") == 1

    def test_permutation(self):
        i = run("let v = math.permutation(5, 2)")
        assert i.globals.get("v") == 20

    def test_divisors(self):
        i = run("let v = math.divisors(12)")
        assert i.globals.get("v") == [1, 2, 3, 4, 6, 12]

    def test_divisors_prime(self):
        i = run("let v = math.divisors(7)")
        assert i.globals.get("v") == [1, 7]

    def test_totient_prime(self):
        i = run("let v = math.totient(7)")
        assert i.globals.get("v") == 6

    def test_totient_six(self):
        i = run("let v = math.totient(6)")
        assert i.globals.get("v") == 2

    def test_bernoulli_zero(self):
        i = run("let v = math.bernoulli(0)")
        assert approx(i.globals.get("v"), 1.0)

    def test_bernoulli_one(self):
        i = run("let v = math.bernoulli(1)")
        assert approx(i.globals.get("v"), -0.5)

    def test_bernoulli_two(self):
        i = run("let v = math.bernoulli(2)")
        assert approx(i.globals.get("v"), 1 / 6)

    def test_bernoulli_odd_gt1(self):
        # All odd Bernoulli numbers > B1 are 0
        i = run("let v = math.bernoulli(3)")
        assert approx(i.globals.get("v"), 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Digit utilities
# ─────────────────────────────────────────────────────────────────────────────


class TestDigitUtils:
    def test_digits(self):
        i = run("let v = math.digits(1234)")
        assert i.globals.get("v") == [1, 2, 3, 4]

    def test_digits_single(self):
        i = run("let v = math.digits(7)")
        assert i.globals.get("v") == [7]

    def test_sum_digits(self):
        i = run("let v = math.sumDigits(1234)")
        assert i.globals.get("v") == 10

    def test_sum_digits_nine_nine(self):
        i = run("let v = math.sumDigits(99)")
        assert i.globals.get("v") == 18

    def test_reverse_digits(self):
        i = run("let v = math.reverseDigits(1234)")
        assert i.globals.get("v") == 4321

    def test_is_palindrome_true(self):
        i = run("let v = math.isPalindrome(121)")
        assert i.globals.get("v") is True

    def test_is_palindrome_false(self):
        i = run("let v = math.isPalindrome(123)")
        assert i.globals.get("v") is False


# ─────────────────────────────────────────────────────────────────────────────
# Statistics (math.*)
# ─────────────────────────────────────────────────────────────────────────────


class TestMathStats:
    def test_mean(self):
        i = run("let v = math.mean([1, 2, 3, 4, 5])")
        assert i.globals.get("v") == 3.0

    def test_median_odd(self):
        i = run("let v = math.median([1, 3, 5])")
        assert i.globals.get("v") == 3.0

    def test_median_even(self):
        i = run("let v = math.median([1, 2, 3, 4])")
        assert i.globals.get("v") == 2.5

    def test_mode(self):
        i = run("let v = math.mode([1, 2, 2, 3, 3, 3])")
        assert i.globals.get("v") == 3

    def test_variance(self):
        # Known: population variance of [2,4,4,4,5,5,7,9] == 4
        i = run("let v = math.variance([2, 4, 4, 4, 5, 5, 7, 9])")
        assert i.globals.get("v") == 4.0

    def test_std_dev(self):
        i = run("let v = math.stdDev([2, 4, 4, 4, 5, 5, 7, 9])")
        assert i.globals.get("v") == 2.0

    def test_range(self):
        i = run("let v = math.range([1, 2, 3, 4, 5])")
        assert i.globals.get("v") == 4

    def test_percentile_50(self):
        i = run("let v = math.percentile([1, 2, 3, 4, 5], 50)")
        assert i.globals.get("v") == 3.0

    def test_percentile_0(self):
        i = run("let v = math.percentile([1, 2, 3, 4, 5], 0)")
        assert i.globals.get("v") == 1.0

    def test_percentile_100(self):
        i = run("let v = math.percentile([1, 2, 3, 4, 5], 100)")
        assert i.globals.get("v") == 5.0

    def test_quartiles(self):
        i = run("let v = math.quartiles([1, 2, 3, 4, 5])")
        val = i.globals.get("v")
        assert len(val) == 3
        assert val[1] == 3.0  # Q2 == median

    def test_correlation_perfect(self):
        # Perfect positive correlation
        i = run("let v = math.correlation([1, 2, 3], [1, 2, 3])")
        assert approx(i.globals.get("v"), 1.0)

    def test_correlation_inverse(self):
        i = run("let v = math.correlation([1, 2, 3], [3, 2, 1])")
        assert approx(i.globals.get("v"), -1.0)

    def test_dot(self):
        i = run("let v = math.dot([1, 2, 3], [4, 5, 6])")
        assert i.globals.get("v") == 32.0

    def test_normalize(self):
        i = run("let v = math.normalize([0, 5, 10])")
        assert i.globals.get("v") == [0.0, 0.5, 1.0]


# ─────────────────────────────────────────────────────────────────────────────
# stats namespace
# ─────────────────────────────────────────────────────────────────────────────


class TestStatsNamespace:
    def test_mean(self):
        i = run("let v = stats.mean([10, 20, 30])")
        assert i.globals.get("v") == 20.0

    def test_median(self):
        i = run("let v = stats.median([3, 1, 4, 1, 5])")
        assert i.globals.get("v") == 3.0

    def test_mode(self):
        i = run("let v = stats.mode([1, 2, 2, 3])")
        assert i.globals.get("v") == 2

    def test_std_dev(self):
        i = run("let v = stats.stdDev([2, 4, 4, 4, 5, 5, 7, 9])")
        assert i.globals.get("v") == 2.0

    def test_variance(self):
        i = run("let v = stats.variance([2, 4, 4, 4, 5, 5, 7, 9])")
        assert i.globals.get("v") == 4.0

    def test_range(self):
        i = run("let v = stats.range([10, 20, 30, 40, 50])")
        assert i.globals.get("v") == 40

    def test_sum(self):
        i = run("let v = stats.sum([1, 2, 3, 4, 5])")
        assert i.globals.get("v") == 15

    def test_product(self):
        i = run("let v = stats.product([1, 2, 3, 4])")
        assert i.globals.get("v") == 24

    def test_min(self):
        i = run("let v = stats.min([5, 3, 8, 1])")
        assert i.globals.get("v") == 1

    def test_max(self):
        i = run("let v = stats.max([5, 3, 8, 1])")
        assert i.globals.get("v") == 8

    def test_percentile(self):
        i = run("let v = stats.percentile([1, 2, 3, 4, 5], 75)")
        assert i.globals.get("v") == 4.0

    def test_quartiles(self):
        i = run("let v = stats.quartiles([1, 2, 3, 4, 5])")
        val = i.globals.get("v")
        assert len(val) == 3

    def test_correlation(self):
        i = run("let v = stats.correlation([1, 2, 3], [2, 4, 6])")
        assert approx(i.globals.get("v"), 1.0)

    def test_normalize(self):
        i = run("let v = stats.normalize([0, 10, 20])")
        assert i.globals.get("v") == [0.0, 0.5, 1.0]

    def test_zscore(self):
        i = run("let v = stats.zscore([2, 4, 4, 4, 5, 5, 7, 9])")
        val = i.globals.get("v")
        assert isinstance(val, list) and len(val) == 8

    def test_frequency(self):
        i = run("let v = stats.frequency([1, 2, 2, 3, 3, 3])")
        assert i.globals.get("v") == {1: 1, 2: 2, 3: 3}


# ─────────────────────────────────────────────────────────────────────────────
# Algebra solvers
# ─────────────────────────────────────────────────────────────────────────────


class TestAlgebraSolvers:
    def test_quadratic_two_roots(self):
        i = run("let v = math.quadratic(1, -5, 6)")
        val = i.globals.get("v")
        assert sorted(val) == [2.0, 3.0]

    def test_quadratic_one_root(self):
        # x² - 2x + 1 = 0 → (x-1)²
        i = run("let v = math.quadratic(1, -2, 1)")
        val = i.globals.get("v")
        assert val == [1.0]

    def test_quadratic_no_real_roots(self):
        # x² + 1 = 0
        i = run("let v = math.quadratic(1, 0, 1)")
        assert i.globals.get("v") == []

    def test_quadratic_linear_degenerate(self):
        # a=0: 2x - 6 = 0 → x = 3
        i = run("let v = math.quadratic(0, 2, -6)")
        assert i.globals.get("v") == [3.0]

    def test_linear_solve(self):
        i = run("let v = math.linearSolve(2, -6)")
        assert i.globals.get("v") == 3.0

    def test_linear_solve_negative(self):
        i = run("let v = math.linearSolve(3, 9)")
        assert i.globals.get("v") == -3.0


# ─────────────────────────────────────────────────────────────────────────────
# Sequences
# ─────────────────────────────────────────────────────────────────────────────


class TestSequences:
    def test_arithmetic_four_terms(self):
        i = run("let v = math.arithmetic(1, 2, 4)")
        assert i.globals.get("v") == [1.0, 3.0, 5.0, 7.0]

    def test_arithmetic_descending(self):
        i = run("let v = math.arithmetic(10, -2, 4)")
        assert i.globals.get("v") == [10.0, 8.0, 6.0, 4.0]

    def test_geometric_four_terms(self):
        i = run("let v = math.geometric(1, 2, 4)")
        assert i.globals.get("v") == [1.0, 2.0, 4.0, 8.0]

    def test_geometric_half(self):
        i = run("let v = math.geometric(8, 0.5, 4)")
        assert i.globals.get("v") == [8.0, 4.0, 2.0, 1.0]

    def test_sum_ap(self):
        # 1 + 3 + 5 + 7 + 9 = 25
        i = run("let v = math.sumAP(5, 1, 2)")
        assert i.globals.get("v") == 25.0

    def test_sum_gp(self):
        # 1 + 2 + 4 + 8 = 15
        i = run("let v = math.sumGP(4, 1, 2)")
        assert i.globals.get("v") == 15.0

    def test_sum_inf_gp(self):
        # 1 / (1 - 0.5) = 2
        i = run("let v = math.sumInfGP(1, 0.5)")
        assert i.globals.get("v") == 2.0


# ─────────────────────────────────────────────────────────────────────────────
# Geometry
# ─────────────────────────────────────────────────────────────────────────────


class TestGeometry:
    def test_circle_area(self):
        i = run("let v = math.circleArea(1)")
        assert approx(i.globals.get("v"), _math.pi)

    def test_circle_area_two(self):
        i = run("let v = math.circleArea(2)")
        assert approx(i.globals.get("v"), 4 * _math.pi)

    def test_circumference(self):
        i = run("let v = math.circumference(1)")
        assert approx(i.globals.get("v"), 2 * _math.pi)

    def test_triangle_area(self):
        i = run("let v = math.triangleArea(6, 4)")
        assert i.globals.get("v") == 12.0

    def test_heron_area(self):
        # 3-4-5 right triangle: area = 6
        i = run("let v = math.heronArea(3, 4, 5)")
        assert approx(i.globals.get("v"), 6.0)

    def test_distance_3_4(self):
        i = run("let v = math.distance(0, 0, 3, 4)")
        assert i.globals.get("v") == 5.0

    def test_distance_same_point(self):
        i = run("let v = math.distance(1, 2, 1, 2)")
        assert i.globals.get("v") == 0.0

    def test_slope(self):
        i = run("let v = math.slope(0, 0, 2, 4)")
        assert i.globals.get("v") == 2.0

    def test_slope_negative(self):
        i = run("let v = math.slope(0, 4, 2, 0)")
        assert i.globals.get("v") == -2.0

    def test_midpoint(self):
        i = run("let v = math.midpoint(0, 0, 4, 6)")
        assert i.globals.get("v") == [2.0, 3.0]


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end math programs
# ─────────────────────────────────────────────────────────────────────────────


class TestMathPrograms:
    def test_quadratic_formula_program(self):
        """Solve x² - 5x + 6 = 0 using the discriminant."""
        i = run("""
let a = 1
let b = -5
let c = 6
let disc = b*b - 4*a*c
let x1 = (-b + math.sqrt(disc)) / (2*a)
let x2 = (-b - math.sqrt(disc)) / (2*a)
let v = x1 + x2
""")
        assert approx(i.globals.get("v"), 5.0)

    def test_compound_interest(self):
        """A = P * (1 + r/n)^(n*t)"""
        i = run("""
let P = 1000
let r = 0.05
let n = 12
let t = 1
let A = P * math.pow(1 + r / n, n * t)
let v = math.roundTo(A, 2)
""")
        assert i.globals.get("v") == 1051.16

    def test_logarithm_equation(self):
        """Solve 2^x = 32 → x = log2(32) = 5."""
        i = run("""
let v = math.log2(32)
""")
        assert i.globals.get("v") == 5.0

    def test_pythagorean_triple(self):
        """Verify 3² + 4² = 5²."""
        i = run("""
let a = 3
let b = 4
let c = math.sqrt(a*a + b*b)
let v = c
""")
        assert i.globals.get("v") == 5.0

    def test_sum_of_squares(self):
        """Sum of squares 1..10 = 385."""
        i = run("""
var s = 0
for i in range(1, 11) {
    s += i * i
}
let v = s
""")
        assert i.globals.get("v") == 385

    def test_arithmetic_series_sum(self):
        """Sum 1+2+…+100 = 5050 via formula and via loop."""
        i = run("""
let formula = math.sumAP(100, 1, 1)
var loop_sum = 0
for i in range(1, 101) {
    loop_sum += i
}
let v = formula == loop_sum
""")
        assert i.globals.get("v") is True

    def test_fibonacci_closed_form(self):
        """fib(10) == 55 via math.fibonacci."""
        i = run("let v = math.fibonacci(10)")
        assert i.globals.get("v") == 55

    def test_prime_count_under_50(self):
        """There are 15 primes below 50."""
        i = run("let v = math.primes(50).length")
        assert i.globals.get("v") == 15

    def test_normalize_then_stats(self):
        """Normalized list has mean ≈ 0.5."""
        i = run("""
let data = [10, 20, 30, 40, 50]
let norm = math.normalize(data)
let v = math.mean(norm)
""")
        assert approx(i.globals.get("v"), 0.5)
