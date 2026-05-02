"""
SpryCode Lexer

Tokenizes SpryCode source code into a stream of tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator


class TokenType(Enum):
    # Literals
    STRING = auto()
    NUMBER = auto()
    BOOL = auto()

    # Identifiers and keywords
    IDENTIFIER = auto()

    # Keywords — control flow
    IF = auto()
    ELSE = auto()
    RETURN = auto()
    STOP = auto()
    TRY = auto()
    CATCH = auto()
    FAILED = auto()
    NOT = auto()

    # Keywords — declarations
    LET = auto()
    VAR = auto()
    FN = auto()
    TASK = auto()
    APP = auto()
    USE = auto()
    ADAPTER = auto()
    CONNECTOR = auto()

    # Keywords — permissions / privacy
    ALLOW = auto()
    DENY = auto()
    PRIVATE = auto()
    SENSITIVE = auto()
    DATA = auto()
    SECRET = auto()
    SANDBOXED = auto()

    # Keywords — file / data operations
    READ = auto()
    WRITE = auto()
    COPY = auto()
    MOVE = auto()
    DELETE = auto()
    STREAM = auto()
    SYNC = auto()
    WATCH = auto()
    COMPRESS = auto()
    EXTRACT = auto()
    PARSE = auto()
    ENCODE = auto()
    DECODE = auto()
    HASH = auto()
    ENCRYPT = auto()
    DECRYPT = auto()
    CHECKSUM = auto()

    # Keywords — transaction / reliability
    ATOMIC = auto()
    TRANSACTION = auto()
    COMPENSATE = auto()
    ROLLBACK = auto()
    COMMIT = auto()

    # Keywords — movement modifiers
    TO = auto()
    FROM = auto()
    WITH = auto()
    IN = auto()
    WHERE = auto()
    AS = auto()
    AT = auto()
    PARALLEL = auto()
    VERIFY = auto()
    PRESERVE = auto()
    RETRY = auto()
    MODE = auto()
    COMPARE = auto()
    FILTER = auto()
    MAP = auto()
    EACH = auto()
    VALIDATE = auto()
    REDACT = auto()
    FIELDS = auto()
    TRANSLATE = auto()
    OUTPUT = auto()
    USING = auto()
    LAST = auto()
    OK = auto()
    FAIL = auto()
    RESULT = auto()
    TAKE = auto()
    SKIP = auto()
    GROUPBY = auto()
    SORT_BY = auto()

    # Keywords — logging
    LOG = auto()
    INFO = auto()
    WARN = auto()
    ERROR = auto()

    # Keywords — network
    HTTP = auto()
    WEBSOCKET = auto()
    TIMEOUT = auto()
    SCHEDULE = auto()
    DAILY = auto()
    SLEEP = auto()

    # Keywords — fraud / compliance
    FRAUD = auto()
    CHECK = auto()
    REASON = auto()
    CASE = auto()
    SCOPE = auto()
    MINIMAL = auto()

    # Keywords — loops
    FOR = auto()
    WHILE = auto()
    BREAK = auto()
    CONTINUE = auto()
    REPEAT = auto()
    UNTIL = auto()
    DO = auto()
    FINALLY = auto()

    # Keywords — switch / case
    SWITCH = auto()
    DEFAULT = auto()

    # Keywords — match / pattern matching
    MATCH = auto()

    # Keywords — assert
    ASSERT = auto()

    # Keywords — reduce
    REDUCE = auto()

    # Wildcard placeholder for match
    UNDERSCORE = auto()

    # Keywords — testing
    TEST = auto()
    EXPECT = auto()
    EXISTS = auto()
    DENIED = auto()

    # Keywords — file creation / archive
    CREATE = auto()

    # Keywords — import / export
    IMPORT = auto()
    EXPORT = auto()

    # Keywords — OOP / throw
    THROW = auto()
    ENUM = auto()
    CLASS = auto()
    STRUCT = auto()
    INTERFACE = auto()
    EXTENDS = auto()
    IMPLEMENTS = auto()
    ASYNC = auto()
    AWAIT = auto()
    SELF = auto()
    TYPEOF = auto()
    INSTANCEOF = auto()
    VOID = auto()            # void operator
    PRIVATE_IDENT = auto()   # #identifier (private field)
    SPAWN = auto()
    DEBIT = auto()
    CREDIT = auto()
    YIELD = auto()
    FN_STAR = auto()  # fn* generator function
    MIXIN = auto()    # mixin keyword for class mixins
    WHEN = auto()     # match guard: case pattern when condition =>
    SUPER = auto()    # super() constructor/method call

    # Types
    TEXT = auto()
    NUMBER_TYPE = auto()
    INT_TYPE = auto()
    FLOAT_TYPE = auto()
    BOOL_TYPE = auto()
    DATE_TYPE = auto()
    TIME_TYPE = auto()
    DATETIME_TYPE = auto()
    DURATION_TYPE = auto()
    FILE_TYPE = auto()
    FOLDER_TYPE = auto()
    PATH_TYPE = auto()
    JSON_TYPE = auto()
    XML_TYPE = auto()
    BINARY_TYPE = auto()
    SECRET_TYPE = auto()
    EMAIL_TYPE = auto()
    URL_TYPE = auto()
    UUID_TYPE = auto()
    MONEY_TYPE = auto()
    TRANSACTION_TYPE = auto()
    RESULT_TYPE = auto()
    OPTION_TYPE = auto()
    LIST_TYPE = auto()
    MAP_TYPE = auto()
    STREAM_TYPE = auto()
    EVENT_TYPE = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ_EQ = auto()
    BANG_EQ = auto()
    LT = auto()
    GT = auto()
    LT_EQ = auto()
    GT_EQ = auto()
    AND_AND = auto()
    OR_OR = auto()
    AND_AND_EQ = auto()   # &&= (logical-and assignment)
    OR_OR_EQ = auto()     # ||= (logical-or assignment)
    BANG = auto()
    EQ = auto()
    ARROW = auto()        # ->
    FAT_ARROW = auto()    # =>
    PIPE_ARROW = auto()   # |>
    PLUS_EQ = auto()      # +=
    MINUS_EQ = auto()     # -=
    STAR_EQ = auto()      # *=
    SLASH_EQ = auto()     # /=
    STAR_STAR = auto()    # ** (power)
    QUESTION = auto()     # ? (ternary)
    QUESTION_QUESTION = auto()  # ?? (null coalescing)
    QUESTION_QUESTION_EQ = auto()  # ??= (null-coalescing assignment)
    QUESTION_DOT = auto()  # ?. (optional chaining)
    ELLIPSIS = auto()     # ... (spread)
    DOTDOT = auto()       # .. (range)
    PLUS_PLUS = auto()    # ++ (increment)
    MINUS_MINUS = auto()  # -- (decrement)
    PERCENT_EQ = auto()   # %=
    REGEX = auto()        # /pattern/flags

    # Bitwise operators
    AMP = auto()          # &  (bitwise AND)
    PIPE = auto()         # |  (bitwise OR)
    CARET = auto()        # ^  (bitwise XOR)
    TILDE = auto()        # ~  (bitwise NOT)
    LSHIFT = auto()       # << (left shift)
    RSHIFT = auto()       # >> (right shift)
    URSHIFT = auto()      # >>> (unsigned right shift)
    AMP_EQ = auto()       # &= (bitwise AND assign)
    PIPE_EQ = auto()      # |= (bitwise OR assign)
    CARET_EQ = auto()     # ^= (bitwise XOR assign)
    LSHIFT_EQ = auto()    # <<= (left shift assign)
    RSHIFT_EQ = auto()    # >>= (right shift assign)

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    SEMICOLON = auto()

    # Special
    NEWLINE = auto()
    EOF = auto()
    COMMENT = auto()
    FSTRING = auto()    # f"..." interpolated string


# Map keyword strings to their token types
KEYWORDS: dict[str, TokenType] = {
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "return": TokenType.RETURN,
    "stop": TokenType.STOP,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "failed": TokenType.FAILED,
    "not": TokenType.NOT,
    "let": TokenType.LET,
    "var": TokenType.VAR,
    "fn": TokenType.FN,
    "task": TokenType.TASK,
    "app": TokenType.APP,
    "use": TokenType.USE,
    "adapter": TokenType.ADAPTER,
    "connector": TokenType.CONNECTOR,
    "allow": TokenType.ALLOW,
    "deny": TokenType.DENY,
    "private": TokenType.PRIVATE,
    "sensitive": TokenType.SENSITIVE,
    "data": TokenType.DATA,
    "secret": TokenType.SECRET,
    "sandboxed": TokenType.SANDBOXED,
    "read": TokenType.READ,
    "write": TokenType.WRITE,
    "copy": TokenType.COPY,
    "move": TokenType.MOVE,
    "delete": TokenType.DELETE,
    "stream": TokenType.STREAM,
    "sync": TokenType.SYNC,
    "watch": TokenType.WATCH,
    "compress": TokenType.COMPRESS,
    "extract": TokenType.EXTRACT,
    "parse": TokenType.PARSE,
    "encode": TokenType.ENCODE,
    "decode": TokenType.DECODE,
    "hash": TokenType.HASH,
    "encrypt": TokenType.ENCRYPT,
    "decrypt": TokenType.DECRYPT,
    "checksum": TokenType.CHECKSUM,
    "atomic": TokenType.ATOMIC,
    "transaction": TokenType.TRANSACTION,
    "compensate": TokenType.COMPENSATE,
    "rollback": TokenType.ROLLBACK,
    "commit": TokenType.COMMIT,
    "to": TokenType.TO,
    "from": TokenType.FROM,
    "with": TokenType.WITH,
    "in": TokenType.IN,
    "where": TokenType.WHERE,
    "as": TokenType.AS,
    "at": TokenType.AT,
    "parallel": TokenType.PARALLEL,
    "verify": TokenType.VERIFY,
    "preserve": TokenType.PRESERVE,
    "retry": TokenType.RETRY,
    "mode": TokenType.MODE,
    "compare": TokenType.COMPARE,
    "filter": TokenType.FILTER,
    "map": TokenType.MAP,
    "each": TokenType.EACH,
    "validate": TokenType.VALIDATE,
    "redact": TokenType.REDACT,
    "fields": TokenType.FIELDS,
    "translate": TokenType.TRANSLATE,
    "output": TokenType.OUTPUT,
    "using": TokenType.USING,
    "last": TokenType.LAST,
    "ok": TokenType.OK,
    "fail": TokenType.FAIL,
    "result": TokenType.RESULT,
    "take": TokenType.TAKE,
    "skip": TokenType.SKIP,
    "groupBy": TokenType.GROUPBY,
    "sortBy": TokenType.SORT_BY,
    "log": TokenType.LOG,
    "info": TokenType.INFO,
    "warn": TokenType.WARN,
    "error": TokenType.ERROR,
    "http": TokenType.HTTP,
    "websocket": TokenType.WEBSOCKET,
    "timeout": TokenType.TIMEOUT,
    "schedule": TokenType.SCHEDULE,
    "daily": TokenType.DAILY,
    "sleep": TokenType.SLEEP,
    "fraud": TokenType.FRAUD,
    "check": TokenType.CHECK,
    "reason": TokenType.REASON,
    "case": TokenType.CASE,
    "scope": TokenType.SCOPE,
    "minimal": TokenType.MINIMAL,
    "import": TokenType.IMPORT,
    "export": TokenType.EXPORT,
    "for": TokenType.FOR,
    "while": TokenType.WHILE,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "repeat": TokenType.REPEAT,
    "until": TokenType.UNTIL,
    "do": TokenType.DO,
    "finally": TokenType.FINALLY,
    "switch": TokenType.SWITCH,
    "default": TokenType.DEFAULT,
    "match": TokenType.MATCH,
    "assert": TokenType.ASSERT,
    "reduce": TokenType.REDUCE,
    "_": TokenType.UNDERSCORE,
    "test": TokenType.TEST,
    "expect": TokenType.EXPECT,
    "exists": TokenType.EXISTS,
    "denied": TokenType.DENIED,
    "create": TokenType.CREATE,
    "true": TokenType.BOOL,
    "false": TokenType.BOOL,
    "throw": TokenType.THROW,
    "enum": TokenType.ENUM,
    "class": TokenType.CLASS,
    "struct": TokenType.STRUCT,
    "interface": TokenType.INTERFACE,
    "extends": TokenType.EXTENDS,
    "implements": TokenType.IMPLEMENTS,
    "async": TokenType.ASYNC,
    "await": TokenType.AWAIT,
    "self": TokenType.SELF,
    "typeof": TokenType.TYPEOF,
    "instanceof": TokenType.INSTANCEOF,
    "void": TokenType.VOID,
    "spawn": TokenType.SPAWN,
    "debit": TokenType.DEBIT,
    "credit": TokenType.CREDIT,
    "yield": TokenType.YIELD,
    "mixin": TokenType.MIXIN,
    "when": TokenType.WHEN,
    "super": TokenType.SUPER,
    # Types (both capitalized form for annotations and lowercase for operations)
    "Text": TokenType.TEXT,
    "Number": TokenType.NUMBER_TYPE,
    "Int": TokenType.INT_TYPE,
    "Float": TokenType.FLOAT_TYPE,
    "Bool": TokenType.BOOL_TYPE,
    "Date": TokenType.DATE_TYPE,
    "Time": TokenType.TIME_TYPE,
    "DateTime": TokenType.DATETIME_TYPE,
    "Duration": TokenType.DURATION_TYPE,
    "File": TokenType.FILE_TYPE,
    "file": TokenType.FILE_TYPE,
    "Folder": TokenType.FOLDER_TYPE,
    "folder": TokenType.FOLDER_TYPE,
    "Path": TokenType.PATH_TYPE,
    "Json": TokenType.JSON_TYPE,
    "Xml": TokenType.XML_TYPE,
    "Binary": TokenType.BINARY_TYPE,
    "Secret": TokenType.SECRET_TYPE,
    "Email": TokenType.EMAIL_TYPE,
    "Url": TokenType.URL_TYPE,
    "Uuid": TokenType.UUID_TYPE,
    "Money": TokenType.MONEY_TYPE,
    "Transaction": TokenType.TRANSACTION_TYPE,
    "Result": TokenType.RESULT_TYPE,
    "Option": TokenType.OPTION_TYPE,
    "List": TokenType.LIST_TYPE,
    "Map": TokenType.MAP_TYPE,
    "Stream": TokenType.STREAM_TYPE,
    "Event": TokenType.EVENT_TYPE,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"Lexer error at line {line}, column {column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    """Tokenizes SpryCode source code."""

    def __init__(self, source: str, filename: str = "<string>") -> None:
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self._tokens: list[Token] = []
        self._last_scan_token: Token | None = None

    def _current(self) -> str:
        if self.pos >= len(self.source):
            return ""
        return self.source[self.pos]

    def _peek(self, offset: int = 1) -> str:
        p = self.pos + offset
        if p >= len(self.source):
            return ""
        return self.source[p]

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _make_token(self, ttype: TokenType, value: str, line: int, column: int) -> Token:
        return Token(ttype, value, line, column)

    def tokenize(self) -> list[Token]:
        """Tokenize all source and return list of tokens."""
        tokens = []
        self._last_scan_token = None
        for tok in self._scan():
            if tok.type != TokenType.COMMENT:
                tokens.append(tok)
                if tok.type not in (TokenType.NEWLINE, TokenType.COMMENT):
                    self._last_scan_token = tok
        return tokens

    def _is_regex_start(self, last_token: "Token | None") -> bool:
        """Return True if '/' should be scanned as a regex literal rather than division."""
        if last_token is None:
            return True
        # After a value-producing token, '/' is division
        value_tokens = {
            TokenType.NUMBER, TokenType.STRING, TokenType.FSTRING, TokenType.REGEX,
            TokenType.IDENTIFIER, TokenType.BOOL,
            TokenType.RPAREN, TokenType.RBRACKET,
        }
        return last_token.type not in value_tokens

    def _scan(self) -> Iterator[Token]:
        while self.pos < len(self.source):
            line, col = self.line, self.column
            ch = self._current()

            # Skip whitespace (but not newlines — they can act as statement separators)
            if ch in (" ", "\t", "\r"):
                self._advance()
                continue

            # Newline
            if ch == "\n":
                self._advance()
                yield Token(TokenType.NEWLINE, "\\n", line, col)
                continue

            # Single-line comment
            if ch == "/" and self._peek() == "/":
                comment = ""
                while self.pos < len(self.source) and self._current() != "\n":
                    comment += self._advance()
                yield Token(TokenType.COMMENT, comment, line, col)
                continue

            # Multi-line comment
            if ch == "/" and self._peek() == "*":
                self._advance()  # /
                self._advance()  # *
                comment = "/*"
                while self.pos < len(self.source):
                    if self._current() == "*" and self._peek() == "/":
                        comment += self._advance()
                        comment += self._advance()
                        break
                    comment += self._advance()
                yield Token(TokenType.COMMENT, comment, line, col)
                continue

            # String literals (double or single quoted, and f-strings)
            if ch == "f" and self._peek() in ('"', "'"):
                yield from self._scan_fstring(line, col)
                continue
            if ch in ('"', "'"):
                yield from self._scan_string(line, col)
                continue
            # Backtick template literal: `Hello, ${name}!` — treat as f-string with ${...} syntax
            if ch == "`":
                yield from self._scan_backtick(line, col)
                continue

            # Number literals
            if ch.isdigit() or (ch == "." and self._peek().isdigit()):
                yield from self._scan_number(line, col)
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == "_":
                yield from self._scan_identifier(line, col)
                continue

            # Private field identifiers: #name
            if ch == "#" and (self._peek().isalpha() or self._peek() == "_"):
                self._advance()  # consume #
                # Scan the identifier part
                start_col = col
                ident = ""
                while self._current().isalnum() or self._current() == "_":
                    ident += self._current()
                    self._advance()
                yield Token(TokenType.PRIVATE_IDENT, ident, line, start_col)
                continue

            # Multi-char operators
            if ch == "-" and self._peek() == ">":
                self._advance()
                self._advance()
                yield Token(TokenType.ARROW, "->", line, col)
                continue

            if ch == "=" and self._peek() == ">":
                self._advance()
                self._advance()
                yield Token(TokenType.FAT_ARROW, "=>", line, col)
                continue

            if ch == "|" and self._peek() == ">":
                self._advance()
                self._advance()
                yield Token(TokenType.PIPE_ARROW, "|>", line, col)
                continue

            if ch == "=" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.EQ_EQ, "==", line, col)
                continue

            if ch == "!" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.BANG_EQ, "!=", line, col)
                continue

            if ch == "<" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.LT_EQ, "<=", line, col)
                continue

            if ch == ">" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.GT_EQ, ">=", line, col)
                continue

            if ch == "&" and self._peek() == "&":
                self._advance()
                self._advance()
                if self._current() == "=":
                    self._advance()
                    yield Token(TokenType.AND_AND_EQ, "&&=", line, col)
                else:
                    yield Token(TokenType.AND_AND, "&&", line, col)
                continue

            if ch == "|" and self._peek() == "|":
                self._advance()
                self._advance()
                if self._current() == "=":
                    self._advance()
                    yield Token(TokenType.OR_OR_EQ, "||=", line, col)
                else:
                    yield Token(TokenType.OR_OR, "||", line, col)
                continue

            # Compound assignment operators
            if ch == "+" and self._peek() == "+":
                self._advance()
                self._advance()
                yield Token(TokenType.PLUS_PLUS, "++", line, col)
                continue

            if ch == "-" and self._peek() == "-":
                self._advance()
                self._advance()
                yield Token(TokenType.MINUS_MINUS, "--", line, col)
                continue

            if ch == "+" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.PLUS_EQ, "+=", line, col)
                continue

            if ch == "-" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.MINUS_EQ, "-=", line, col)
                continue

            if ch == "%" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.PERCENT_EQ, "%=", line, col)
                continue

            if ch == "*" and self._peek() == "*":
                self._advance()
                self._advance()
                yield Token(TokenType.STAR_STAR, "**", line, col)
                continue

            if ch == "*" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.STAR_EQ, "*=", line, col)
                continue

            if ch == "/" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.SLASH_EQ, "/=", line, col)
                continue

            if ch == "?" and self._peek() == "?":
                self._advance()
                self._advance()
                if self._current() == "=":
                    self._advance()
                    yield Token(TokenType.QUESTION_QUESTION_EQ, "??=", line, col)
                else:
                    yield Token(TokenType.QUESTION_QUESTION, "??", line, col)
                continue

            if ch == "?" and self._peek() == ".":
                self._advance()
                self._advance()
                yield Token(TokenType.QUESTION_DOT, "?.", line, col)
                continue

            if ch == "?":
                self._advance()
                yield Token(TokenType.QUESTION, "?", line, col)
                continue

            # Bitwise operators (multi-char must come before single-char)
            if ch == "&" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.AMP_EQ, "&=", line, col)
                continue

            if ch == "|" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.PIPE_EQ, "|=", line, col)
                continue

            if ch == "^" and self._peek() == "=":
                self._advance()
                self._advance()
                yield Token(TokenType.CARET_EQ, "^=", line, col)
                continue

            if ch == "<" and self._peek() == "<":
                self._advance()
                self._advance()
                if self._current() == "=":
                    self._advance()
                    yield Token(TokenType.LSHIFT_EQ, "<<=", line, col)
                else:
                    yield Token(TokenType.LSHIFT, "<<", line, col)
                continue

            if ch == ">" and self._peek() == ">":
                self._advance()
                self._advance()
                if self._current() == ">":
                    # >>> unsigned right shift
                    self._advance()
                    yield Token(TokenType.URSHIFT, ">>>", line, col)
                elif self._current() == "=":
                    self._advance()
                    yield Token(TokenType.RSHIFT_EQ, ">>=", line, col)
                else:
                    yield Token(TokenType.RSHIFT, ">>", line, col)
                continue

            if ch == "&":
                self._advance()
                yield Token(TokenType.AMP, "&", line, col)
                continue

            if ch == "|":
                self._advance()
                yield Token(TokenType.PIPE, "|", line, col)
                continue

            if ch == "^":
                self._advance()
                yield Token(TokenType.CARET, "^", line, col)
                continue

            if ch == "~":
                self._advance()
                yield Token(TokenType.TILDE, "~", line, col)
                continue

            if ch == "." and self._peek() == "." and self.pos + 2 < len(self.source) and self.source[self.pos + 2] == ".":
                self._advance()
                self._advance()
                self._advance()
                yield Token(TokenType.ELLIPSIS, "...", line, col)
                continue

            if ch == "." and self._peek() == ".":
                self._advance()
                self._advance()
                yield Token(TokenType.DOTDOT, "..", line, col)
                continue

            # Regex literal: /pattern/flags  — only when '/' cannot be division.
            # Heuristic: if the last emitted meaningful token was a value (number,
            # string, ident, ), ]), then '/' is division; otherwise it's a regex.
            if ch == "/" and self._is_regex_start(self._last_scan_token):
                self._advance()  # consume opening /
                pattern = ""
                in_class = False
                while self.pos < len(self.source):
                    rc = self._current()
                    if rc == "\n":
                        raise LexerError("Unterminated regex literal", line, col)
                    if rc == "\\" and self.pos + 1 < len(self.source):
                        pattern += self._advance()  # backslash
                        pattern += self._advance()  # next char
                        continue
                    if rc == "[":
                        in_class = True
                    elif rc == "]":
                        in_class = False
                    elif rc == "/" and not in_class:
                        self._advance()  # consume closing /
                        break
                    pattern += self._advance()
                else:
                    raise LexerError("Unterminated regex literal", line, col)
                # consume optional flags (g, i, m, s, u, y)
                flags = ""
                while self.pos < len(self.source) and self._current() in "gimsuy":
                    flags += self._advance()
                regex_value = f"{pattern}\x00{flags}"  # embed flags after NUL separator
                self._last_scan_token = Token(TokenType.REGEX, regex_value, line, col)
                yield self._last_scan_token
                continue

            # Single-char operators and delimiters
            single = {
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "%": TokenType.PERCENT,
                "<": TokenType.LT,
                ">": TokenType.GT,
                "!": TokenType.BANG,
                "=": TokenType.EQ,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                ",": TokenType.COMMA,
                ".": TokenType.DOT,
                ":": TokenType.COLON,
                ";": TokenType.SEMICOLON,
            }
            if ch in single:
                self._advance()
                yield Token(single[ch], ch, line, col)
                continue

            raise LexerError(f"Unexpected character: {ch!r}", line, col)

        yield Token(TokenType.EOF, "", self.line, self.column)

    def _scan_string(self, line: int, col: int) -> Iterator[Token]:
        quote = self._advance()
        # Check for triple-quoted string
        if self.pos < len(self.source) and self._current() == quote:
            self._advance()  # consume second quote
            if self.pos < len(self.source) and self._current() == quote:
                self._advance()  # consume third quote — triple-quoted string
                yield from self._scan_triple_string(quote, line, col)
                return
            else:
                # Empty string ""
                yield Token(TokenType.STRING, "", line, col)
                return
        value = ""
        while self.pos < len(self.source):
            ch = self._current()
            if ch == "\\":
                self._advance()
                esc = self._advance()
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    "\\": "\\",
                    '"': '"',
                    "'": "'",
                    "0": "\0",
                }
                value += escape_map.get(esc, esc)
            elif ch == quote:
                self._advance()
                break
            elif ch == "\n":
                raise LexerError("Unterminated string literal", line, col)
            else:
                value += self._advance()
        else:
            raise LexerError("Unterminated string literal", line, col)
        yield Token(TokenType.STRING, value, line, col)

    def _scan_triple_string(self, quote: str, line: int, col: int) -> Iterator[Token]:
        """Scan a triple-quoted string that may span multiple lines."""
        value = ""
        while self.pos < len(self.source):
            ch = self._current()
            if ch == quote and self.pos + 2 < len(self.source) and self.source[self.pos + 1] == quote and self.source[self.pos + 2] == quote:
                self._advance()
                self._advance()
                self._advance()
                yield Token(TokenType.STRING, value, line, col)
                return
            if ch == "\\":
                self._advance()
                esc = self._advance()
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                              '"': '"', "'": "'", "0": "\0"}
                value += escape_map.get(esc, esc)
            else:
                if ch == "\n":
                    self.line += 1
                    self.column = 1
                value += self._advance()
        raise LexerError("Unterminated triple-quoted string", line, col)

    def _scan_fstring(self, line: int, col: int) -> Iterator[Token]:
        """Scan an f-string: f"Hello {name}!" → FSTRING token with raw value."""
        self._advance()  # consume 'f'
        quote = self._advance()  # consume opening quote
        value = ""
        while self.pos < len(self.source):
            ch = self._current()
            if ch == "\\":
                self._advance()
                esc = self._advance()
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                              '"': '"', "'": "'", "0": "\0"}
                value += escape_map.get(esc, esc)
            elif ch == quote:
                self._advance()
                break
            elif ch == "\n":
                raise LexerError("Unterminated f-string", line, col)
            else:
                value += self._advance()
        else:
            raise LexerError("Unterminated f-string", line, col)
        # Yield as FSTRING with raw content including {expr} markers
        yield Token(TokenType.FSTRING, value, line, col)

    def _scan_backtick(self, line: int, col: int) -> Iterator[Token]:
        """Scan a backtick template literal: `Hello, ${name}!` → FSTRING token.

        Converts ${...} interpolation to {...} (matching f-string format).
        """
        self._advance()  # consume opening `
        value = ""
        while self.pos < len(self.source):
            ch = self._current()
            if ch == "\\":
                self._advance()
                esc = self._advance()
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                              "`": "`", "$": "$"}
                value += escape_map.get(esc, esc)
            elif ch == "`":
                self._advance()
                break
            elif ch == "$" and self._peek() == "{":
                # ${expr} → {expr}
                self._advance()  # skip $
                value += self._advance()  # include {
            else:
                value += self._advance()
        else:
            raise LexerError("Unterminated template literal", line, col)
        yield Token(TokenType.FSTRING, value, line, col)

    def _scan_number(self, line: int, col: int) -> Iterator[Token]:
        # Check for 0x, 0b, 0o prefix literals
        if self._current() == "0" and self.pos + 1 < len(self.source):
            next_ch = self.source[self.pos + 1].lower()
            if next_ch == "x":
                self._advance()  # consume '0'
                self._advance()  # consume 'x'
                hex_val = ""
                while self.pos < len(self.source) and (self._current() in "0123456789abcdefABCDEF_"):
                    if self._current() != "_":
                        hex_val += self._advance()
                    else:
                        self._advance()
                yield Token(TokenType.NUMBER, str(int(hex_val or "0", 16)), line, col)
                return
            if next_ch == "b":
                self._advance()  # consume '0'
                self._advance()  # consume 'b'
                bin_val = ""
                while self.pos < len(self.source) and self._current() in "01_":
                    if self._current() != "_":
                        bin_val += self._advance()
                    else:
                        self._advance()
                yield Token(TokenType.NUMBER, str(int(bin_val or "0", 2)), line, col)
                return
            if next_ch == "o":
                self._advance()  # consume '0'
                self._advance()  # consume 'o'
                oct_val = ""
                while self.pos < len(self.source) and self._current() in "01234567_":
                    if self._current() != "_":
                        oct_val += self._advance()
                    else:
                        self._advance()
                yield Token(TokenType.NUMBER, str(int(oct_val or "0", 8)), line, col)
                return
        value = ""
        has_dot = False
        while self.pos < len(self.source):
            ch = self._current()
            if ch.isdigit():
                value += self._advance()
            elif ch == "." and not has_dot and self._peek().isdigit():
                has_dot = True
                value += self._advance()
            elif ch == "_":
                # Allow underscores in numbers for readability: 1_000_000
                self._advance()
            else:
                break
        yield Token(TokenType.NUMBER, value, line, col)

    def _scan_identifier(self, line: int, col: int) -> Iterator[Token]:
        value = ""
        while self.pos < len(self.source):
            ch = self._current()
            if ch.isalnum() or ch in ("_",):
                value += self._advance()
            else:
                break
        # Check if it's a keyword
        ttype = KEYWORDS.get(value, TokenType.IDENTIFIER)
        # Special case: fn* is a generator function keyword
        if ttype == TokenType.FN and self.pos < len(self.source) and self._current() == "*":
            self._advance()  # consume '*'
            yield Token(TokenType.FN_STAR, "fn*", line, col)
        else:
            yield Token(ttype, value, line, col)
