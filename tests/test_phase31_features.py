"""Phase 31 tests: catch (e) parens, for(...) parens, Number.MIN_VALUE,
toExponential JS-style, typeof Proxy → Object, for comma-update i++,j--."""
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


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 1: catch (e) – optional parentheses around catch binding
# ---------------------------------------------------------------------------
class TestCatchParens:
    def test_catch_paren_message(self):
        i = run('var v = ""\ntry { throw Error.new("boom") } catch (e) { v = e.message }')
        assert val(i, "v") == "boom"

    def test_catch_paren_typename(self):
        i = run('var v = ""\ntry { throw TypeError.new("bad") } catch (e) { v = e.name }')
        assert val(i, "v") == "TypeError"

    def test_catch_paren_rangeerror(self):
        i = run('var v = ""\ntry { throw RangeError.new("rng") } catch (e) { v = e.message }')
        assert val(i, "v") == "rng"

    def test_catch_no_paren_still_works(self):
        i = run('var v = ""\ntry { throw Error.new("ok") } catch e { v = e.message }')
        assert val(i, "v") == "ok"

    def test_catch_paren_reraise(self):
        with pytest.raises(Exception):
            run('try { throw Error.new("x") } catch (e) { throw e }')

    def test_catch_paren_number(self):
        i = run('var v = 0\ntry { var x = 1\nthrow x } catch (e) { v = e }')
        assert val(i, "v") == 1

    def test_catch_finally_with_paren(self):
        i = run('var v = 0\ntry { throw Error.new("x") } catch (e) { v = 1 } finally { v = v + 10 }')
        assert val(i, "v") == 11


# ---------------------------------------------------------------------------
# Fix 2: for (...) – optional parentheses around for-loop header
# ---------------------------------------------------------------------------
class TestForParens:
    def test_cstyle_paren_simple(self):
        i = run('var v = 0\nfor (var i = 0; i < 5; i++) { v++ }')
        assert val(i, "v") == 5

    def test_cstyle_paren_down(self):
        i = run('var v = 0\nfor (var i = 10; i > 0; i--) { v++ }')
        assert val(i, "v") == 10

    def test_cstyle_paren_multi_init(self):
        i = run('var v = 0\nfor (var i = 0, j = 10; i < j; i++) { v = v + i }')
        assert val(i, "v") == 45  # 0+1+...+9

    def test_cstyle_paren_multi_update(self):
        i = run('var v = 0\nfor (var i = 0, j = 10; i < j; i++, j--) { v++ }')
        assert val(i, "v") == 5

    def test_for_of_paren(self):
        i = run('var v = 0\nfor (let x of [10, 20, 30]) { v = v + x }')
        assert val(i, "v") == 60

    def test_for_in_paren(self):
        i = run('let obj = {a:1, b:2, c:3}\nvar v = 0\nfor (let k in obj) { v++ }')
        assert val(i, "v") == 3

    def test_for_of_paren_array_destruct(self):
        i = run('var v = 0\nfor (let [a, b] of [[1,2],[3,4]]) { v = v + a + b }')
        assert val(i, "v") == 10

    def test_for_no_paren_still_works(self):
        i = run('var v = 0\nfor var i = 0; i < 3; i++ { v++ }')
        assert val(i, "v") == 3


# ---------------------------------------------------------------------------
# Fix 2b: comma-update in C-style for (no parens)
# ---------------------------------------------------------------------------
class TestForCommaUpdate:
    def test_comma_update_no_paren(self):
        i = run('var v = 0\nfor var i = 0, j = 10; i < j; i++, j-- { v++ }')
        assert val(i, "v") == 5

    def test_comma_update_three(self):
        i = run('var v = 0\nfor (var i = 0, j = 10, k = 0; i < j; i++, j--, k++) { v = k }')
        assert val(i, "v") == 4  # k goes 0,1,2,3,4 — last iter k=4

    def test_comma_update_sum(self):
        i = run('var s = 0\nfor (var i = 0, j = 5; i < j; i++, j--) { s = s + i + j }')
        # i=0,j=5 → 5; i=1,j=4 → 5; i=2,j=3 → 5 → total 15
        assert val(i, "s") == 15


# ---------------------------------------------------------------------------
# Fix 3: Number.MIN_VALUE = 5e-324 (smallest positive float64)
# ---------------------------------------------------------------------------
class TestNumberMinValue:
    def test_min_value_positive(self):
        i = run('let v = Number.MIN_VALUE > 0')
        assert val(i, "v") is True

    def test_min_value_exact(self):
        i = run('let v = Number.MIN_VALUE')
        assert val(i, "v") == 5e-324

    def test_min_value_less_than_epsilon(self):
        i = run('let v = Number.MIN_VALUE < Number.EPSILON')
        assert val(i, "v") is True

    def test_max_value_finite(self):
        import math
        i = run('let v = Number.MAX_VALUE')
        assert math.isfinite(val(i, "v"))
        assert val(i, "v") > 0


# ---------------------------------------------------------------------------
# Fix 4: toExponential JS-style (no leading zero in exponent)
# ---------------------------------------------------------------------------
class TestToExponential:
    def test_large_number(self):
        i = run('let v = (12345).toExponential(2)')
        assert val(i, "v") == '1.23e+4'

    def test_small_number(self):
        i = run('let v = (0.00123).toExponential(2)')
        assert val(i, "v") == '1.23e-3'

    def test_one_digit_exp(self):
        i = run('let v = (1).toExponential(0)')
        assert val(i, "v") == '1e+0'

    def test_negative(self):
        i = run('let v = (-9876).toExponential(1)')
        assert val(i, "v") == '-9.9e+3'

    def test_default_digits(self):
        i = run('let v = (1234567).toExponential()')
        # Should produce e+6, not e+06
        assert 'e+' in val(i, "v") or 'e-' in val(i, "v")
        exp_part = val(i, "v").split('e')[1]
        # No leading zero in exponent
        assert not exp_part.lstrip('+-').startswith('0') or len(exp_part.lstrip('+-')) == 1


# ---------------------------------------------------------------------------
# Fix 5: typeof Proxy → 'Object'
# ---------------------------------------------------------------------------
class TestProxyTypeof:
    def test_typeof_proxy_is_object(self):
        i = run('let p = Proxy.new({x: 1}, {})\nlet v = typeof p')
        assert val(i, "v") == 'Object'

    def test_proxy_member_access(self):
        i = run('let p = Proxy.new({x: 42}, {})\nlet v = p.x')
        assert val(i, "v") == 42

    def test_proxy_index_access(self):
        i = run('let p = Proxy.new({y: 99}, {})\nlet v = p["y"]')
        assert val(i, "v") == 99
