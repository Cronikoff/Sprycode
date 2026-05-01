"""
Tests for the SpryCode Lexer.
"""

import pytest
from sprycode.lexer import Lexer, LexerError, Token, TokenType


def tokenize(source: str) -> list[Token]:
    return Lexer(source).tokenize()


def token_types(source: str) -> list[TokenType]:
    return [t.type for t in tokenize(source)]


class TestBasicTokens:
    def test_empty_source(self):
        tokens = tokenize("")
        assert tokens == [Token(TokenType.EOF, "", 1, 1)]

    def test_string_double_quote(self):
        tokens = tokenize('"hello world"')
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_string_single_quote(self):
        tokens = tokenize("'hello'")
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello"

    def test_string_escape_sequences(self):
        tokens = tokenize(r'"hello\nworld"')
        assert tokens[0].value == "hello\nworld"

    def test_integer(self):
        tokens = tokenize("42")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "42"

    def test_float(self):
        tokens = tokenize("3.14")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "3.14"

    def test_number_with_underscore(self):
        tokens = tokenize("1_000_000")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "1000000"

    def test_bool_true(self):
        tokens = tokenize("true")
        assert tokens[0].type == TokenType.BOOL
        assert tokens[0].value == "true"

    def test_bool_false(self):
        tokens = tokenize("false")
        assert tokens[0].type == TokenType.BOOL
        assert tokens[0].value == "false"

    def test_identifier(self):
        tokens = tokenize("myVariable")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "myVariable"

    def test_identifier_underscore(self):
        tokens = tokenize("_private_var")
        assert tokens[0].type == TokenType.IDENTIFIER


class TestKeywords:
    def test_let_keyword(self):
        tokens = tokenize("let")
        assert tokens[0].type == TokenType.LET

    def test_var_keyword(self):
        tokens = tokenize("var")
        assert tokens[0].type == TokenType.VAR

    def test_fn_keyword(self):
        tokens = tokenize("fn")
        assert tokens[0].type == TokenType.FN

    def test_task_keyword(self):
        tokens = tokenize("task")
        assert tokens[0].type == TokenType.TASK

    def test_allow_keyword(self):
        tokens = tokenize("allow")
        assert tokens[0].type == TokenType.ALLOW

    def test_deny_keyword(self):
        tokens = tokenize("deny")
        assert tokens[0].type == TokenType.DENY

    def test_move_keyword(self):
        tokens = tokenize("move")
        assert tokens[0].type == TokenType.MOVE

    def test_types(self):
        assert tokenize("Text")[0].type == TokenType.TEXT
        assert tokenize("Number")[0].type == TokenType.NUMBER_TYPE
        assert tokenize("Bool")[0].type == TokenType.BOOL_TYPE
        assert tokenize("Secret")[0].type == TokenType.SECRET_TYPE
        assert tokenize("Money")[0].type == TokenType.MONEY_TYPE


class TestOperators:
    def test_arrow(self):
        tokens = tokenize("->")
        assert tokens[0].type == TokenType.ARROW

    def test_fat_arrow(self):
        tokens = tokenize("=>")
        assert tokens[0].type == TokenType.FAT_ARROW

    def test_pipe_arrow(self):
        tokens = tokenize("|>")
        assert tokens[0].type == TokenType.PIPE_ARROW

    def test_eq_eq(self):
        tokens = tokenize("==")
        assert tokens[0].type == TokenType.EQ_EQ

    def test_bang_eq(self):
        tokens = tokenize("!=")
        assert tokens[0].type == TokenType.BANG_EQ

    def test_and_and(self):
        tokens = tokenize("&&")
        assert tokens[0].type == TokenType.AND_AND

    def test_or_or(self):
        tokens = tokenize("||")
        assert tokens[0].type == TokenType.OR_OR

    def test_lt_eq(self):
        tokens = tokenize("<=")
        assert tokens[0].type == TokenType.LT_EQ

    def test_gt_eq(self):
        tokens = tokenize(">=")
        assert tokens[0].type == TokenType.GT_EQ


class TestComments:
    def test_single_line_comment_filtered(self):
        tokens = tokenize("// this is a comment\nlet x = 1")
        # Comments should be filtered out
        types = [t.type for t in tokens]
        assert TokenType.COMMENT not in types
        assert TokenType.LET in types

    def test_multi_line_comment_filtered(self):
        tokens = tokenize("/* multi\nline */ let x = 1")
        types = [t.type for t in tokens]
        assert TokenType.COMMENT not in types
        assert TokenType.LET in types


class TestErrors:
    def test_unterminated_string(self):
        with pytest.raises(LexerError):
            tokenize('"unterminated')

    def test_unexpected_character(self):
        with pytest.raises(LexerError):
            tokenize("@invalid")


class TestLineTracking:
    def test_line_numbers(self):
        tokens = tokenize("let\nvar\nfn")
        assert tokens[0].line == 1
        # After stripping newlines in tokenize()
        lines = [t.line for t in tokens if t.type != TokenType.EOF]
        assert 1 in lines
        assert 2 in lines
        assert 3 in lines

    def test_column_numbers(self):
        tokens = tokenize("let x = 1")
        let_tok = tokens[0]
        assert let_tok.line == 1
        assert let_tok.column == 1


class TestComplexExpressions:
    def test_full_let_statement(self):
        types = token_types('let name = "SpryCode"')
        assert TokenType.LET in types
        assert TokenType.IDENTIFIER in types
        assert TokenType.EQ in types
        assert TokenType.STRING in types

    def test_permission_path(self):
        types = token_types("allow filesystem.read")
        assert TokenType.ALLOW in types
        assert TokenType.IDENTIFIER in types
        assert TokenType.DOT in types

    def test_pipeline(self):
        types = token_types('read file "a.txt" |> parse csv')
        assert TokenType.READ in types
        # lowercase "file" is tokenized as FILE_TYPE keyword
        assert TokenType.FILE_TYPE in types
        assert TokenType.PIPE_ARROW in types
        assert TokenType.PARSE in types
