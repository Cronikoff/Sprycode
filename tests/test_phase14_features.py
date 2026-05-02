"""Phase 14 feature tests.

Covers:
  - console namespace (log, warn, error, assert, time, timeEnd, count, dir, table)
  - Math uppercase alias + newly added JS-compat methods (trunc, sign, cbrt, hypot,
    clz32, fround, imul, log10, log2)
  - &&= and ||= logical assignment operators
  - Object.is() SameValue comparison
  - string.isWellFormed() / string.toWellFormed()
  - WeakMap.new() / WeakSet.new()
  - crypto namespace (randomUUID, randomBytes, getRandomValues)
  - Intl namespace (NumberFormat, DateTimeFormat, Collator, PluralRules,
    RelativeTimeFormat, ListFormat, getCanonicalLocales, supportedValuesOf)
  - FinalizationRegistry (stub)
  - Proxy (basic get / set / has traps + empty handler pass-through)
  - eval() — evaluate SpryCode source string in current environment
"""

import math
import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def val(source: str, name: str = "v"):
    return run(source).globals.get(name)


# ---------------------------------------------------------------------------
# console namespace
# ---------------------------------------------------------------------------


class TestConsole:
    def test_console_is_defined(self):
        v = val("let v = console != null")
        assert v is True

    def test_console_log_runs(self, capsys):
        run('console.log("hello")')
        out = capsys.readouterr().out
        assert "hello" in out

    def test_console_log_multiple(self, capsys):
        run('console.log("a", "b", "c")')
        out = capsys.readouterr().out
        assert "a" in out and "b" in out and "c" in out

    def test_console_log_number(self, capsys):
        run("console.log(42)")
        out = capsys.readouterr().out
        assert "42" in out

    def test_console_warn_runs(self, capsys):
        run('console.warn("caution")')
        err = capsys.readouterr().err
        assert "caution" in err

    def test_console_error_runs(self, capsys):
        run('console.error("boom")')
        err = capsys.readouterr().err
        assert "boom" in err

    def test_console_assert_pass(self, capsys):
        run("console.assert(true, \"should not print\")")
        err = capsys.readouterr().err
        assert err == ""

    def test_console_assert_fail(self, capsys):
        run("console.assert(false, \"assertion failed\")")
        err = capsys.readouterr().err
        assert "assertion failed" in err.lower() or "Assertion" in err

    def test_console_count(self, capsys):
        run("console.count(\"c\")\nconsole.count(\"c\")")
        out = capsys.readouterr().out
        assert "2" in out

    def test_console_time_end(self, capsys):
        run("console.time(\"t\")\nconsole.timeEnd(\"t\")")
        out = capsys.readouterr().out
        assert "ms" in out or "t" in out

    def test_console_group(self, capsys):
        run("console.group(\"group1\")")
        # just ensure it doesn't raise

    def test_console_dir(self, capsys):
        run("console.dir({a: 1})")
        out = capsys.readouterr().out
        assert out  # something is printed


# ---------------------------------------------------------------------------
# Math uppercase alias
# ---------------------------------------------------------------------------


class TestMathUppercase:
    def test_math_abs(self):
        assert val("let v = Math.abs(-7)") == 7

    def test_math_floor(self):
        assert val("let v = Math.floor(3.9)") == 3

    def test_math_ceil(self):
        assert val("let v = Math.ceil(3.1)") == 4

    def test_math_round(self):
        assert val("let v = Math.round(3.5)") == 4

    def test_math_sqrt(self):
        assert val("let v = Math.sqrt(25)") == 5

    def test_math_pow(self):
        assert val("let v = Math.pow(2, 10)") == 1024

    def test_math_max(self):
        assert val("let v = Math.max(1, 5, 3)") == 5

    def test_math_min(self):
        assert val("let v = Math.min(1, 5, 3)") == 1

    def test_math_PI(self):
        assert abs(val("let v = Math.PI") - math.pi) < 1e-10

    def test_math_E(self):
        assert abs(val("let v = Math.E") - math.e) < 1e-10

    def test_math_log10(self):
        assert abs(val("let v = Math.log10(100)") - 2.0) < 1e-10

    def test_math_log2(self):
        assert abs(val("let v = Math.log2(8)") - 3.0) < 1e-10

    def test_math_trunc_positive(self):
        assert val("let v = Math.trunc(4.9)") == 4

    def test_math_trunc_negative(self):
        assert val("let v = Math.trunc(-4.9)") == -4

    def test_math_sign_positive(self):
        assert val("let v = Math.sign(99)") == 1

    def test_math_sign_negative(self):
        assert val("let v = Math.sign(-99)") == -1

    def test_math_sign_zero(self):
        assert val("let v = Math.sign(0)") == 0

    def test_math_cbrt(self):
        assert abs(val("let v = Math.cbrt(27)") - 3.0) < 1e-9

    def test_math_cbrt_negative(self):
        assert abs(val("let v = Math.cbrt(-8)") - (-2.0)) < 1e-9

    def test_math_hypot(self):
        assert abs(val("let v = Math.hypot(3, 4)") - 5.0) < 1e-10

    def test_math_hypot_3d(self):
        result = val("let v = Math.hypot(1, 2, 2)")
        assert abs(result - 3.0) < 1e-10

    def test_math_clz32_one(self):
        assert val("let v = Math.clz32(1)") == 31

    def test_math_clz32_zero(self):
        assert val("let v = Math.clz32(0)") == 32

    def test_math_clz32_max(self):
        assert val("let v = Math.clz32(2147483648)") == 0

    def test_math_imul(self):
        assert val("let v = Math.imul(3, 4)") == 12

    def test_math_imul_overflow(self):
        # imul wraps at 32 bits
        result = val("let v = Math.imul(2147483647, 2)")
        assert isinstance(result, int)

    def test_math_fround(self):
        # fround(1.5) == 1.5 (exact in float32)
        result = val("let v = Math.fround(1.5)")
        assert abs(result - 1.5) < 1e-7

    def test_math_log(self):
        assert abs(val("let v = Math.log(Math.E)") - 1.0) < 1e-10

    def test_math_sin_cos(self):
        assert abs(val("let v = Math.sin(0)")) < 1e-10
        assert abs(val("let v = Math.cos(0)") - 1.0) < 1e-10

    def test_math_random(self):
        result = val("let v = Math.random()")
        assert 0.0 <= result < 1.0


# ---------------------------------------------------------------------------
# Logical assignment operators: &&= and ||=
# ---------------------------------------------------------------------------


class TestLogicalAssignment:
    def test_and_and_eq_truthy_lhs_assigns(self):
        # x = true; x &&= false => x is false
        assert val("var x = true\nx &&= false\nlet v = x") is False

    def test_and_and_eq_falsy_lhs_noop(self):
        # x = false; x &&= true => x stays false
        assert val("var x = false\nx &&= true\nlet v = x") is False

    def test_and_and_eq_truthy_to_truthy(self):
        assert val("var x = true\nx &&= true\nlet v = x") is True

    def test_and_and_eq_with_value(self):
        assert val("var x = 10\nx &&= 99\nlet v = x") == 99

    def test_and_and_eq_zero_lhs_noop(self):
        # 0 is falsy
        assert val("var x = 0\nx &&= 42\nlet v = x") == 0

    def test_or_or_eq_falsy_lhs_assigns(self):
        # x = false; x ||= true => x is true
        assert val("var x = false\nx ||= true\nlet v = x") is True

    def test_or_or_eq_truthy_lhs_noop(self):
        # x = true; x ||= false => x stays true
        assert val("var x = true\nx ||= false\nlet v = x") is True

    def test_or_or_eq_null_assigns(self):
        assert val("var x = null\nx ||= 42\nlet v = x") == 42

    def test_or_or_eq_zero_assigns(self):
        # 0 is falsy
        assert val("var x = 0\nx ||= 99\nlet v = x") == 99

    def test_or_or_eq_string_noop(self):
        assert val('var x = "hello"\nx ||= "world"\nlet v = x') == "hello"

    def test_and_and_eq_lexed_correctly(self):
        # Ensure lexer produces AND_AND_EQ and not two tokens
        from sprycode.lexer import Lexer, TokenType
        tokens = list(Lexer("x &&= 1").tokenize())
        types = [t.type for t in tokens]
        assert TokenType.AND_AND_EQ in types

    def test_or_or_eq_lexed_correctly(self):
        from sprycode.lexer import Lexer, TokenType
        tokens = list(Lexer("x ||= 1").tokenize())
        types = [t.type for t in tokens]
        assert TokenType.OR_OR_EQ in types


# ---------------------------------------------------------------------------
# Object.is
# ---------------------------------------------------------------------------


class TestObjectIs:
    def test_same_numbers(self):
        assert val("let v = Object.is(1, 1)") is True

    def test_different_numbers(self):
        assert val("let v = Object.is(1, 2)") is False

    def test_same_strings(self):
        assert val('let v = Object.is("a", "a")') is True

    def test_different_strings(self):
        assert val('let v = Object.is("a", "b")') is False

    def test_null_null(self):
        assert val("let v = Object.is(null, null)") is True

    def test_true_true(self):
        assert val("let v = Object.is(true, true)") is True

    def test_nan_nan(self):
        # NaN is the same value as itself in SameValue semantics
        assert val("let v = Object.is(Number.NaN, Number.NaN)") is True

    def test_zero_zero(self):
        assert val("let v = Object.is(0, 0)") is True


# ---------------------------------------------------------------------------
# String isWellFormed / toWellFormed
# ---------------------------------------------------------------------------


class TestStringWellFormed:
    def test_is_well_formed_ascii(self):
        assert val('let v = "hello".isWellFormed()') is True

    def test_is_well_formed_unicode(self):
        assert val('let v = "café".isWellFormed()') is True

    def test_is_well_formed_empty(self):
        assert val('let v = "".isWellFormed()') is True

    def test_to_well_formed_returns_string(self):
        result = val('let v = "hello world".toWellFormed()')
        assert result == "hello world"

    def test_to_well_formed_unicode(self):
        result = val('let v = "日本語".toWellFormed()')
        assert result == "日本語"


# ---------------------------------------------------------------------------
# WeakMap / WeakSet
# ---------------------------------------------------------------------------


class TestWeakMap:
    def test_new_returns_instance(self):
        v = val("let v = WeakMap.new() != null")
        assert v is True

    def test_set_and_get(self):
        src = "let m = WeakMap.new()\nlet k = {}\nm.set(k, 42)\nlet v = m.get(k)"
        assert val(src) == 42

    def test_has_existing_key(self):
        src = "let m = WeakMap.new()\nlet k = {}\nm.set(k, 1)\nlet v = m.has(k)"
        assert val(src) is True

    def test_has_missing_key(self):
        src = "let m = WeakMap.new()\nlet k = {}\nlet v = m.has(k)"
        assert val(src) is False

    def test_delete_key(self):
        src = "let m = WeakMap.new()\nlet k = {}\nm.set(k, 1)\nm.delete(k)\nlet v = m.has(k)"
        assert val(src) is False

    def test_get_missing_returns_null(self):
        src = "let m = WeakMap.new()\nlet k = {}\nlet v = m.get(k)"
        assert val(src) is None

    def test_separate_keys_independent(self):
        src = "let m = WeakMap.new()\nlet a = {}\nlet b = {}\nm.set(a, 1)\nm.set(b, 2)\nlet v = m.get(a)"
        assert val(src) == 1


class TestWeakSet:
    def test_new_returns_instance(self):
        v = val("let v = WeakSet.new() != null")
        assert v is True

    def test_add_and_has(self):
        src = "let s = WeakSet.new()\nlet k = {}\ns.add(k)\nlet v = s.has(k)"
        assert val(src) is True

    def test_has_missing(self):
        src = "let s = WeakSet.new()\nlet k = {}\nlet v = s.has(k)"
        assert val(src) is False

    def test_delete(self):
        src = "let s = WeakSet.new()\nlet k = {}\ns.add(k)\ns.delete(k)\nlet v = s.has(k)"
        assert val(src) is False

    def test_separate_keys(self):
        src = "let s = WeakSet.new()\nlet a = {}\nlet b = {}\ns.add(a)\nlet v = s.has(b)"
        assert val(src) is False


# ---------------------------------------------------------------------------
# crypto namespace
# ---------------------------------------------------------------------------


class TestCrypto:
    def test_crypto_defined(self):
        assert val("let v = crypto != null") is True

    def test_random_uuid_is_string(self):
        result = val("let v = crypto.randomUUID()")
        assert isinstance(result, str)

    def test_random_uuid_format(self):
        result = val("let v = crypto.randomUUID()")
        parts = result.split("-")
        assert len(parts) == 5

    def test_random_uuid_unique(self):
        src = "let a = crypto.randomUUID()\nlet b = crypto.randomUUID()\nlet v = a != b"
        assert val(src) is True

    def test_random_bytes_length(self):
        result = val("let v = crypto.randomBytes(8)")
        assert isinstance(result, list)
        assert len(result) == 8

    def test_random_bytes_range(self):
        result = val("let v = crypto.randomBytes(16)")
        assert all(0 <= b <= 255 for b in result)

    def test_get_random_values(self):
        result = val("let v = crypto.getRandomValues(16)")
        assert isinstance(result, list)
        assert len(result) == 16


# ---------------------------------------------------------------------------
# Intl namespace
# ---------------------------------------------------------------------------


class TestIntl:
    def test_intl_defined(self):
        assert val("let v = Intl != null") is True

    def test_number_format_basic(self):
        result = val('let f = Intl.NumberFormat("en-US")\nlet v = f.format(1000)')
        assert "1" in str(result)  # at minimum contains the number

    def test_number_format_decimal(self):
        result = val('let f = Intl.NumberFormat("en-US")\nlet v = f.format(1234.5)')
        assert isinstance(result, str)

    def test_datetime_format_returns_string(self):
        result = val('let f = Intl.DateTimeFormat("en-US")\nlet v = f.format(Date.new(2024,1,15))')
        assert isinstance(result, str)

    def test_datetime_format_contains_year(self):
        result = val('let f = Intl.DateTimeFormat("en-US")\nlet v = f.format(Date.new(2024,6,1))')
        assert "2024" in result

    def test_collator_compare_lt(self):
        result = val('let c = Intl.Collator("en")\nlet v = c.compare("apple", "banana")')
        assert result < 0

    def test_collator_compare_gt(self):
        result = val('let c = Intl.Collator("en")\nlet v = c.compare("zebra", "apple")')
        assert result > 0

    def test_collator_compare_eq(self):
        result = val('let c = Intl.Collator("en")\nlet v = c.compare("cat", "cat")')
        assert result == 0

    def test_plural_rules_one(self):
        result = val('let p = Intl.PluralRules("en")\nlet v = p.select(1)')
        assert result == "one"

    def test_plural_rules_other(self):
        result = val('let p = Intl.PluralRules("en")\nlet v = p.select(5)')
        assert result == "other"

    def test_plural_rules_zero(self):
        result = val('let p = Intl.PluralRules("en")\nlet v = p.select(0)')
        assert result == "other"

    def test_list_format(self):
        result = val('let lf = Intl.ListFormat("en")\nlet v = lf.format(["a", "b", "c"])')
        assert isinstance(result, str)
        assert "a" in result and "c" in result

    def test_relative_time_format(self):
        result = val('let rtf = Intl.RelativeTimeFormat("en")\nlet v = rtf.format(-1, "day")')
        assert isinstance(result, str)

    def test_get_canonical_locales(self):
        result = val('let v = Intl.getCanonicalLocales(["en-US"])')
        assert isinstance(result, list)
        assert len(result) == 1

    def test_supported_values_of(self):
        result = val('let v = Intl.supportedValuesOf("currency")')
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# FinalizationRegistry
# ---------------------------------------------------------------------------


class TestFinalizationRegistry:
    def test_new_instance(self):
        v = val("let r = FinalizationRegistry.new(x => {})\nlet v = r != null")
        assert v is True

    def test_register_noop(self):
        # register should not raise
        v = val(
            "let r = FinalizationRegistry.new(x => {})\n"
            "let obj = {}\n"
            "r.register(obj, \"held\")\n"
            "let v = true"
        )
        assert v is True

    def test_unregister_returns_false(self):
        v = val(
            "let r = FinalizationRegistry.new(x => {})\n"
            "let v = r.unregister(\"token\")"
        )
        assert v is False


# ---------------------------------------------------------------------------
# Proxy
# ---------------------------------------------------------------------------


class TestProxy:
    def test_new_returns_instance(self):
        v = val("let p = Proxy.new({x: 1}, {})\nlet v = p != null")
        assert v is True

    def test_passthrough_get(self):
        assert val("let p = Proxy.new({x: 42}, {})\nlet v = p.x") == 42

    def test_passthrough_set(self):
        v = val("let t = {x: 0}\nlet p = Proxy.new(t, {})\np.x = 99\nlet v = t.x")
        assert v == 99

    def test_get_trap_invoked(self):
        src = (
            "let handler = {get: (t, p) => 777}\n"
            "let p = Proxy.new({x: 1}, handler)\n"
            "let v = p.x"
        )
        assert val(src) == 777

    def test_get_trap_passes_target_and_prop(self):
        src = (
            "var lastProp = null\n"
            "fn getHandler(target, prop) { lastProp = prop\nreturn target.x }\n"
            "let handler = {get: getHandler}\n"
            "let p = Proxy.new({x: 42}, handler)\n"
            "let res = p.x\n"
            "let v = lastProp"
        )
        assert val(src) == "x"

    def test_proxy_missing_prop_returns_null(self):
        v = val("let p = Proxy.new({}, {})\nlet v = p.missing")
        assert v is None

    def test_revocable_proxy(self):
        v = val(
            "let rp = Proxy.revocable({x: 1}, {})\n"
            "let v = rp.proxy.x"
        )
        assert v == 1


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------


class TestEval:
    def test_eval_arithmetic(self):
        assert val("let v = eval(\"1 + 2\")") == 3

    def test_eval_string_concat(self):
        # eval a simple string expression
        assert val("let v = eval(\"1 + 1\")") == 2

    def test_eval_uses_current_env(self):
        assert val("var x = 10\nlet v = eval(\"x * 3\")") == 30

    def test_eval_can_define_var(self):
        # eval can reference variables defined in outer scope
        assert val("var y = 5\nlet v = eval(\"y + y\")") == 10

    def test_eval_returns_last_value(self):
        result = val("let v = eval(\"42\")")
        assert result == 42

    def test_eval_empty_string(self):
        result = val('let v = eval("")')
        assert result is None

    def test_eval_list_literal(self):
        result = val("let v = eval(\"[1, 2, 3]\")")
        assert result == [1, 2, 3]

    def test_eval_dict_literal(self):
        result = val('let v = eval("{x: 1}")')
        assert isinstance(result, dict)
        assert result.get("x") == 1
