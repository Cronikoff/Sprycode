"""
Tests for the SpryCode Parser.
"""

import pytest
from sprycode.ast_nodes import (
    AllowStatement,
    AppDeclaration,
    Assignment,
    BinaryExpression,
    Block,
    BoolLiteral,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    LetDeclaration,
    LogStatement,
    MoveStatement,
    NumberLiteral,
    ObjectLiteral,
    ParseStatement,
    PipelineExpression,
    Program,
    ReadStatement,
    ReturnStatement,
    SecretLiteral,
    StringLiteral,
    TaskDeclaration,
    TransactionStatement,
    TryCatchStatement,
    VarDeclaration,
    WriteStatement,
)
from sprycode.lexer import Lexer
from sprycode.parser import ParseError, Parser


def parse(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def parse_first(source: str):
    return parse(source).body[0]


class TestLetDeclaration:
    def test_simple_let(self):
        node = parse_first('let name = "SpryCode"')
        assert isinstance(node, LetDeclaration)
        assert node.name == "name"
        assert isinstance(node.value, StringLiteral)
        assert node.value.value == "SpryCode"

    def test_let_with_type(self):
        node = parse_first("let age: Number = 32")
        assert isinstance(node, LetDeclaration)
        assert node.name == "age"
        assert node.type_annotation == "Number"
        assert isinstance(node.value, NumberLiteral)

    def test_let_bool(self):
        node = parse_first("let active = true")
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, BoolLiteral)
        assert node.value.value is True

    def test_let_number(self):
        node = parse_first("let x = 42")
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, NumberLiteral)
        assert node.value.value == 42.0

    def test_let_no_value(self):
        node = parse_first("let x: Text")
        assert isinstance(node, LetDeclaration)
        assert node.value is None


class TestVarDeclaration:
    def test_simple_var(self):
        node = parse_first("var retries = 0")
        assert isinstance(node, VarDeclaration)
        assert node.name == "retries"

    def test_var_with_type(self):
        node = parse_first("var count: Int = 5")
        assert isinstance(node, VarDeclaration)
        assert node.type_annotation == "Int"


class TestFunctionDeclaration:
    def test_simple_fn(self):
        node = parse_first('fn greet(name: Text) -> Text {\n    return "Hello"\n}')
        assert isinstance(node, FunctionDeclaration)
        assert node.name == "greet"
        assert len(node.params) == 1
        assert node.params[0] == ("name", "Text")
        assert node.return_type == "Text"

    def test_fn_no_params(self):
        node = parse_first("fn hello() {\n    log info \"hello\"\n}")
        assert isinstance(node, FunctionDeclaration)
        assert node.params == []

    def test_fn_multiple_params(self):
        node = parse_first("fn add(a: Number, b: Number) -> Number { return a }")
        assert len(node.params) == 2

    def test_fn_short_form(self):
        node = parse_first("fn double(x: Number) => x * 2")
        assert isinstance(node, FunctionDeclaration)
        assert node.short_form is True
        assert node.name == "double"


class TestTaskDeclaration:
    def test_simple_task(self):
        node = parse_first("task hello {\n    log info \"Hello\"\n}")
        assert isinstance(node, TaskDeclaration)
        assert node.name == "hello"
        assert isinstance(node.body, Block)

    def test_task_with_permissions(self):
        source = """task backup {
    allow filesystem.read "./data"
    allow filesystem.write "./backup"
    move file "./data/a.txt" to "./backup/a.txt"
}"""
        node = parse_first(source)
        assert isinstance(node, TaskDeclaration)
        assert len(node.body.body) == 3


class TestPermissions:
    def test_allow_with_path(self):
        node = parse_first('allow filesystem.read "./data"')
        assert isinstance(node, AllowStatement)
        assert node.permission == "filesystem.read"
        assert node.argument == "./data"

    def test_allow_no_arg(self):
        node = parse_first("allow filesystem.read")
        assert isinstance(node, AllowStatement)
        assert node.argument is None

    def test_allow_nested_permission(self):
        node = parse_first("allow network.request")
        assert isinstance(node, AllowStatement)
        assert node.permission == "network.request"


class TestIfStatement:
    def test_simple_if(self):
        node = parse_first("if x == 1 { log info \"yes\" }")
        assert isinstance(node, IfStatement)
        assert node.else_block is None

    def test_if_else(self):
        source = "if x > 0 { log info \"pos\" } else { log info \"neg\" }"
        node = parse_first(source)
        assert isinstance(node, IfStatement)
        assert node.else_block is not None


class TestTryCatch:
    def test_try_catch(self):
        source = 'try { let x = 1 } catch err { log error err }'
        node = parse_first(source)
        assert isinstance(node, TryCatchStatement)
        assert node.error_name == "err"


class TestFileOperations:
    def test_move_file(self):
        node = parse_first('move file "./a.txt" to "./b.txt"')
        assert isinstance(node, MoveStatement)
        assert node.target_type == "file"
        assert isinstance(node.source, StringLiteral)
        assert node.source.value == "./a.txt"
        assert isinstance(node.destination, StringLiteral)
        assert node.destination.value == "./b.txt"

    def test_move_file_with_checksum(self):
        node = parse_first('move file "./a.txt" to "./b.txt" verify checksum sha256')
        assert isinstance(node, MoveStatement)
        assert node.verify_checksum == "sha256"

    def test_move_file_with_retry(self):
        node = parse_first('move file "./a.txt" to "./b.txt" retry 3')
        assert isinstance(node, MoveStatement)
        assert node.retry == 3

    def test_move_folder(self):
        node = parse_first('move folder "./src" to "./dst"')
        assert isinstance(node, MoveStatement)
        assert node.target_type == "folder"

    def test_read_file(self):
        node = parse_first('read file "data.csv"')
        assert isinstance(node, ReadStatement)
        assert isinstance(node.path, StringLiteral)
        assert node.path.value == "data.csv"

    def test_write_file(self):
        node = parse_first('write file "output.txt" with data')
        assert isinstance(node, WriteStatement)
        assert isinstance(node.path, StringLiteral)
        assert isinstance(node.data, Identifier)


class TestTransaction:
    def test_simple_transaction(self):
        source = 'transaction db.main { log info "ok" }'
        node = parse_first(source)
        assert isinstance(node, TransactionStatement)

    def test_transaction_with_target(self):
        source = 'transaction filesystem { copy file "./a.txt" to "./b.txt" }'
        node = parse_first(source)
        assert isinstance(node, TransactionStatement)


class TestBinaryExpressions:
    def test_addition(self):
        node = parse_first("let x = 1 + 2")
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, BinaryExpression)
        assert node.value.op == "+"

    def test_string_concat(self):
        node = parse_first('let s = "hello" + " world"')
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, BinaryExpression)

    def test_equality(self):
        node = parse_first("let b = x == 1")
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, BinaryExpression)
        assert node.value.op == "=="

    def test_complex_expression(self):
        node = parse_first("let result = (a + b) * c")
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, BinaryExpression)
        assert node.value.op == "*"


class TestObjectLiteral:
    def test_simple_object(self):
        node = parse_first('let obj = { name: "Alex", age: 30 }')
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, ObjectLiteral)
        assert "name" in node.value.pairs
        assert "age" in node.value.pairs

    def test_nested_object(self):
        node = parse_first('let obj = { a: { b: 1 } }')
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, ObjectLiteral)


class TestLogStatement:
    def test_log_info(self):
        node = parse_first('log info "Task started"')
        assert isinstance(node, LogStatement)
        assert node.level == "info"

    def test_log_error(self):
        node = parse_first("log error err")
        assert isinstance(node, LogStatement)
        assert node.level == "error"

    def test_log_warn(self):
        node = parse_first('log warn "retrying"')
        assert isinstance(node, LogStatement)
        assert node.level == "warn"


class TestSecretLiteral:
    def test_secret(self):
        node = parse_first('let key = secret "API_KEY"')
        assert isinstance(node, LetDeclaration)
        assert isinstance(node.value, SecretLiteral)
        assert node.value.key == "API_KEY"


class TestAppDeclaration:
    def test_app(self):
        node = parse_first('app MyApp version "1.0.0"')
        assert isinstance(node, AppDeclaration)
        assert node.name == "MyApp"
        assert node.version == "1.0.0"


class TestPipeline:
    def test_simple_pipeline(self):
        source = 'let result = read file "a.txt" |> parse json'
        node = parse_first(source)
        assert isinstance(node, LetDeclaration)


class TestParseErrors:
    def test_missing_closing_brace(self):
        with pytest.raises(ParseError):
            parse("task x { log info \"oops\"")

    def test_missing_to_in_move(self):
        with pytest.raises(ParseError):
            parse('move file "./a.txt" "./b.txt"')
