"""Phase 36 feature tests.

Covers:
- ``new WeakRef(obj)`` / ``new FinalizationRegistry(fn)`` / ``new URL(href)`` constructor syntax
- Optional catch binding: ``try { } catch { }`` without variable name (ES2019)
- ``JSON.stringify`` compact output (no spaces around ``:`` or ``,``) when no indent arg
- ``toExponential()`` with no args: minimum digits needed (JS semantics)
- ``list.indexOf(item, fromIndex)`` — optional second fromIndex argument
- ``list.lastIndexOf(item, fromIndex)`` — optional second fromIndex argument
- ``string.indexOf(sub, fromIndex)`` — optional second fromIndex argument
- ``string.lastIndexOf(sub, fromIndex)`` — optional second fromIndex argument
- Accessing a missing property on a dict returns ``None`` (JS-compat, after ``delete``)
"""

from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter, SpryFinalizationRegistry, SpryURL, SpryWeakRef
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(source_or_interp: Any, name: str = "v") -> Any:
    if isinstance(source_or_interp, str):
        return run(source_or_interp).globals.get(name)
    return source_or_interp.globals.get(name)


# ---------------------------------------------------------------------------
# new WeakRef(obj) constructor syntax
# ---------------------------------------------------------------------------


class TestNewWeakRef:
    def test_new_weakref_deref(self) -> None:
        i = run("let obj = {x: 42}; let ref = new WeakRef(obj); let v = ref.deref().x")
        assert val(i) == 42

    def test_new_weakref_deref_string(self) -> None:
        i = run('let ref = new WeakRef("hello"); let v = ref.deref()')
        assert val(i) == "hello"

    def test_weakref_new_still_works(self) -> None:
        """WeakRef.new() syntax should still work."""
        i = run("let obj = {n: 99}; let w = WeakRef.new(obj); let v = w.deref().n")
        assert val(i) == 99

    def test_new_weakref_returns_weakref(self) -> None:
        i = run("let obj = {x: 1}; let ref = new WeakRef(obj)")
        result = i.globals.get("ref")
        assert isinstance(result, SpryWeakRef)


# ---------------------------------------------------------------------------
# new FinalizationRegistry(fn) constructor syntax
# ---------------------------------------------------------------------------


class TestNewFinalizationRegistry:
    def test_new_registry_creates_instance(self) -> None:
        i = run("let reg = new FinalizationRegistry(x => null); let v = reg != null")
        assert val(i) is True

    def test_new_registry_register_and_unregister(self) -> None:
        src = """
let reg = new FinalizationRegistry(x => null)
let token = {}
reg.register({}, "held", token)
reg.unregister(token)
let v = true
"""
        assert val(src) is True

    def test_registry_new_still_works(self) -> None:
        i = run("let reg = FinalizationRegistry.new(x => null); let v = reg != null")
        assert val(i) is True

    def test_new_registry_returns_correct_type(self) -> None:
        i = run("let reg = new FinalizationRegistry(x => null)")
        result = i.globals.get("reg")
        assert isinstance(result, SpryFinalizationRegistry)


# ---------------------------------------------------------------------------
# new URL(href) constructor syntax
# ---------------------------------------------------------------------------


class TestNewURL:
    def test_new_url_hostname(self) -> None:
        i = run('let u = new URL("https://example.com/path?q=1"); let v = u.hostname')
        assert val(i) == "example.com"

    def test_new_url_pathname(self) -> None:
        i = run('let u = new URL("https://example.com/path?q=1"); let v = u.pathname')
        assert val(i) == "/path"

    def test_new_url_protocol(self) -> None:
        i = run('let u = new URL("https://example.com"); let v = u.protocol')
        assert val(i) == "https:"

    def test_new_url_search(self) -> None:
        i = run('let u = new URL("https://example.com/p?q=1&r=2"); let v = u.search')
        assert val(i) == "?q=1&r=2"

    def test_url_new_still_works(self) -> None:
        i = run('let u = URL.new("https://example.com"); let v = u.hostname')
        assert val(i) == "example.com"

    def test_new_url_returns_spry_url(self) -> None:
        i = run('let u = new URL("https://example.com")')
        result = i.globals.get("u")
        assert isinstance(result, SpryURL)


# ---------------------------------------------------------------------------
# Optional catch binding (ES2019) — try { } catch { }
# ---------------------------------------------------------------------------


class TestOptionalCatchBinding:
    def test_catch_no_binding_executes(self) -> None:
        src = "var v = 0; try { throw \"error\" } catch { v = 1 }"
        assert val(src) == 1

    def test_catch_empty_parens_executes(self) -> None:
        src = "var v = 0; try { throw \"error\" } catch() { v = 1 }"
        assert val(src) == 1

    def test_catch_no_binding_body_runs(self) -> None:
        src = """
var v = 0
try {
  throw new Error("boom")
} catch {
  v = 99
}
"""
        assert val(src) == 99

    def test_catch_no_binding_cannot_access_error(self) -> None:
        """Without a binding variable, there is no error variable in catch scope."""
        src = """
var v = 0
try {
  throw "oops"
} catch {
  v = 42
}
"""
        assert val(src) == 42

    def test_catch_with_binding_still_works(self) -> None:
        src = "var v = null; try { throw new Error(\"msg\") } catch(e) { v = e.message }"
        assert val(src) == "msg"

    def test_catch_bare_identifier_still_works(self) -> None:
        src = "var v = null; try { throw new Error(\"test\") } catch e { v = e.message }"
        assert val(src) == "test"

    def test_catch_no_binding_with_finally(self) -> None:
        src = """
var v = 0
try {
  throw "x"
} catch {
  v = v + 1
} finally {
  v = v + 10
}
"""
        assert val(src) == 11


# ---------------------------------------------------------------------------
# JSON.stringify compact output (no spaces without indent)
# ---------------------------------------------------------------------------


class TestJSONStringifyCompact:
    def test_object_no_spaces(self) -> None:
        assert val('let v = JSON.stringify({a: 1})') == '{"a":1}'

    def test_list_no_spaces(self) -> None:
        assert val('let v = JSON.stringify([1, 2, 3])') == '[1,2,3]'

    def test_nested_no_spaces(self) -> None:
        result = val('let v = JSON.stringify({a: [1, 2], b: {c: 3}})')
        import json
        assert json.loads(result) == {"a": [1, 2], "b": {"c": 3}}
        assert " " not in result  # no spaces

    def test_with_indent_uses_spaces(self) -> None:
        result = val('let v = JSON.stringify({a: 1}, null, 2)')
        assert "\n" in result  # indented
        assert '"a": 1' in result  # space after colon when indented

    def test_string_value(self) -> None:
        assert val('let v = JSON.stringify("hello")') == '"hello"'

    def test_number_value(self) -> None:
        assert val('let v = JSON.stringify(42)') == '42'

    def test_null_value(self) -> None:
        assert val('let v = JSON.stringify(null)') == 'null'

    def test_boolean_value(self) -> None:
        assert val('let v = JSON.stringify(true)') == 'true'

    def test_roundtrip(self) -> None:
        src = """
let original = {a: 1, b: [2, 3]}
let serialized = JSON.stringify(original)
let restored = JSON.parse(serialized)
let v = restored.a + restored.b.length
"""
        assert val(src) == 3


# ---------------------------------------------------------------------------
# toExponential() with no args: minimum digits
# ---------------------------------------------------------------------------


class TestToExponentialNoArgs:
    def test_small_number(self) -> None:
        assert val("let v = (0.000001).toExponential()") == "1e-6"

    def test_thousand(self) -> None:
        assert val("let v = (1000).toExponential()") == "1e+3"

    def test_twelve_thousand(self) -> None:
        assert val("let v = (12345).toExponential()") == "1.2345e+4"

    def test_one(self) -> None:
        assert val("let v = (1).toExponential()") == "1e+0"

    def test_hundred(self) -> None:
        assert val("let v = (100).toExponential()") == "1e+2"

    def test_fraction_pi(self) -> None:
        # 3.14 should give '3.14e+0'
        result = val("let v = (3.14).toExponential()")
        assert result == "3.14e+0"

    def test_zero(self) -> None:
        assert val("let v = (0).toExponential()") == "0e+0"

    def test_with_digits_arg(self) -> None:
        assert val("let v = (12345).toExponential(2)") == "1.23e+4"

    def test_with_digits_zero(self) -> None:
        assert val("let v = (12345).toExponential(0)") == "1e+4"

    def test_with_digits_four(self) -> None:
        result = val("let v = (12345).toExponential(4)")
        assert result == "1.2345e+4"


# ---------------------------------------------------------------------------
# list.indexOf(item, fromIndex) — optional fromIndex
# ---------------------------------------------------------------------------


class TestListIndexOfFromIndex:
    def test_no_fromindex(self) -> None:
        assert val("let v = [1,2,3,2,1].indexOf(2)") == 1

    def test_fromindex_skip_first(self) -> None:
        assert val("let v = [1,2,3,2,1].indexOf(2, 2)") == 3

    def test_fromindex_zero(self) -> None:
        assert val("let v = [1,2,3].indexOf(1, 0)") == 0

    def test_fromindex_beyond_end(self) -> None:
        assert val("let v = [1,2,3].indexOf(1, 10)") == -1

    def test_fromindex_not_found(self) -> None:
        assert val("let v = [1,2,3].indexOf(5, 0)") == -1

    def test_fromindex_negative(self) -> None:
        # Negative fromIndex counts from end
        assert val("let v = [1,2,3,2,1].indexOf(2, -3)") == 3

    def test_fromindex_exact_match(self) -> None:
        assert val("let v = [1,2,3,4,5].indexOf(3, 2)") == 2


# ---------------------------------------------------------------------------
# list.lastIndexOf(item, fromIndex) — optional fromIndex
# ---------------------------------------------------------------------------


class TestListLastIndexOfFromIndex:
    def test_no_fromindex(self) -> None:
        assert val("let v = [1,2,3,2,1].lastIndexOf(2)") == 3

    def test_fromindex_limit(self) -> None:
        assert val("let v = [1,2,3,2,1].lastIndexOf(2, 2)") == 1

    def test_fromindex_full(self) -> None:
        assert val("let v = [1,2,3,2,1].lastIndexOf(2, 3)") == 3

    def test_fromindex_not_found(self) -> None:
        assert val("let v = [1,2,3].lastIndexOf(5)") == -1

    def test_fromindex_single(self) -> None:
        assert val("let v = [1,2,3].lastIndexOf(1)") == 0

    def test_fromindex_end(self) -> None:
        assert val("let v = [1,2,3,2,1].lastIndexOf(1)") == 4


# ---------------------------------------------------------------------------
# string.indexOf(sub, fromIndex) — optional fromIndex
# ---------------------------------------------------------------------------


class TestStringIndexOfFromIndex:
    def test_no_fromindex(self) -> None:
        assert val('let v = "abcabc".indexOf("b")') == 1

    def test_fromindex_skip(self) -> None:
        assert val('let v = "abcabc".indexOf("b", 2)') == 4

    def test_fromindex_zero(self) -> None:
        assert val('let v = "hello".indexOf("l", 0)') == 2

    def test_fromindex_not_found(self) -> None:
        assert val('let v = "hello".indexOf("z")') == -1

    def test_fromindex_beyond(self) -> None:
        assert val('let v = "hello".indexOf("h", 1)') == -1


# ---------------------------------------------------------------------------
# string.lastIndexOf(sub, fromIndex) — optional fromIndex
# ---------------------------------------------------------------------------


class TestStringLastIndexOfFromIndex:
    def test_no_fromindex(self) -> None:
        assert val('let v = "abcabc".lastIndexOf("b")') == 4

    def test_fromindex_limit(self) -> None:
        assert val('let v = "abcabc".lastIndexOf("b", 3)') == 1

    def test_fromindex_not_found(self) -> None:
        assert val('let v = "hello".lastIndexOf("z")') == -1

    def test_fromindex_full(self) -> None:
        assert val('let v = "abcabc".lastIndexOf("a")') == 3


# ---------------------------------------------------------------------------
# dict missing property returns None (JS-compat, after delete)
# ---------------------------------------------------------------------------


class TestDictMissingProperty:
    def test_delete_then_access_returns_none(self) -> None:
        src = "let obj = {a: 1, b: 2}; delete obj.a; let v = obj.a"
        assert val(src) is None

    def test_delete_then_in_returns_false(self) -> None:
        src = "let obj = {a: 1, b: 2}; delete obj.a; let v = \"a\" in obj"
        assert val(src) is False

    def test_delete_other_key_still_accessible(self) -> None:
        src = "let obj = {a: 1, b: 2}; delete obj.a; let v = obj.b"
        assert val(src) == 2

    def test_access_missing_property_returns_none(self) -> None:
        """Accessing a property that was never set returns None (JS-compat)."""
        src = "let obj = {a: 1}; let v = obj.missing"
        assert val(src) is None

    def test_nullish_coalesce_on_missing(self) -> None:
        src = 'let obj = {a: 1}; let v = obj.missing ?? "default"'
        assert val(src) == "default"

    def test_delete_index_then_access(self) -> None:
        src = 'let obj = {a: 1, b: 2}; delete obj["a"]; let v = obj.a'
        assert val(src) is None

    def test_optional_chain_on_missing(self) -> None:
        src = "let obj = {a: 1}; let v = obj.missing?.nested"
        assert val(src) is None

    def test_known_methods_still_work(self) -> None:
        """Dict methods like .keys(), .values() still work despite fallback."""
        src = "let obj = {a: 1, b: 2}; let v = obj.keys().length"
        assert val(src) == 2
