"""Tests for Phase 94: String Advanced Methods
- normalize, codePointAt, String.fromCodePoint, charCodeAt, String.fromCharCode
- substring, substr, match, matchAll, search, replace with fn, replaceAll
- split by regex, trimStart/trimEnd, padStart/padEnd, repeat
- startsWith/endsWith/includes with position argument
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


# ── normalize ─────────────────────────────────────────────────────────────────

class TestNormalize:
    def test_normalize_default(self):
        i = run('let v = "hello".normalize()')
        assert val(i) == "hello"

    def test_normalize_nfc(self):
        i = run('let v = "hello".normalize("NFC")')
        assert val(i) == "hello"

    def test_normalize_nfd(self):
        i = run('let v = "hello".normalize("NFD")')
        assert val(i) == "hello"

    def test_normalize_nfkc(self):
        i = run('let v = "hello".normalize("NFKC")')
        assert val(i) == "hello"


# ── codePointAt ───────────────────────────────────────────────────────────────

class TestCodePointAt:
    def test_codePointAt_A(self):
        i = run('let v = "ABC".codePointAt(0)')
        assert val(i) == 65

    def test_codePointAt_B(self):
        i = run('let v = "ABC".codePointAt(1)')
        assert val(i) == 66

    def test_codePointAt_space(self):
        i = run('let v = " ".codePointAt(0)')
        assert val(i) == 32


# ── String.fromCodePoint ──────────────────────────────────────────────────────

class TestFromCodePoint:
    def test_fromCodePoint_A(self):
        i = run('let v = String.fromCodePoint(65)')
        assert val(i) == "A"

    def test_fromCodePoint_multiple(self):
        i = run('let v = String.fromCodePoint(72, 101, 108, 108, 111)')
        assert val(i) == "Hello"

    def test_fromCodePoint_z(self):
        i = run('let v = String.fromCodePoint(122)')
        assert val(i) == "z"


# ── charCodeAt ────────────────────────────────────────────────────────────────

class TestCharCodeAt:
    def test_charCodeAt_A(self):
        i = run('let v = "ABC".charCodeAt(0)')
        assert val(i) == 65

    def test_charCodeAt_z(self):
        i = run('let v = "z".charCodeAt(0)')
        assert val(i) == 122

    def test_charCodeAt_middle(self):
        i = run('let v = "ABC".charCodeAt(2)')
        assert val(i) == 67


# ── String.fromCharCode ───────────────────────────────────────────────────────

class TestFromCharCode:
    def test_fromCharCode_A(self):
        i = run('let v = String.fromCharCode(65)')
        assert val(i) == "A"

    def test_fromCharCode_hello(self):
        i = run('let v = String.fromCharCode(72, 105)')
        assert val(i) == "Hi"


# ── substring ─────────────────────────────────────────────────────────────────

class TestSubstring:
    def test_substring_world(self):
        i = run('let v = "hello world".substring(6, 11)')
        assert val(i) == "world"

    def test_substring_no_end(self):
        i = run('let v = "hello world".substring(6)')
        assert val(i) == "world"

    def test_substring_empty(self):
        i = run('let v = "hello".substring(2, 2)')
        assert val(i) == ""

    def test_substring_start(self):
        i = run('let v = "hello".substring(0, 3)')
        assert val(i) == "hel"


# ── substr ────────────────────────────────────────────────────────────────────

class TestSubstr:
    def test_substr_world(self):
        i = run('let v = "hello world".substr(6, 5)')
        assert val(i) == "world"

    def test_substr_no_length(self):
        i = run('let v = "hello world".substr(6)')
        assert val(i) == "world"

    def test_substr_from_zero(self):
        i = run('let v = "hello".substr(0, 3)')
        assert val(i) == "hel"

    def test_substr_one_char(self):
        i = run('let v = "hello".substr(1, 1)')
        assert val(i) == "e"


# ── match ─────────────────────────────────────────────────────────────────────

class TestMatch:
    def test_match_first(self):
        i = run('let m = "hello world".match(/\\w+/); let v = m[0]')
        assert val(i) == "hello"

    def test_match_returns_none_no_match(self):
        i = run('let v = "hello".match(/\\d+/)')
        assert val(i) is None

    def test_match_index(self):
        i = run('let m = "hello world".match(/world/); let v = m.index')
        assert val(i) == 6

    def test_match_capture_group(self):
        i = run('let m = "2024-01-15".match(/(\\d{4})-(\\d{2})/); let v = m[1]')
        assert val(i) == "2024"


# ── matchAll ──────────────────────────────────────────────────────────────────

class TestMatchAll:
    def test_matchAll_count(self):
        i = run('let v = [..."hello world".matchAll(/\\w+/g)].length')
        assert val(i) == 2

    def test_matchAll_first_value(self):
        i = run('let matches = [..."hi 42 bye 99".matchAll(/\\d+/g)]; let v = matches[0][0]')
        assert val(i) == "42"

    def test_matchAll_second_value(self):
        i = run('let matches = [..."hi 42 bye 99".matchAll(/\\d+/g)]; let v = matches[1][0]')
        assert val(i) == "99"

    def test_matchAll_no_matches(self):
        i = run('let v = [..."hello".matchAll(/\\d+/g)].length')
        assert val(i) == 0


# ── search ────────────────────────────────────────────────────────────────────

class TestSearch:
    def test_search_found(self):
        i = run('let v = "hello world".search(/world/)')
        assert val(i) == 6

    def test_search_not_found(self):
        i = run('let v = "hello world".search(/xyz/)')
        assert val(i) == -1

    def test_search_start(self):
        i = run('let v = "hello".search(/h/)')
        assert val(i) == 0

    def test_search_digit(self):
        i = run('let v = "abc123".search(/\\d/)')
        assert val(i) == 3


# ── replace with function ─────────────────────────────────────────────────────

class TestReplaceWithFn:
    def test_replace_fn_uppercase(self):
        i = run('let v = "hello".replace(/l/, m => m.toUpperCase())')
        assert val(i) == "heLlo"

    def test_replace_fn_global(self):
        i = run('let v = "hello".replace(/l/g, m => m.toUpperCase())')
        assert val(i) == "heLLo"

    def test_replace_fn_with_match(self):
        i = run('let v = "abc123".replace(/\\d+/, n => "[" + n + "]")')
        assert val(i) == "abc[123]"


# ── replaceAll ────────────────────────────────────────────────────────────────

class TestReplaceAll:
    def test_replaceAll_l(self):
        i = run('let v = "hello world".replaceAll("l", "L")')
        assert val(i) == "heLLo worLd"

    def test_replaceAll_no_match(self):
        i = run('let v = "hello".replaceAll("z", "Z")')
        assert val(i) == "hello"

    def test_replaceAll_space(self):
        i = run('let v = "a b c".replaceAll(" ", "_")')
        assert val(i) == "a_b_c"


# ── split by regex ────────────────────────────────────────────────────────────

class TestSplitRegex:
    def test_split_digit(self):
        i = run('let v = "a1b2c".split(/[0-9]/)')
        assert val(i) == ["a", "b", "c"]

    def test_split_whitespace(self):
        i = run('let v = "hello   world".split(/\\s+/)')
        assert val(i) == ["hello", "world"]

    def test_split_comma_or_semicolon(self):
        i = run('let v = "a,b;c".split(/[,;]/)')
        assert val(i) == ["a", "b", "c"]


# ── trimStart / trimEnd ───────────────────────────────────────────────────────

class TestTrimStartEnd:
    def test_trimStart(self):
        i = run('let v = "  hi  ".trimStart()')
        assert val(i) == "hi  "

    def test_trimEnd(self):
        i = run('let v = "  hi  ".trimEnd()')
        assert val(i) == "  hi"

    def test_trimStart_no_leading(self):
        i = run('let v = "hi  ".trimStart()')
        assert val(i) == "hi  "

    def test_trimEnd_no_trailing(self):
        i = run('let v = "  hi".trimEnd()')
        assert val(i) == "  hi"

    def test_trimStart_all(self):
        i = run('let v = "   ".trimStart()')
        assert val(i) == ""


# ── padStart / padEnd ─────────────────────────────────────────────────────────

class TestPadStartEnd:
    def test_padStart_zeros(self):
        i = run('let v = "5".padStart(3, "0")')
        assert val(i) == "005"

    def test_padEnd_zeros(self):
        i = run('let v = "5".padEnd(3, "0")')
        assert val(i) == "500"

    def test_padStart_spaces(self):
        i = run('let v = "hi".padStart(5)')
        assert val(i) == "   hi"

    def test_padEnd_spaces(self):
        i = run('let v = "hi".padEnd(5)')
        assert val(i) == "hi   "

    def test_padStart_already_long(self):
        i = run('let v = "hello".padStart(3)')
        assert val(i) == "hello"

    def test_padEnd_already_long(self):
        i = run('let v = "hello".padEnd(3)')
        assert val(i) == "hello"


# ── repeat ────────────────────────────────────────────────────────────────────

class TestRepeat:
    def test_repeat_3(self):
        i = run('let v = "ab".repeat(3)')
        assert val(i) == "ababab"

    def test_repeat_1(self):
        i = run('let v = "hello".repeat(1)')
        assert val(i) == "hello"

    def test_repeat_0(self):
        i = run('let v = "hi".repeat(0)')
        assert val(i) == ""

    def test_repeat_dash(self):
        i = run('let v = "-".repeat(5)')
        assert val(i) == "-----"


# ── startsWith with position ──────────────────────────────────────────────────

class TestStartsWithPos:
    def test_startsWith_pos_0(self):
        i = run('let v = "hello".startsWith("he", 0)')
        assert val(i) is True

    def test_startsWith_pos_2(self):
        i = run('let v = "hello".startsWith("ll", 2)')
        assert val(i) is True

    def test_startsWith_pos_miss(self):
        i = run('let v = "hello".startsWith("he", 1)')
        assert val(i) is False

    def test_startsWith_no_pos(self):
        i = run('let v = "hello".startsWith("hel")')
        assert val(i) is True


# ── endsWith with position ────────────────────────────────────────────────────

class TestEndsWithPos:
    def test_endsWith_pos_4(self):
        i = run('let v = "hello".endsWith("ll", 4)')
        assert val(i) is True

    def test_endsWith_pos_full(self):
        i = run('let v = "hello".endsWith("lo", 5)')
        assert val(i) is True

    def test_endsWith_no_pos(self):
        i = run('let v = "hello".endsWith("lo")')
        assert val(i) is True

    def test_endsWith_miss(self):
        i = run('let v = "hello".endsWith("he")')
        assert val(i) is False


# ── includes with position ────────────────────────────────────────────────────

class TestIncludesPos:
    def test_includes_found(self):
        i = run('let v = "hello world".includes("world")')
        assert val(i) is True

    def test_includes_with_pos(self):
        i = run('let v = "hello".includes("ll", 1)')
        assert val(i) is True

    def test_includes_pos_skips(self):
        i = run('let v = "hello".includes("ll", 3)')
        assert val(i) is False

    def test_includes_not_found(self):
        i = run('let v = "hello".includes("xyz")')
        assert val(i) is False

    def test_includes_pos_zero(self):
        i = run('let v = "hello".includes("he", 0)')
        assert val(i) is True
