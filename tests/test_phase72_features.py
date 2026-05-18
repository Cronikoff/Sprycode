"""Tests for Phase 72: Regular Expressions
- Regex literal /pattern/flags
- str.match, str.test, /regex/.test(str), /regex/.exec(str)
- str.replace, str.split, str.search, str.matchAll
- Regex flags: g, i, m, s
- Groups: capturing, named, non-capturing
- Lookahead/lookbehind
- new RegExp(pattern, flags)
- .lastIndex, .source, .flags properties
"""
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


# ---------------------------------------------------------------------------
# Regex literals
# ---------------------------------------------------------------------------

class TestRegexLiteral:
    def test_regex_literal_type(self):
        i = run("let v = /hello/")
        assert type(val(i)).__name__ == "SpryRegex"

    def test_regex_source(self):
        i = run("let v = /hello/.source")
        assert val(i) == "hello"

    def test_regex_source_complex(self):
        i = run(r"let v = /\d+/.source")
        assert val(i) == r"\d+"

    def test_regex_flags_empty(self):
        i = run("let v = /hello/.flags")
        assert val(i) == ""

    def test_regex_flags_i(self):
        i = run("let v = /hello/i.flags")
        assert val(i) == "i"

    def test_regex_flags_g(self):
        i = run("let v = /hello/g.flags")
        assert val(i) == "g"

    def test_regex_flags_multiple(self):
        i = run("let v = /hello/gi.flags")
        assert "g" in val(i)
        assert "i" in val(i)

    def test_regex_lastIndex_default(self):
        i = run("let v = /abc/g.lastIndex")
        assert val(i) == 0

    def test_regex_stored_in_variable(self):
        i = run("let r = /test/\nlet v = r.source")
        assert val(i) == "test"


# ---------------------------------------------------------------------------
# .test() method
# ---------------------------------------------------------------------------

class TestRegexTest:
    def test_test_match(self):
        i = run('let v = /hello/.test("hello world")')
        assert val(i) is True

    def test_test_no_match(self):
        i = run('let v = /xyz/.test("hello world")')
        assert val(i) is False

    def test_test_case_insensitive(self):
        i = run('let v = /hello/i.test("HELLO")')
        assert val(i) is True

    def test_test_case_sensitive(self):
        i = run('let v = /hello/.test("HELLO")')
        assert val(i) is False

    def test_test_digits(self):
        i = run(r'let v = /\d+/.test("abc123")')
        assert val(i) is True

    def test_test_digits_no_match(self):
        i = run(r'let v = /\d+/.test("abcdef")')
        assert val(i) is False

    def test_test_anchored_start(self):
        i = run('let v = /^hello/.test("hello world")')
        assert val(i) is True

    def test_test_anchored_start_fail(self):
        i = run('let v = /^world/.test("hello world")')
        assert val(i) is False

    def test_test_anchored_end(self):
        i = run('let v = /world$/.test("hello world")')
        assert val(i) is True

    def test_test_multiline(self):
        i = run('let v = /^hello/m.test("world\\nhello")')
        assert val(i) is True

    def test_test_dotall(self):
        i = run('let v = /hello.world/s.test("hello\\nworld")')
        assert val(i) is True

    def test_test_variable(self):
        i = run('let r = /test/i\nlet v = r.test("TEST")')
        assert val(i) is True


# ---------------------------------------------------------------------------
# str.match()
# ---------------------------------------------------------------------------

class TestStrMatch:
    def test_match_returns_object(self):
        i = run('let v = "hello".match(/hello/)')
        assert val(i) is not None

    def test_match_first_capture(self):
        i = run('let m = "hello world".match(/hello/)\nlet v = m[0]')
        assert val(i) == "hello"

    def test_match_index(self):
        i = run('let m = "hello world".match(/world/)\nlet v = m.index')
        assert val(i) == 6

    def test_match_global_array(self):
        i = run('let m = "aabbcc".match(/[abc]/g)\nlet v = m[0]')
        assert val(i) == "a"

    def test_match_global_all(self):
        i = run('let v = "a1b2c3".match(/[a-z]/g)')
        result = val(i)
        assert result[0] == "a"

    def test_match_no_match_null(self):
        i = run('let v = "hello".match(/xyz/)')
        assert val(i) is None

    def test_match_case_insensitive(self):
        i = run('let m = "HELLO".match(/hello/i)\nlet v = m[0]')
        assert val(i) == "HELLO"

    def test_match_group(self):
        i = run('let m = "2024-01".match(/(\\d{4})-(\\d{2})/)\nlet v = m !== null')
        assert val(i) is True

    def test_match_digits(self):
        i = run('let m = "price: 42".match(/price/)\nlet v = m[0]')
        assert val(i) == "price"


# ---------------------------------------------------------------------------
# /regex/.exec()
# ---------------------------------------------------------------------------

class TestRegexExec:
    def test_exec_returns_object(self):
        i = run('let v = /hello/.exec("hello world")')
        assert val(i) is not None

    def test_exec_first_match(self):
        i = run('let m = /hello/.exec("hello world")\nlet v = m[0]')
        assert val(i) == "hello"

    def test_exec_index(self):
        i = run('let m = /world/.exec("hello world")\nlet v = m.index')
        assert val(i) == 6

    def test_exec_no_match_null(self):
        i = run('let v = /xyz/.exec("hello")')
        assert val(i) is None

    def test_exec_capturing_group(self):
        i = run('let m = /price/.exec("price 42")\nlet v = m[0]')
        assert val(i) == "price"

    def test_exec_named_group(self):
        i = run('let m = /(?<year>\\d{4})/.exec("2024-01-01")\nlet v = m.groups.year')
        assert val(i) == "2024"

    def test_exec_named_group_month(self):
        i = run('let m = /(?<y>\\d{4})-(?<m>\\d{2})/.exec("2024-03")\nlet v = m.groups.m')
        assert val(i) == "03"

    def test_exec_full_match(self):
        i = run('let m = /abc/.exec("xabcdef")\nlet v = m[0]')
        assert val(i) == "abc"

    def test_exec_stored_regex(self):
        i = run('let r = /\\w+/\nlet m = r.exec("hello")\nlet v = m[0]')
        assert val(i) == "hello"

    def test_exec_new_regexp(self):
        i = run('let r = new RegExp("hello")\nlet m = r.exec("say hello")\nlet v = m[0]')
        assert val(i) == "hello"


# ---------------------------------------------------------------------------
# str.replace()
# ---------------------------------------------------------------------------

class TestStrReplace:
    def test_replace_simple(self):
        i = run('let v = "hello world".replace(/world/, "there")')
        assert val(i) == "hello there"

    def test_replace_first_only_without_g(self):
        i = run('let v = "aaa".replace(/a/, "b")')
        assert val(i) == "baa"

    def test_replace_global(self):
        i = run('let v = "aaa".replace(/a/g, "b")')
        assert val(i) == "bbb"

    def test_replace_case_insensitive(self):
        i = run('let v = "HELLO".replace(/hello/i, "world")')
        assert val(i) == "world"

    def test_replace_with_fn_side_effect(self):
        i = run("""
let results = []
"hello".replace(/l/g, fn(m) { results.push(m) })
let v = results
""")
        assert val(i) == ["l", "l"]

    def test_replace_digits(self):
        i = run(r'let v = "price: 42".replace(/\d+/, "99")')
        assert val(i) == "price: 99"

    def test_replace_anchored(self):
        i = run('let v = "hello world".replace(/^hello/, "hi")')
        assert val(i) == "hi world"


# ---------------------------------------------------------------------------
# str.split()
# ---------------------------------------------------------------------------

class TestStrSplitRegex:
    def test_split_simple(self):
        i = run('let v = "a,b,c".split(/,/)')
        assert val(i) == ["a", "b", "c"]

    def test_split_whitespace(self):
        i = run(r'let v = "one  two   three".split(/\s+/)')
        assert val(i) == ["one", "two", "three"]

    def test_split_no_match(self):
        i = run('let v = "hello".split(/,/)')
        assert val(i) == ["hello"]

    def test_split_multiple_delimiters(self):
        i = run('let v = "a:b;c".split(/[:;]/)')
        assert val(i) == ["a", "b", "c"]

    def test_split_digits(self):
        i = run(r'let v = "a1b2c3".split(/\d/)')
        assert val(i) == ["a", "b", "c", ""]


# ---------------------------------------------------------------------------
# str.search()
# ---------------------------------------------------------------------------

class TestStrSearch:
    def test_search_found(self):
        i = run('let v = "hello world".search(/world/)')
        assert val(i) == 6

    def test_search_not_found(self):
        i = run('let v = "hello".search(/xyz/)')
        assert val(i) == -1

    def test_search_start(self):
        i = run('let v = "hello".search(/hello/)')
        assert val(i) == 0

    def test_search_case_insensitive(self):
        i = run('let v = "HELLO".search(/hello/i)')
        assert val(i) == 0

    def test_search_digits(self):
        i = run(r'let v = "abc123".search(/\d/)')
        assert val(i) == 3


# ---------------------------------------------------------------------------
# str.matchAll()
# ---------------------------------------------------------------------------

class TestStrMatchAll:
    def test_matchAll_returns_list(self):
        i = run(r'let v = "test1 test2".matchAll(/test(\d)/g)')
        assert isinstance(val(i), list)

    def test_matchAll_count(self):
        i = run(r'let v = "test1 test2".matchAll(/test(\d)/g)')
        assert len(val(i)) == 2

    def test_matchAll_first_match(self):
        i = run(r'let v = "test1 test2".matchAll(/test(\d)/g)')
        assert val(i)[0][0] == "test1"

    def test_matchAll_second_match(self):
        i = run(r'let v = "test1 test2".matchAll(/test(\d)/g)')
        assert val(i)[1][0] == "test2"

    def test_matchAll_words(self):
        i = run(r'let v = "hello world".matchAll(/\w+/g)')
        assert len(val(i)) == 2


# ---------------------------------------------------------------------------
# Regex flags
# ---------------------------------------------------------------------------

class TestRegexFlags:
    def test_flag_i_case_insensitive(self):
        i = run('let v = /hello/i.test("HELLO WORLD")')
        assert val(i) is True

    def test_flag_g_global(self):
        i = run('let v = "aaa".match(/a/g)')
        result = val(i)
        assert len(result) == 3

    def test_flag_m_multiline(self):
        i = run('let v = /^line/m.test("first\\nline two")')
        assert val(i) is True

    def test_flag_s_dotall(self):
        i = run('let v = /a.b/s.test("a\\nb")')
        assert val(i) is True

    def test_flag_gi_combined(self):
        i = run('let v = "Hello HELLO".match(/hello/gi)')
        result = val(i)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Regex groups
# ---------------------------------------------------------------------------

class TestRegexGroups:
    def test_capturing_group(self):
        i = run('let m = /price/.exec("price 42")\nlet v = m[0]')
        assert val(i) == "price"

    def test_named_group(self):
        i = run('let m = /(?<year>\\d{4})/.exec("2024")\nlet v = m.groups.year')
        assert val(i) == "2024"

    def test_non_capturing_group(self):
        i = run('let v = /(?:hello) world/.test("hello world")')
        assert val(i) is True

    def test_named_group_multiple(self):
        i = run('let m = /(?<d>\\d+)-(?<w>\\w+)/.exec("42-hello")\nlet v = m.groups.d')
        assert val(i) == "42"

    def test_lookahead_positive(self):
        i = run('let v = /hello(?= world)/.test("hello world")')
        assert val(i) is True

    def test_lookahead_negative(self):
        i = run('let v = /hello(?! there)/.test("hello world")')
        assert val(i) is True

    def test_lookbehind_positive(self):
        i = run('let v = /(?<=hello )world/.test("hello world")')
        assert val(i) is True

    def test_non_capturing_no_extra_group(self):
        i = run('let v = /(?:ab)+/.test("ababab")')
        assert val(i) is True


# ---------------------------------------------------------------------------
# new RegExp constructor
# ---------------------------------------------------------------------------

class TestNewRegExp:
    def test_new_regexp_basic(self):
        i = run('let v = new RegExp("hello")')
        assert type(val(i)).__name__ == "SpryRegex"

    def test_new_regexp_test(self):
        i = run('let r = new RegExp("hello")\nlet v = r.test("say hello")')
        assert val(i) is True

    def test_new_regexp_flags(self):
        i = run('let r = new RegExp("hello", "i")\nlet v = r.test("HELLO")')
        assert val(i) is True

    def test_new_regexp_source(self):
        i = run('let r = new RegExp("world")\nlet v = r.source')
        assert val(i) == "world"

    def test_new_regexp_exec(self):
        i = run('let r = new RegExp("\\\\d+")\nlet m = r.exec("abc123")\nlet v = m[0]')
        assert val(i) == "123"

    def test_new_regexp_global_flag(self):
        i = run('let r = new RegExp("a", "g")\nlet v = "aaa".match(r)')
        result = val(i)
        assert len(result) == 3
