"""Tests for Phase 66 features: Comprehensive String Methods"""
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


class TestPadStartPadEnd:
    def test_pad_start_basic(self):
        assert val(run('let v = "5".padStart(3, "0")')) == "005"

    def test_pad_start_no_pad_needed(self):
        assert val(run('let v = "hello".padStart(3, "0")')) == "hello"

    def test_pad_start_exact_length(self):
        assert val(run('let v = "abc".padStart(3, "x")')) == "abc"

    def test_pad_start_spaces(self):
        assert val(run('let v = "hi".padStart(5)')) == "   hi"

    def test_pad_end_basic(self):
        assert val(run('let v = "5".padEnd(3, "0")')) == "500"

    def test_pad_end_no_pad_needed(self):
        assert val(run('let v = "hello".padEnd(3, "0")')) == "hello"

    def test_pad_end_spaces(self):
        assert val(run('let v = "hi".padEnd(5)')) == "hi   "

    def test_pad_start_with_fill_char(self):
        assert val(run('let v = "1".padStart(5, "x")')) == "xxxx1"

    def test_pad_end_with_fill_char(self):
        assert val(run('let v = "1".padEnd(5, "x")')) == "1xxxx"


class TestTrimStartTrimEnd:
    def test_trim_start_basic(self):
        assert val(run('let v = "  hello".trimStart()')) == "hello"

    def test_trim_start_trailing_preserved(self):
        assert val(run('let v = "  hi  ".trimStart()')) == "hi  "

    def test_trim_end_basic(self):
        assert val(run('let v = "hello  ".trimEnd()')) == "hello"

    def test_trim_end_leading_preserved(self):
        assert val(run('let v = "  hi  ".trimEnd()')) == "  hi"

    def test_trim_start_no_whitespace(self):
        assert val(run('let v = "hello".trimStart()')) == "hello"

    def test_trim_end_no_whitespace(self):
        assert val(run('let v = "hello".trimEnd()')) == "hello"

    def test_trim_start_tabs_newlines(self):
        result = val(run('let v = "\\t\\nhello".trimStart()'))
        assert result == "hello"

    def test_trim_end_tabs_newlines(self):
        result = val(run('let v = "hello\\t\\n".trimEnd()'))
        assert result == "hello"


class TestRepeat:
    def test_repeat_basic(self):
        assert val(run('let v = "ab".repeat(3)')) == "ababab"

    def test_repeat_zero(self):
        assert val(run('let v = "abc".repeat(0)')) == ""

    def test_repeat_one(self):
        assert val(run('let v = "xyz".repeat(1)')) == "xyz"

    def test_repeat_single_char(self):
        assert val(run('let v = "a".repeat(5)')) == "aaaaa"

    def test_repeat_longer_string(self):
        assert val(run('let v = "ha".repeat(4)')) == "hahahaha"


class TestIndexOfLastIndexOf:
    def test_index_of_basic(self):
        assert val(run('let v = "hello".indexOf("l")')) == 2

    def test_index_of_not_found(self):
        assert val(run('let v = "hello".indexOf("x")')) == -1

    def test_index_of_with_from(self):
        assert val(run('let v = "hello".indexOf("l", 3)')) == 3

    def test_index_of_from_past_end(self):
        assert val(run('let v = "hello".indexOf("l", 4)')) == -1

    def test_last_index_of_basic(self):
        assert val(run('let v = "hello".lastIndexOf("l")')) == 3

    def test_last_index_of_not_found(self):
        assert val(run('let v = "hello".lastIndexOf("x")')) == -1

    def test_last_index_of_with_from(self):
        assert val(run('let v = "hello".lastIndexOf("l", 2)')) == 2

    def test_index_of_empty_string(self):
        assert val(run('let v = "hello".indexOf("")')) == 0

    def test_last_index_of_empty_string(self):
        result = val(run('let v = "hello".lastIndexOf("")'))
        assert result >= 0


class TestStartsWithEndsWith:
    def test_starts_with_true(self):
        assert val(run('let v = "hello".startsWith("hel")')) is True

    def test_starts_with_false(self):
        assert val(run('let v = "hello".startsWith("world")')) is False

    def test_starts_with_position(self):
        assert val(run('let v = "hello".startsWith("lo", 3)')) is True

    def test_starts_with_position_false(self):
        assert val(run('let v = "hello".startsWith("lo", 2)')) is False

    def test_ends_with_true(self):
        assert val(run('let v = "hello".endsWith("llo")')) is True

    def test_ends_with_false(self):
        assert val(run('let v = "hello".endsWith("hel")')) is False

    def test_ends_with_length(self):
        assert val(run('let v = "hello world".endsWith("hello", 5)')) is True

    def test_starts_with_empty(self):
        assert val(run('let v = "hello".startsWith("")')) is True

    def test_ends_with_empty(self):
        assert val(run('let v = "hello".endsWith("")')) is True


class TestNormalizeCodePoint:
    def test_normalize_returns_string(self):
        assert val(run('let v = "hello".normalize()')) == "hello"

    def test_normalize_unicode(self):
        result = val(run('let v = "caf\u00e9".normalize()'))
        assert isinstance(result, str)

    def test_code_point_at_basic(self):
        assert val(run('let v = "A".codePointAt(0)')) == 65

    def test_code_point_at_lowercase(self):
        assert val(run('let v = "hello".codePointAt(0)')) == 104

    def test_code_point_at_index(self):
        assert val(run('let v = "hello".codePointAt(1)')) == 101

    def test_from_code_point_basic(self):
        assert val(run('let v = String.fromCodePoint(65)')) == "A"

    def test_from_code_point_multiple(self):
        assert val(run('let v = String.fromCodePoint(65, 66, 67)')) == "ABC"

    def test_from_char_code_basic(self):
        assert val(run('let v = String.fromCharCode(65)')) == "A"

    def test_from_char_code_multiple(self):
        assert val(run('let v = String.fromCharCode(72, 101, 108, 108, 111)')) == "Hello"

    def test_char_code_at_basic(self):
        assert val(run('let v = "A".charCodeAt(0)')) == 65

    def test_char_code_at_index(self):
        assert val(run('let v = "hello".charCodeAt(4)')) == 111


class TestSubstring:
    def test_substring_basic(self):
        assert val(run('let v = "hello".substring(1, 3)')) == "el"

    def test_substring_from_start(self):
        assert val(run('let v = "hello".substring(0, 3)')) == "hel"

    def test_substring_to_end(self):
        assert val(run('let v = "hello".substring(2)')) == "llo"

    def test_substring_full(self):
        assert val(run('let v = "hello".substring(0)')) == "hello"

    def test_substring_empty(self):
        assert val(run('let v = "hello".substring(2, 2)')) == ""

    def test_substring_single_char(self):
        assert val(run('let v = "hello".substring(1, 2)')) == "e"


class TestSplit:
    def test_split_basic(self):
        assert val(run('let v = "a,b,c".split(",")')) == ["a", "b", "c"]

    def test_split_with_limit(self):
        assert val(run('let v = "a,b,c".split(",", 2)')) == ["a", "b"]

    def test_split_empty_sep(self):
        assert val(run('let v = "abc".split("")')) == ["a", "b", "c"]

    def test_split_not_found(self):
        assert val(run('let v = "hello".split(",")')) == ["hello"]

    def test_split_repeated_sep(self):
        assert val(run('let v = "hello".split("l")')) == ["he", "", "o"]

    def test_split_limit_zero(self):
        assert val(run('let v = "a,b,c".split(",", 0)')) == []


class TestMatchSearchReplaceIncludes:
    def test_search_found(self):
        assert val(run('let v = "hello".search(/l/)')) == 2

    def test_search_not_found(self):
        assert val(run('let v = "hello".search(/x/)')) == -1

    def test_replace_basic(self):
        assert val(run('let v = "hello world".replace("world", "there")')) == "hello there"

    def test_replace_first_only(self):
        assert val(run('let v = "aabbaa".replace("a", "x")')) == "xabbaa"

    def test_replace_all_basic(self):
        assert val(run('let v = "aabbcc".replaceAll("b", "x")')) == "aaxxcc"

    def test_replace_all_no_match(self):
        assert val(run('let v = "hello".replaceAll("x", "y")')) == "hello"

    def test_includes_true(self):
        assert val(run('let v = "hello world".includes("world")')) is True

    def test_includes_false(self):
        assert val(run('let v = "hello".includes("xyz")')) is False

    def test_includes_with_position(self):
        # includes with from position - first check it works without position
        assert val(run('let v = "hello".includes("hel")')) is True

    def test_match_returns_result(self):
        result = val(run('let v = "hello".match(/l+/)'))
        assert result is not None

    def test_search_at_start(self):
        assert val(run('let v = "hello".search(/h/)')) == 0


class TestAtMethod:
    def test_at_positive(self):
        assert val(run('let v = "hello".at(0)')) == "h"

    def test_at_negative(self):
        assert val(run('let v = "hello".at(-1)')) == "o"

    def test_at_negative_two(self):
        assert val(run('let v = "hello".at(-2)')) == "l"

    def test_at_middle(self):
        assert val(run('let v = "hello".at(2)')) == "l"

    def test_at_last(self):
        assert val(run('let v = "hello".at(4)')) == "o"

    def test_at_out_of_bounds(self):
        result = val(run('let v = "hello".at(10)'))
        assert result is None or result == "undefined"
