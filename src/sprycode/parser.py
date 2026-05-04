"""
SpryCode Parser

Recursive descent parser that builds an AST from a token stream.
"""

from __future__ import annotations

from typing import Any, Sequence

from .ast_nodes import (
    AdapterDeclaration,
    AllowStatement,
    AppDeclaration,
    ArrayLiteral,
    AssertStatement,
    Assignment,
    AtomicStatement,
    BinaryExpression,
    Block,
    BoolLiteral,
    BreakStatement,
    CallExpression,
    ClassDeclaration,
    ClassExpression,
    CompensateStatement,
    CompoundAssignment,
    CompoundMemberAssignment,
    CompressStatement,
    ConnectorDeclaration,
    ContinueStatement,
    CopyStatement,
    CreateStatement,
    CreditStatement,
    DebitStatement,
    DeleteStatement,
    DenyStatement,
    DoWhileStatement,
    EnumDeclaration,
    ExportStatement,
    ExpectStatement,
    ExtractStatement,
    ForStatement,
    ForCStyleStatement,
    FraudCheckStatement,
    FStringExpression,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    ImportStatement,
    IndexAssignment,
    InExpression,
    IndexExpression,
    InstanceofExpression,
    InterfaceDeclaration,
    LabeledStatement,
    LambdaExpression,
    LetDeclaration,
    ListDestructure,
    ListDestructureAssignment,
    ListComprehension,
    DictComprehension,
    LogStatement,
    MatchArm,
    MatchStatement,
    MemberAssignment,
    MemberExpression,
    MoveStatement,
    MultiParamLambda,
    Node,
    NullCoalesceExpression,
    NullLiteral,
    NumberLiteral,
    ObjectDestructure,
    ObjectLiteral,
    OptionalMemberExpression,
    OptionalIndexExpression,
    ParseStatement,
    PipelineExpression,
    PostfixExpression,
    PrivateDataDeclaration,
    Program,
    ReadStatement,
    RedactStatement,
    RegexLiteral,
    RepeatUntilStatement,
    ResultLiteral,
    ReturnStatement,
    ScheduleStatement,
    SecretLiteral,
    SensitiveDataDeclaration,
    SleepStatement,
    SpawnStatement,
    SpreadElement,
    StopStatement,
    StreamStatement,
    StringLiteral,
    StructDeclaration,
    SwitchCase,
    SwitchStatement,
    SyncStatement,
    AnonymousFunctionExpression,
    TaskDeclaration,
    TernaryExpression,
    TestBlock,
    ThrowStatement,
    TransactionStatement,
    TryCatchStatement,
    TypeCastExpression,
    TypeofExpression,
    UnaryExpression,
    UseStatement,
    ValidateStatement,
    VarDeclaration,
    WatchStatement,
    WebSocketStatement,
    WhileStatement,
    WithStatement,
    WriteStatement,
    YieldStatement,
    SuperExpression,
    GetterDeclaration,
    SetterDeclaration,
    TaggedTemplateExpression,
    AwaitExpression,
    OptionalCallExpression,
    ComputedMethodDeclaration,
    SequenceExpression,
    DeclarationList,
)
from .lexer import Token, TokenType


class ParseError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        super().__init__(
            f"Parse error at line {token.line}, column {token.column}: {message} (got {token.type.name} {token.value!r})"
        )
        self.token = token


class Parser:
    """Builds an AST from a list of tokens produced by the Lexer."""

    def __init__(self, tokens: list[Token]) -> None:
        # Filter out newlines that are purely whitespace (we handle them implicitly)
        self.tokens = [t for t in tokens if t.type != TokenType.NEWLINE]
        self.pos = 0

    # ------------------------------------------------------------------
    # Token navigation helpers
    # ------------------------------------------------------------------

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def _peek(self, offset: int = 1) -> Token:
        p = self.pos + offset
        if p < len(self.tokens):
            return self.tokens[p]
        return self.tokens[-1]

    def _advance(self) -> Token:
        tok = self._current()
        self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._current().type in types

    def _match(self, *types: TokenType) -> Token | None:
        if self._check(*types):
            return self._advance()
        return None

    def _expect(self, *types: TokenType) -> Token:
        if self._check(*types):
            return self._advance()
        raise ParseError(
            f"Expected one of {[t.name for t in types]}",
            self._current(),
        )

    def _at_end(self) -> bool:
        return self._current().type == TokenType.EOF

    # Tokens that may be used as variable/parameter names even though
    # they are keywords in other contexts.
    _IDENTIFIER_LIKE = frozenset({
        TokenType.IDENTIFIER,
        TokenType.UNDERSCORE,    # _ used as ignored parameter name
        TokenType.FILE_TYPE,     # "file", "File"
        TokenType.FOLDER_TYPE,   # "folder", "Folder"
        TokenType.DATA,          # "data"
        TokenType.INFO,
        TokenType.WARN,
        TokenType.ERROR,
        TokenType.MODE,
        TokenType.LAST,
        TokenType.MINIMAL,
        TokenType.RESULT_TYPE,   # "Result"
        TokenType.OK,            # "ok"
        TokenType.FAIL,
        TokenType.RESULT,        # "result"
        TokenType.TEST,          # "test" usable as identifier in some contexts
        TokenType.EXISTS,
        # Built-in function names that are also keywords
        TokenType.ENCODE,        # encode(...)
        TokenType.DECODE,        # decode(...)
        TokenType.HASH,          # hash(...)
        TokenType.CHECKSUM,      # checksum(...)
        TokenType.ENCRYPT,       # encrypt(...)
        TokenType.DECRYPT,       # decrypt(...)
        TokenType.HTTP,          # http.get(...) / http.post(...)
        TokenType.COMPRESS,      # compress(...) used as expression
        TokenType.EXTRACT,       # extract(...) used as expression
        TokenType.CHECK,         # check(...)
        TokenType.VERIFY,        # verify(...)
        TokenType.OUTPUT,        # output(...)
        TokenType.TRANSLATE,     # translate(...)
        # Type names used as global namespace identifiers (e.g. Number.isInteger, Array.isArray)
        TokenType.NUMBER_TYPE,   # "Number"
        TokenType.TEXT,          # "Text"
        TokenType.BOOL_TYPE,     # "Bool"
        TokenType.INT_TYPE,      # "Int"
        TokenType.FLOAT_TYPE,    # "Float"
        TokenType.DATE_TYPE,     # "Date"
        TokenType.TIME_TYPE,     # "Time"
        TokenType.DATETIME_TYPE, # "DateTime"
        TokenType.MAP_TYPE,      # "Map" — used as global namespace identifier
        TokenType.MONEY_TYPE,    # "Money" — used as class/identifier name
        TokenType.LOG,           # "log" — usable as variable/function/parameter name
        # SpryCode-specific keywords commonly used as field/property names in class bodies
        # and object literals (e.g. `static timeout = 5000`, `{ retry: 3 }`)
        TokenType.TIMEOUT,       # "timeout"
        TokenType.SLEEP,         # "sleep"
        TokenType.RETRY,         # "retry"
        TokenType.SCHEDULE,      # "schedule"
        TokenType.DAILY,         # "daily"
        TokenType.FRAUD,         # "fraud"
        TokenType.REASON,        # "reason"
        TokenType.CASE,          # "case"
        TokenType.SCOPE,         # "scope"
        TokenType.WEBSOCKET,     # "websocket"
        # Common SpryCode keywords also used as method names in class bodies
        # and object literals (e.g. class { create() {}, delete() {}, from() {} })
        TokenType.CREATE,        # "create"
        TokenType.DELETE,        # "delete"
        TokenType.FROM,          # "from"
        TokenType.DEFAULT,       # "default"
        TokenType.TO,            # "to" — commonly used as variable name in ranges
        TokenType.STOP,          # "stop" — commonly used as variable name
    })

    def _expect_ident(self) -> Token:
        """Expect any token that may serve as an identifier (variable/parameter name)."""
        tok = self._current()
        if tok.type in self._IDENTIFIER_LIKE:
            return self._advance()
        raise ParseError("Expected identifier", tok)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self) -> Program:
        body: list[Node] = []
        while not self._at_end():
            # Skip statement-separator semicolons
            while self._check(TokenType.SEMICOLON):
                self._advance()
            if self._at_end():
                break
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        tok = self.tokens[0] if self.tokens else Token(TokenType.EOF, "", 1, 1)
        return Program(body=body, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Statement dispatch
    # ------------------------------------------------------------------

    def _parse_statement(self) -> Node | None:
        tok = self._current()

        if tok.type == TokenType.APP:
            return self._parse_app()
        if tok.type == TokenType.LET:
            return self._parse_let()
        if tok.type == TokenType.CONST:
            return self._parse_let()  # const is an immutable binding, same as let
        if tok.type == TokenType.VAR:
            return self._parse_var()
        if tok.type == TokenType.FN:
            return self._parse_fn()
        if tok.type == TokenType.FN_STAR:
            return self._parse_fn(is_generator=True)
        if tok.type == TokenType.YIELD:
            return self._parse_yield()
        if tok.type == TokenType.EXPORT:
            return self._parse_export()
        if tok.type == TokenType.ASYNC:
            # async fn — parse function and mark it as async
            self._advance()
            if self._check(TokenType.FN):
                return self._parse_fn(is_async=True)
            if self._check(TokenType.FN_STAR):
                return self._parse_fn(is_generator=True, is_async=True)
            # async block or expression — parse remainder as expression stmt
            return self._parse_expr_or_assignment()
        if tok.type == TokenType.TASK:
            return self._parse_task()
        if tok.type == TokenType.ALLOW:
            return self._parse_allow()
        if tok.type == TokenType.DENY:
            return self._parse_deny()
        if tok.type == TokenType.IF:
            return self._parse_if()
        if tok.type == TokenType.TRY:
            return self._parse_try()
        if tok.type == TokenType.ATOMIC:
            return self._parse_atomic()
        if tok.type == TokenType.TRANSACTION:
            return self._parse_transaction()
        if tok.type == TokenType.LOG:
            # Only parse as a log statement when followed by a message-producing token.
            # When followed by `.`, `(`, operators, etc. treat `log` as an identifier.
            _LOG_MSG_START = {
                TokenType.STRING, TokenType.FSTRING, TokenType.NUMBER,
                TokenType.IDENTIFIER, TokenType.LBRACKET, TokenType.LBRACE,
                TokenType.BOOL,
                TokenType.INFO, TokenType.WARN, TokenType.ERROR,
                TokenType.MINUS, TokenType.NOT,
            }
            if self._peek().type in _LOG_MSG_START:
                return self._parse_log()
        if tok.type == TokenType.MOVE:
            return self._parse_move()
        if tok.type == TokenType.COPY:
            return self._parse_copy()
        if tok.type == TokenType.READ:
            return self._parse_read()
        if tok.type == TokenType.WRITE:
            return self._parse_write()
        if tok.type == TokenType.DELETE:
            return self._parse_delete()
        if tok.type == TokenType.STREAM:
            return self._parse_stream()
        if tok.type == TokenType.SYNC:
            return self._parse_sync()
        if tok.type == TokenType.WATCH:
            return self._parse_watch()
        if tok.type == TokenType.RETURN:
            return self._parse_return()
        if tok.type == TokenType.STOP:
            self._advance()
            return StopStatement(line=tok.line, column=tok.column)
        if tok.type == TokenType.PRIVATE:
            return self._parse_private_data()
        if tok.type == TokenType.SENSITIVE:
            return self._parse_sensitive_data()
        if tok.type == TokenType.USE:
            return self._parse_use()
        if tok.type == TokenType.ADAPTER:
            return self._parse_adapter()
        if tok.type == TokenType.CONNECTOR:
            return self._parse_connector()
        if tok.type == TokenType.FRAUD:
            return self._parse_fraud_check()
        if tok.type == TokenType.VALIDATE:
            return self._parse_validate()
        if tok.type == TokenType.REDACT:
            return self._parse_redact()
        if tok.type == TokenType.PARSE:
            return self._parse_parse_stmt()
        if tok.type == TokenType.COMPENSATE:
            return self._parse_compensate()
        if tok.type == TokenType.FOR:
            return self._parse_for()
        if tok.type == TokenType.WHILE:
            return self._parse_while()
        if tok.type == TokenType.BREAK:
            self._advance()
            # Optional label: break outer  (only if label is on the same line)
            label = None
            if (self._check(TokenType.IDENTIFIER) and not self._at_end()
                    and self._current().line == tok.line):
                label = self._advance().value
            return BreakStatement(label=label, line=tok.line, column=tok.column)
        if tok.type == TokenType.CONTINUE:
            self._advance()
            # Optional label: continue outer  (only if label is on the same line)
            label = None
            if (self._check(TokenType.IDENTIFIER) and not self._at_end()
                    and self._current().line == tok.line):
                label = self._advance().value
            return ContinueStatement(label=label, line=tok.line, column=tok.column)
        if tok.type == TokenType.CREATE:
            return self._parse_create()
        if tok.type == TokenType.COMPRESS:
            return self._parse_compress()
        if tok.type == TokenType.EXTRACT:
            return self._parse_extract()
        if tok.type == TokenType.SLEEP:
            return self._parse_sleep()
        if tok.type == TokenType.SCHEDULE:
            return self._parse_schedule()
        if tok.type == TokenType.TEST:
            return self._parse_test_block()
        if tok.type == TokenType.EXPECT:
            return self._parse_expect()
        if tok.type == TokenType.MATCH:
            return self._parse_match()
        if tok.type == TokenType.REPEAT:
            return self._parse_repeat_until()
        if tok.type == TokenType.ASSERT:
            return self._parse_assert()
        if tok.type == TokenType.IMPORT:
            return self._parse_import()
        if tok.type == TokenType.THROW:
            return self._parse_throw()
        if tok.type == TokenType.ENUM:
            return self._parse_enum()
        if tok.type == TokenType.CLASS:
            return self._parse_class()
        if tok.type == TokenType.STRUCT:
            return self._parse_struct()
        if tok.type == TokenType.INTERFACE:
            return self._parse_interface()
        if tok.type == TokenType.SWITCH:
            return self._parse_switch()
        if tok.type == TokenType.DO:
            return self._parse_do_while()
        if tok.type == TokenType.SPAWN:
            return self._parse_spawn()
        if tok.type == TokenType.WEBSOCKET:
            return self._parse_websocket()
        if tok.type == TokenType.WITH:
            return self._parse_with()
        if tok.type == TokenType.DEBIT:
            return self._parse_debit()
        if tok.type == TokenType.CREDIT:
            return self._parse_credit()

        # Labeled statement: label: for/while/do {...}
        # Detect: IDENTIFIER followed immediately by COLON
        if tok.type == TokenType.IDENTIFIER and self._peek().type == TokenType.COLON:
            label_tok = self._advance()  # consume identifier
            self._advance()              # consume ':'
            body_stmt = self._parse_statement()
            return LabeledStatement(label=label_tok.value, body=body_stmt,
                                    line=label_tok.line, column=label_tok.column)

        # Array destructuring assignment at statement start: [a, b, c] = expr
        # Must be checked BEFORE expression parsing to avoid [a, b] being consumed
        # as a subscript on the previous statement's trailing value (newlines are stripped).
        if tok.type == TokenType.LBRACKET:
            saved_pos = self.pos
            try:
                self._advance()  # consume '['
                names: list[str] = []
                rest_name_s: str | None = None
                ok = True
                while not self._check(TokenType.RBRACKET) and not self._at_end():
                    if self._check(TokenType.ELLIPSIS):
                        self._advance()
                        if self._current().type in self._IDENTIFIER_LIKE:
                            rest_name_s = self._advance().value
                        else:
                            ok = False
                        break
                    if self._current().type in self._IDENTIFIER_LIKE:
                        names.append(self._advance().value)
                    else:
                        ok = False
                        break
                    if not self._match(TokenType.COMMA):
                        break
                if ok and self._check(TokenType.RBRACKET):
                    self._advance()  # consume ']'
                    if self._check(TokenType.EQ):
                        self._advance()  # consume '='
                        rhs = self._parse_expression()
                        return ListDestructureAssignment(
                            names=names, value=rhs, rest_name=rest_name_s,
                            line=tok.line, column=tok.column,
                        )
            except Exception:
                pass
            self.pos = saved_pos

        # Standalone block statement: { stmt; stmt; ... }
        # Disambiguate from object literals by peeking at the first token inside.
        # Treat as block when the first inner token is:
        #   - a statement keyword (let, var, fn, if, for, while, return, etc.)
        #   - an identifier/keyword NOT followed by ':' (assignment, not key:value)
        #   - empty (RBRACE) — an empty block
        if tok.type == TokenType.LBRACE:
            _BLOCK_KEYWORDS = {
                TokenType.LET, TokenType.CONST, TokenType.VAR,
                TokenType.FN, TokenType.FN_STAR, TokenType.IF, TokenType.FOR,
                TokenType.WHILE, TokenType.DO, TokenType.RETURN, TokenType.THROW,
                TokenType.TRY, TokenType.BREAK, TokenType.CONTINUE,
                TokenType.CLASS, TokenType.SWITCH, TokenType.ASYNC,
            }
            peek1 = self._peek(1)
            peek2 = self._peek(2)
            _is_block = (
                peek1.type == TokenType.RBRACE                          # empty {}
                or peek1.type in _BLOCK_KEYWORDS                        # starts with statement kw
                or (peek1.type in self._IDENTIFIER_LIKE                  # ident not followed by ':'
                    and peek2.type != TokenType.COLON)
            )
            if _is_block:
                return self._parse_block()

        # Expression statement or assignment
        return self._parse_expr_or_assignment()

    def _parse_block(self) -> Block:
        tok = self._expect(TokenType.LBRACE)
        body: list[Node] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            # Skip statement-separator semicolons inside blocks
            while self._check(TokenType.SEMICOLON):
                self._advance()
            if self._check(TokenType.RBRACE) or self._at_end():
                break
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        self._expect(TokenType.RBRACE)
        return Block(body=body, line=tok.line, column=tok.column)

    def _parse_block_or_stmt(self) -> Block:
        """Parse either a brace-enclosed block or a single statement.

        Supports JS-style single-statement if/else/while bodies without braces:
          if (cond) return x
          if (cond) throw new Error('msg')
          while (cond) x++
        Always returns a Block (wrapping a single statement in a one-element block).
        """
        if self._check(TokenType.LBRACE):
            return self._parse_block()
        stmt = self._parse_statement()
        tok = self._current()
        return Block(body=[stmt] if stmt is not None else [],
                     line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Top-level declarations
    # ------------------------------------------------------------------

    def _parse_app(self) -> AppDeclaration:
        tok = self._expect(TokenType.APP)
        name_tok = self._expect(TokenType.IDENTIFIER)
        version = ""
        if self._match(TokenType.IDENTIFIER):  # "version"
            version = self._expect(TokenType.STRING).value
        return AppDeclaration(name=name_tok.value, version=version, line=tok.line, column=tok.column)

    def _parse_let(self) -> Node:
        is_const = self._check(TokenType.CONST)
        if is_const:
            tok = self._advance()  # consume 'const' (JS-compatible immutable binding)
        else:
            tok = self._expect(TokenType.LET)
        # mutable=True for let (reassignable), mutable=False for const (immutable)
        mutable = not is_const
        # Check for list destructuring: let [a, b, c] = expr
        if self._check(TokenType.LBRACKET):
            first: Node = self._parse_list_destructure(tok, mutable=mutable)
        # Check for object destructuring: let {a, b} = expr
        elif self._check(TokenType.LBRACE):
            first = self._parse_object_destructure(tok, mutable=mutable)
        else:
            name_tok = self._expect_ident()
            type_annotation = None
            if self._match(TokenType.COLON):
                type_annotation = self._parse_type_name()
            value = None
            if self._match(TokenType.EQ):
                value = self._parse_expression()
            first = LetDeclaration(
                name=name_tok.value,
                type_annotation=type_annotation,
                value=value,
                line=tok.line,
                column=tok.column,
                is_const=is_const,
            )
        # Multiple declarations: let a = 1, b = 2, c = 3
        if self._check(TokenType.COMMA):
            decls: list[Node] = [first]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.LBRACKET):
                    decls.append(self._parse_list_destructure(tok, mutable=mutable))
                elif self._check(TokenType.LBRACE):
                    decls.append(self._parse_object_destructure(tok, mutable=mutable))
                else:
                    n_tok = self._expect_ident()
                    t_ann = None
                    if self._match(TokenType.COLON):
                        t_ann = self._parse_type_name()
                    v_node = None
                    if self._match(TokenType.EQ):
                        v_node = self._parse_expression()
                    decls.append(LetDeclaration(
                        name=n_tok.value, type_annotation=t_ann, value=v_node,
                        line=n_tok.line, column=n_tok.column, is_const=is_const,
                    ))
            return DeclarationList(body=decls, line=tok.line, column=tok.column)
        return first

    def _parse_var(self) -> Node:
        tok = self._expect(TokenType.VAR)
        # Check for list destructuring: var [a, b, c] = expr
        if self._check(TokenType.LBRACKET):
            first_v: Node = self._parse_list_destructure(tok, mutable=True)
        # Check for object destructuring: var {a, b} = expr
        elif self._check(TokenType.LBRACE):
            first_v = self._parse_object_destructure(tok, mutable=True)
        else:
            # Private field: var #name = value
            if self._check(TokenType.PRIVATE_IDENT):
                priv_tok = self._advance()
                name = f"__private__{priv_tok.value}"
            else:
                name_tok = self._expect_ident()
                name = name_tok.value
            type_annotation = None
            if self._match(TokenType.COLON):
                type_annotation = self._parse_type_name()
            value = None
            if self._match(TokenType.EQ):
                value = self._parse_expression()
            first_v = VarDeclaration(
                name=name,
                type_annotation=type_annotation,
                value=value,
                line=tok.line,
                column=tok.column,
            )
        # Multiple declarations: var a = 1, b = 2, c = 3
        if self._check(TokenType.COMMA):
            decls_v: list[Node] = [first_v]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.LBRACKET):
                    decls_v.append(self._parse_list_destructure(tok, mutable=True))
                elif self._check(TokenType.LBRACE):
                    decls_v.append(self._parse_object_destructure(tok, mutable=True))
                else:
                    n_tok2 = self._expect_ident()
                    t_ann2 = None
                    if self._match(TokenType.COLON):
                        t_ann2 = self._parse_type_name()
                    v_node2 = None
                    if self._match(TokenType.EQ):
                        v_node2 = self._parse_expression()
                    decls_v.append(VarDeclaration(
                        name=n_tok2.value, type_annotation=t_ann2, value=v_node2,
                        line=n_tok2.line, column=n_tok2.column,
                    ))
            return DeclarationList(body=decls_v, line=tok.line, column=tok.column)
        return first_v

    def _parse_fn(self, is_generator: bool = False, is_async: bool = False) -> FunctionDeclaration:
        if is_generator:
            tok = self._expect(TokenType.FN_STAR)
        else:
            tok = self._expect(TokenType.FN)
        name_tok = self._expect_ident()
        self._expect(TokenType.LPAREN)
        params: list[tuple[str, str | None]] = []
        defaults: dict[str, Node] = {}
        rest_param: str | None = None
        while not self._check(TokenType.RPAREN) and not self._at_end():
            # Rest parameter: ...name
            if self._check(TokenType.ELLIPSIS):
                self._advance()
                rest_tok = self._expect_ident()
                rest_param = rest_tok.value
                break  # rest must be last
            # Dict destructuring param: {a, b}
            if self._check(TokenType.LBRACE):
                # Accept as a synthetic param name "__destruct__" and store original names
                param_names, param_defaults = self._parse_dict_destruct_param()
                params.append(("__destruct__:" + ",".join(param_names), None))
                for _fname, _dflt in param_defaults.items():
                    defaults[f"__destruct_default__{_fname}"] = _dflt
                if not self._match(TokenType.COMMA):
                    break
                continue
            # Array destructuring param: [a, b, ...rest]
            if self._check(TokenType.LBRACKET):
                self._advance()  # consume '['
                arr_names: list[str] = []
                arr_rest: str | None = None
                while not self._check(TokenType.RBRACKET) and not self._at_end():
                    if self._check(TokenType.ELLIPSIS):
                        self._advance()
                        arr_rest = self._expect_ident().value
                        break
                    arr_names.append(self._expect_ident().value)
                    if not self._match(TokenType.COMMA):
                        break
                self._expect(TokenType.RBRACKET)
                synth = "__array_destruct__:" + ",".join(arr_names)
                if arr_rest:
                    synth += "..." + arr_rest
                params.append((synth, None))
                if not self._match(TokenType.COMMA):
                    break
                continue
            pname = self._expect_ident()
            ptype = None
            if self._match(TokenType.COLON):
                ptype = self._parse_type_name()
            default_expr = None
            if self._match(TokenType.EQ):
                default_expr = self._parse_null_coalesce()
            params.append((pname.value, ptype))
            if default_expr is not None:
                defaults[pname.value] = default_expr
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RPAREN)

        return_type = None
        if self._match(TokenType.ARROW):
            return_type = self._parse_type_name()

        # Short form: => expression
        if self._check(TokenType.FAT_ARROW):
            self._advance()
            expr = self._parse_expression()
            body = Block(body=[ReturnStatement(value=expr, line=tok.line, column=tok.column)])
            return FunctionDeclaration(
                name=name_tok.value,
                params=params,
                return_type=return_type,
                body=body,
                short_form=True,
                defaults=defaults,
                rest_param=rest_param,
                is_generator=is_generator,
                is_async=is_async,
                line=tok.line,
                column=tok.column,
            )

        body = self._parse_block()
        return FunctionDeclaration(
            name=name_tok.value,
            params=params,
            return_type=return_type,
            body=body,
            defaults=defaults,
            rest_param=rest_param,
            is_generator=is_generator,
            is_async=is_async,
            line=tok.line,
            column=tok.column,
        )

    def _parse_yield(self) -> YieldStatement:
        tok = self._expect(TokenType.YIELD)
        delegate = False
        value: Node | None = None
        if self._check(TokenType.STAR):
            self._advance()
            delegate = True
        if not self._check(TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF, TokenType.SEMICOLON):
            value = self._parse_expression()
        return YieldStatement(value=value, line=tok.line, column=tok.column, delegate=delegate)

    def _parse_export(self) -> ExportStatement:
        tok = self._expect(TokenType.EXPORT)
        # export fn, export let, export var, export class, export enum, etc.
        inner = self._parse_statement()
        return ExportStatement(declaration=inner, line=tok.line, column=tok.column)

    def _parse_dict_destruct_param(self) -> tuple[list[str], dict[str, "Node"]]:
        """Parse {a, b, c} or {a: alias, key = default} destructuring pattern in function params.

        Returns a tuple of:
        - names: list of field specs, each either ``"name"`` or ``"key|alias"``
        - defaults: dict mapping local name → default AST node
        """
        from .ast_nodes import Node as _Node  # noqa: F401 (avoid circular at module top)
        self._expect(TokenType.LBRACE)
        names: list[str] = []
        defaults: dict[str, Any] = {}
        while not self._check(TokenType.RBRACE) and not self._at_end():
            name_tok = self._expect_ident()
            key = name_tok.value
            if self._match(TokenType.COLON):
                # rename: {key: localName} — optionally followed by = default
                alias_tok = self._expect_ident()
                local = alias_tok.value
                names.append(key + "|" + local)
                if self._match(TokenType.EQ):
                    defaults[local] = self._parse_expression()
            elif self._match(TokenType.EQ):
                # default: {key = defaultExpr}
                defaults[key] = self._parse_expression()
                names.append(key)
            else:
                names.append(key)
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE)
        return names, defaults

    def _parse_task(self) -> TaskDeclaration:
        tok = self._expect(TokenType.TASK)
        name_tok = self._expect(TokenType.IDENTIFIER)
        body = self._parse_block()
        return TaskDeclaration(name=name_tok.value, body=body, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Permission / Privacy
    # ------------------------------------------------------------------

    def _parse_allow(self) -> AllowStatement:
        tok = self._expect(TokenType.ALLOW)
        perm = self._parse_permission_path()
        argument = None
        if self._check(TokenType.STRING):
            argument = self._advance().value
        return AllowStatement(permission=perm, argument=argument, line=tok.line, column=tok.column)

    def _parse_deny(self) -> DenyStatement:
        tok = self._expect(TokenType.DENY)
        perm = self._parse_permission_path()
        argument = None
        if self._check(TokenType.STRING):
            argument = self._advance().value
        return DenyStatement(permission=perm, argument=argument, line=tok.line, column=tok.column)

    def _parse_permission_path(self) -> str:
        """Parse a permission path like filesystem.read or network.all.

        Accepts any token type as path components (including keywords like
        'secret', 'read', 'write', 'all', etc.).
        """
        tok = self._current()
        if tok.type == TokenType.EOF:
            raise ParseError("Expected permission path", tok)
        parts = [self._advance().value]
        while self._check(TokenType.DOT):
            self._advance()
            if self._at_end():
                break
            parts.append(self._advance().value)
        return ".".join(parts)

    def _parse_private_data(self) -> PrivateDataDeclaration:
        tok = self._expect(TokenType.PRIVATE)
        self._expect(TokenType.DATA)
        name_tok = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.COLON)
        type_name = self._parse_type_name()
        return PrivateDataDeclaration(
            name=name_tok.value, type_annotation=type_name, line=tok.line, column=tok.column
        )

    def _parse_sensitive_data(self) -> SensitiveDataDeclaration:
        tok = self._expect(TokenType.SENSITIVE)
        self._expect(TokenType.DATA)
        name_tok = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.COLON)
        type_name = self._parse_type_name()
        return SensitiveDataDeclaration(
            name=name_tok.value, type_annotation=type_name, line=tok.line, column=tok.column
        )

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def _parse_if(self) -> IfStatement:
        tok = self._expect(TokenType.IF)
        condition = self._parse_expression()
        then_block = self._parse_block_or_stmt()
        # Consume optional trailing semicolons before `else` so that
        # `if (c) return x; else return y` is parsed correctly.
        while self._check(TokenType.SEMICOLON):
            self._advance()
        else_block = None
        if self._match(TokenType.ELSE):
            if self._check(TokenType.IF):
                # else if — wrap in a block
                nested = self._parse_if()
                else_block = Block(body=[nested], line=nested.line, column=nested.column)
            else:
                else_block = self._parse_block_or_stmt()
        return IfStatement(
            condition=condition,
            then_block=then_block,
            else_block=else_block,
            line=tok.line,
            column=tok.column,
        )

    def _parse_try(self) -> TryCatchStatement:
        tok = self._expect(TokenType.TRY)
        body = self._parse_block()
        # catch is optional if finally is present
        err_name = ""
        handler: Block | None = None
        if self._check(TokenType.CATCH):
            self._advance()
            # Support:
            #   catch e { ... }         — bare identifier
            #   catch (e) { ... }       — parenthesised identifier
            #   catch { ... }           — no binding (optional catch binding, ES2019)
            has_paren = self._match(TokenType.LPAREN)
            if has_paren:
                if self._check(TokenType.RPAREN):
                    # catch () { ... } — empty parens, no binding
                    self._advance()
                    err_name = ""
                else:
                    err_name = self._expect_ident().value
                    self._expect(TokenType.RPAREN)
            elif not self._check(TokenType.LBRACE):
                # bare identifier: catch e { ... }
                err_name = self._expect_ident().value
            # else: catch { ... } — no binding at all
            handler = self._parse_block()
        # optional finally block
        finally_block: Block | None = None
        if self._check(TokenType.FINALLY):
            self._advance()
            finally_block = self._parse_block()
        return TryCatchStatement(
            body=body,
            error_name=err_name,
            handler=handler,
            finally_block=finally_block,
            line=tok.line,
            column=tok.column,
        )

    def _parse_atomic(self) -> AtomicStatement:
        tok = self._expect(TokenType.ATOMIC)
        body = self._parse_block()
        return AtomicStatement(body=body, line=tok.line, column=tok.column)

    def _parse_transaction(self) -> TransactionStatement:
        tok = self._expect(TokenType.TRANSACTION)
        target = self._parse_expression()
        body_stmts: list[Node] = []
        compensate_block: Block | None = None
        self._expect(TokenType.LBRACE)
        while not self._check(TokenType.RBRACE) and not self._at_end():
            if self._check(TokenType.COMPENSATE):
                compensate_block = self._parse_compensate_block()
            else:
                stmt = self._parse_statement()
                if stmt is not None:
                    body_stmts.append(stmt)
        self._expect(TokenType.RBRACE)
        body = Block(body=body_stmts, line=tok.line, column=tok.column)
        return TransactionStatement(
            target=target,
            body=body,
            compensate=compensate_block,
            line=tok.line,
            column=tok.column,
        )

    def _parse_compensate(self) -> CompensateStatement:
        tok = self._expect(TokenType.COMPENSATE)
        body = self._parse_block()
        return CompensateStatement(body=body, line=tok.line, column=tok.column)

    def _parse_compensate_block(self) -> Block:
        tok = self._expect(TokenType.COMPENSATE)
        body = self._parse_block()
        return body

    def _parse_return(self) -> ReturnStatement:
        tok = self._expect(TokenType.RETURN)
        # Check if there's a value on the same line
        value = None
        if not self._check(TokenType.RBRACE) and not self._at_end():
            value = self._parse_expression()
        return ReturnStatement(value=value, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _parse_log(self) -> LogStatement:
        tok = self._expect(TokenType.LOG)
        level_tok = self._current()
        if level_tok.type in (TokenType.INFO, TokenType.WARN, TokenType.ERROR):
            self._advance()
            level = level_tok.value
        else:
            level = "info"
        message = self._parse_expression()
        return LogStatement(level=level, message=message, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # File / Folder / Data operations
    # ------------------------------------------------------------------

    def _parse_move(self) -> MoveStatement:
        tok = self._expect(TokenType.MOVE)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
            target_type = "file"
        elif self._check(TokenType.FOLDER_TYPE):
            self._advance()
            target_type = "folder"
        elif self._check(TokenType.IDENTIFIER) and self._current().value == "files":
            self._advance()
            target_type = "files"

        source = self._parse_value_expression()

        # Handle "move files from <dir> where ... to <dir>"
        where_clause = None
        if self._check(TokenType.FROM):
            self._advance()
            source = self._parse_value_expression()

        if self._check(TokenType.WHERE):
            self._advance()
            where_clause = self._parse_value_expression()

        self._expect(TokenType.TO)
        destination = self._parse_value_expression()

        # Optional modifiers
        verify_checksum = None
        preserve_metadata = False
        parallel = None
        retry = None

        while True:
            if self._check(TokenType.VERIFY):
                self._advance()
                if self._check(TokenType.CHECKSUM):
                    self._advance()
                    verify_checksum = self._expect(TokenType.IDENTIFIER).value
            elif self._check(TokenType.PRESERVE):
                self._advance()
                self._advance()  # metadata
                preserve_metadata = True
            elif self._check(TokenType.PARALLEL):
                self._advance()
                parallel = int(self._expect(TokenType.NUMBER).value)
            elif self._check(TokenType.RETRY):
                self._advance()
                retry = int(self._expect(TokenType.NUMBER).value)
            else:
                break

        return MoveStatement(
            target_type=target_type,
            source=source,
            destination=destination,
            verify_checksum=verify_checksum,
            preserve_metadata=preserve_metadata,
            parallel=parallel,
            retry=retry,
            where_clause=where_clause,
            line=tok.line,
            column=tok.column,
        )

    def _parse_copy(self) -> CopyStatement:
        tok = self._expect(TokenType.COPY)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
        elif self._check(TokenType.FOLDER_TYPE):
            self._advance()
            target_type = "folder"

        source = self._parse_value_expression()
        self._expect(TokenType.TO)
        destination = self._parse_value_expression()

        verify_checksum = None
        preserve_metadata = False
        while True:
            if self._check(TokenType.VERIFY):
                self._advance()
                if self._check(TokenType.CHECKSUM):
                    self._advance()
                    verify_checksum = self._expect(TokenType.IDENTIFIER).value
            elif self._check(TokenType.PRESERVE):
                self._advance()
                self._advance()
                preserve_metadata = True
            else:
                break

        return CopyStatement(
            target_type=target_type,
            source=source,
            destination=destination,
            verify_checksum=verify_checksum,
            preserve_metadata=preserve_metadata,
            line=tok.line,
            column=tok.column,
        )

    def _parse_read(self) -> ReadStatement:
        tok = self._expect(TokenType.READ)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
        elif self._check(TokenType.FOLDER_TYPE):
            self._advance()
            target_type = "folder"
        path = self._parse_value_expression()
        return ReadStatement(target_type=target_type, path=path, line=tok.line, column=tok.column)

    def _parse_write(self) -> WriteStatement:
        tok = self._expect(TokenType.WRITE)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
        path = self._parse_value_expression()
        data = None
        if self._match(TokenType.WITH):
            data = self._parse_value_expression()
        return WriteStatement(
            target_type=target_type, path=path, data=data, line=tok.line, column=tok.column
        )

    def _parse_delete(self) -> DeleteStatement:
        tok = self._expect(TokenType.DELETE)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
        elif self._check(TokenType.FOLDER_TYPE):
            self._advance()
            target_type = "folder"
        path = self._parse_value_expression()
        return DeleteStatement(target_type=target_type, path=path, line=tok.line, column=tok.column)

    def _parse_stream(self) -> StreamStatement:
        tok = self._expect(TokenType.STREAM)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
        elif self._check(TokenType.FOLDER_TYPE):
            self._advance()
            target_type = "folder"
        source = self._parse_value_expression()
        # Pipeline stages follow
        stages: list[Node] = []
        while self._check(TokenType.PIPE_ARROW):
            self._advance()
            stages.append(self._parse_pipeline_stage())
        return StreamStatement(
            target_type=target_type,
            source=source,
            pipeline=stages,
            line=tok.line,
            column=tok.column,
        )

    def _parse_sync(self) -> SyncStatement:
        tok = self._expect(TokenType.SYNC)
        if self._check(TokenType.FOLDER_TYPE):
            self._advance()
        source = self._parse_expression()
        self._expect(TokenType.WITH)
        destination = self._parse_expression()
        mode = None
        compare = None
        do_encrypt = False
        while True:
            if self._check(TokenType.MODE):
                self._advance()
                mode = self._advance().value
            elif self._check(TokenType.COMPARE):
                self._advance()
                compare = self._advance().value
            elif self._check(TokenType.ENCRYPT):
                self._advance()
                val = self._advance()
                do_encrypt = val.value in ("true", "1")
            else:
                break
        return SyncStatement(
            source=source,
            destination=destination,
            mode=mode,
            compare=compare,
            encrypt=do_encrypt,
            line=tok.line,
            column=tok.column,
        )

    def _parse_watch(self) -> WatchStatement:
        tok = self._expect(TokenType.WATCH)
        if self._check(TokenType.FOLDER_TYPE):
            self._advance()
        path = self._parse_expression()
        return WatchStatement(path=path, line=tok.line, column=tok.column)

    def _parse_parse_stmt(self) -> ParseStatement:
        tok = self._expect(TokenType.PARSE)
        fmt_tok = self._advance()  # json, csv, xml, yaml
        # Data argument is optional — in pipeline context it comes from upstream
        data = None
        if not self._check(TokenType.EOF, TokenType.RBRACE, TokenType.PIPE_ARROW):
            data = self._parse_value_expression()
        return ParseStatement(format=fmt_tok.value, data=data, line=tok.line, column=tok.column)

    def _parse_validate(self) -> ValidateStatement:
        tok = self._expect(TokenType.VALIDATE)
        data = self._parse_expression()
        self._expect(TokenType.USING)
        schema = self._parse_expression()
        return ValidateStatement(data=data, schema=schema, line=tok.line, column=tok.column)

    def _parse_redact(self) -> RedactStatement:
        tok = self._expect(TokenType.REDACT)
        data = self._parse_expression()
        fields: list[str] = []
        if self._match(TokenType.FIELDS):
            self._expect(TokenType.LBRACKET)
            while not self._check(TokenType.RBRACKET) and not self._at_end():
                fields.append(self._expect(TokenType.STRING).value)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RBRACKET)
        return RedactStatement(data=data, fields=fields, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Adapters / connectors
    # ------------------------------------------------------------------

    def _parse_use(self) -> UseStatement:
        tok = self._expect(TokenType.USE)
        kind = "adapter"
        if self._check(TokenType.ADAPTER):
            self._advance()
            kind = "adapter"
        elif self._check(TokenType.IDENTIFIER) and self._current().value == "db":
            self._advance()
            kind = "db"
        name_tok = self._expect(TokenType.IDENTIFIER)
        alias = None
        if self._match(TokenType.AS):
            alias = self._expect(TokenType.IDENTIFIER).value
        return UseStatement(kind=kind, name=name_tok.value, alias=alias, line=tok.line, column=tok.column)

    def _parse_adapter(self) -> AdapterDeclaration:
        tok = self._expect(TokenType.ADAPTER)
        name_tok = self._expect(TokenType.IDENTIFIER)
        sandboxed = False
        if self._check(TokenType.SANDBOXED):
            self._advance()
            sandboxed = True
        body = self._parse_block()
        return AdapterDeclaration(
            name=name_tok.value, sandboxed=sandboxed, body=body, line=tok.line, column=tok.column
        )

    def _parse_connector(self) -> ConnectorDeclaration:
        tok = self._expect(TokenType.CONNECTOR)
        name_tok = self._expect(TokenType.IDENTIFIER)
        body = self._parse_block()
        return ConnectorDeclaration(name=name_tok.value, body=body, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Loops
    # ------------------------------------------------------------------

    def _parse_for(self) -> "ForStatement | ForCStyleStatement":
        tok = self._expect(TokenType.FOR)
        is_async = False
        if self._check(TokenType.AWAIT):
            self._advance()  # consume 'await'
            is_async = True
        # Optional parentheses around the for-loop header: for (...) { }
        has_paren = self._match(TokenType.LPAREN)
        # Support: for [a, b] in/of ... — list destructuring
        if self._check(TokenType.LBRACKET):
            self._advance()  # consume '['
            dest_vars: list[str] = []
            while not self._check(TokenType.RBRACKET) and not self._at_end():
                dest_vars.append(self._expect_ident().value)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RBRACKET)
            if (self._check(TokenType.IDENTIFIER) and self._current().value == "of"):
                self._advance()  # consume 'of'
            else:
                self._expect(TokenType.IN)
            iterable = self._parse_value_expression()
            if has_paren:
                self._expect(TokenType.RPAREN)
            body = self._parse_block()
            return ForStatement(
                var=dest_vars[0] if dest_vars else "_",
                vars=dest_vars,
                iterable=iterable, body=body,
                is_async=is_async,
                line=tok.line, column=tok.column,
            )
        # Support: for {x, y} in/of ... — object destructuring
        if self._check(TokenType.LBRACE):
            self._advance()  # consume '{'
            obj_dest_vars: list[str] = []
            while not self._check(TokenType.RBRACE) and not self._at_end():
                obj_dest_vars.append(self._expect_ident().value)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RBRACE)
            if (self._check(TokenType.IDENTIFIER) and self._current().value == "of"):
                self._advance()  # consume 'of'
            else:
                self._expect(TokenType.IN)
            iterable = self._parse_value_expression()
            if has_paren:
                self._expect(TokenType.RPAREN)
            body = self._parse_block()
            synth_var = "__obj_destruct__:" + ",".join(obj_dest_vars)
            return ForStatement(
                var=synth_var,
                vars=[synth_var],
                iterable=iterable, body=body,
                is_async=is_async,
                line=tok.line, column=tok.column,
            )
        # C-style: for var i = 0; i < 5; i++ { ... }
        if self._check(TokenType.VAR, TokenType.LET, TokenType.CONST):
            # Peek ahead: if this is var/let/const IDENT = expr ; it's C-style
            saved_pos = self.pos
            try:
                init_stmt = self._parse_statement()
                # Handle comma-separated declarations: var i = 0, j = 10
                if self._check(TokenType.COMMA) and isinstance(init_stmt, (VarDeclaration, LetDeclaration)):
                    stmts = [init_stmt]
                    while self._match(TokenType.COMMA):
                        # Parse the next IDENT = expr (no var/let keyword)
                        name_tok = self._expect_ident()
                        self._expect(TokenType.EQ)
                        val_node = self._parse_expression()
                        # Use the same mutability as the first declaration
                        if isinstance(init_stmt, VarDeclaration):
                            stmts.append(VarDeclaration(name=name_tok.value, type_annotation=None, value=val_node, line=name_tok.line, column=name_tok.column))
                        else:
                            stmts.append(LetDeclaration(name=name_tok.value, type_annotation=None, value=val_node, privacy=None, line=name_tok.line, column=name_tok.column))
                    init_stmt = Block(body=stmts, line=stmts[0].line, column=stmts[0].column)
                if self._match(TokenType.SEMICOLON):
                    # condition may be empty: for (var i=0;; update)
                    if self._check(TokenType.SEMICOLON):
                        condition = BoolLiteral(value=True, line=tok.line, column=tok.column)
                    else:
                        condition = self._parse_value_expression()
                    self._expect(TokenType.SEMICOLON)
                    # Support comma-separated updates: i++, j--  (may also be empty)
                    if self._check(TokenType.RPAREN):
                        update: Node = NullLiteral(line=tok.line, column=tok.column)
                    else:
                        update = self._parse_expr_or_assignment()
                    if self._check(TokenType.COMMA):
                        update_nodes: list[Node] = [update]
                        while self._match(TokenType.COMMA):
                            update_nodes.append(self._parse_expr_or_assignment())
                        update = Block(
                            body=update_nodes,
                            line=update_nodes[0].line, column=update_nodes[0].column,
                        )
                    if has_paren:
                        self._expect(TokenType.RPAREN)
                    body = self._parse_block()
                    return ForCStyleStatement(
                        init=init_stmt, condition=condition, update=update, body=body,
                        line=tok.line, column=tok.column,
                    )
                # Not C-style, restore and fall through
                self.pos = saved_pos
            except Exception:
                self.pos = saved_pos
        # C-style with empty init or expression init: for (;;) { }
        # or for (; cond; update) { }  or  for (i=0; cond; update) { }
        # Must be in parentheses to disambiguate from for-in/of.
        if has_paren:
            # Empty init: for (; cond ; update)
            if self._check(TokenType.SEMICOLON):
                self._advance()  # consume ';'
                # condition (may be empty too, e.g. for(;;))
                if self._check(TokenType.SEMICOLON):
                    cond_node: Node = BoolLiteral(value=True, line=tok.line, column=tok.column)
                else:
                    cond_node = self._parse_value_expression()
                self._expect(TokenType.SEMICOLON)
                # update (may be empty: for(;;))
                if self._check(TokenType.RPAREN):
                    up_node: Node = NullLiteral(line=tok.line, column=tok.column)
                else:
                    up_node = self._parse_expr_or_assignment()
                    if self._check(TokenType.COMMA):
                        up_nodes: list[Node] = [up_node]
                        while self._match(TokenType.COMMA):
                            up_nodes.append(self._parse_expr_or_assignment())
                        up_node = Block(body=up_nodes, line=up_nodes[0].line, column=up_nodes[0].column)
                self._expect(TokenType.RPAREN)
                body_empty = self._parse_block_or_stmt()
                return ForCStyleStatement(
                    init=NullLiteral(line=tok.line, column=tok.column),
                    condition=cond_node,
                    update=up_node,
                    body=body_empty,
                    line=tok.line, column=tok.column,
                )
            # Expression/assignment init: for (i=0; cond; update) or for (i++; ...)
            # Look ahead to see if current position looks like an expression followed by ';'
            # Use backtracking to avoid mis-parsing a for-in/of loop
            saved_pos2 = self.pos
            try:
                init_expr = self._parse_expr_or_assignment()
                # If the initializer is actually a comma sequence
                if self._check(TokenType.COMMA):
                    init_exprs: list[Node] = [init_expr]
                    while self._match(TokenType.COMMA):
                        init_exprs.append(self._parse_expr_or_assignment())
                    init_expr = Block(body=init_exprs, line=init_exprs[0].line, column=init_exprs[0].column)
                if self._check(TokenType.SEMICOLON):
                    self._advance()  # consume first ';'
                    if self._check(TokenType.SEMICOLON):
                        # for (init; ; update) — empty condition
                        cond_e: Node = BoolLiteral(value=True, line=tok.line, column=tok.column)
                    else:
                        cond_e = self._parse_value_expression()
                    self._expect(TokenType.SEMICOLON)
                    if self._check(TokenType.RPAREN):
                        up_e: Node = NullLiteral(line=tok.line, column=tok.column)
                    else:
                        up_e = self._parse_expr_or_assignment()
                        if self._check(TokenType.COMMA):
                            up_es: list[Node] = [up_e]
                            while self._match(TokenType.COMMA):
                                up_es.append(self._parse_expr_or_assignment())
                            up_e = Block(body=up_es, line=up_es[0].line, column=up_es[0].column)
                    self._expect(TokenType.RPAREN)
                    body_e = self._parse_block_or_stmt()
                    return ForCStyleStatement(
                        init=init_expr,
                        condition=cond_e,
                        update=up_e,
                        body=body_e,
                        line=tok.line, column=tok.column,
                    )
                # Not a C-style semicolon, restore and fall through to for-in/of
                self.pos = saved_pos2
            except Exception:
                self.pos = saved_pos2
        # for let x of ... / for var x of ... (skip optional let/var/const before iterator var)
        let_var_tok = None
        if self._check(TokenType.LET, TokenType.VAR, TokenType.CONST):
            let_var_tok = self._advance()
        # Handle array destructure: for let [a, b] of list  or  for [a, b] of list
        if self._check(TokenType.LBRACKET):
            dest_tok = let_var_tok if let_var_tok is not None else tok
            mutable = (let_var_tok is not None and let_var_tok.type == TokenType.VAR)
            dest_node = self._parse_list_destructure(dest_tok, mutable)
            dest_node.value = None  # will be filled at runtime
            synth_name = "__list_destruct_for__:" + ",".join(dest_node.names)
            if (self._check(TokenType.IDENTIFIER) and self._current().value == "of"):
                self._advance()
            else:
                self._expect(TokenType.IN)
            iterable = self._parse_value_expression()
            if has_paren:
                self._expect(TokenType.RPAREN)
            body = self._parse_block()
            return ForStatement(
                var=synth_name,
                vars=[synth_name],
                iterable=iterable, body=body,
                is_async=is_async,
                _list_destruct_node=dest_node,
                line=tok.line, column=tok.column,
            )
        # Handle object destructure: for let {a, b} of list  or  for {a, b} of list
        if self._check(TokenType.LBRACE):
            dest_tok2 = let_var_tok if let_var_tok is not None else tok
            mutable2 = (let_var_tok is not None and let_var_tok.type == TokenType.VAR)
            dest_node2 = self._parse_object_destructure(dest_tok2, mutable2)
            dest_node2.value = None
            synth_name2 = "__obj_destruct_for__:" + ",".join(dest_node2.names)
            if (self._check(TokenType.IDENTIFIER) and self._current().value == "of"):
                self._advance()
            else:
                self._expect(TokenType.IN)
            iterable = self._parse_value_expression()
            if has_paren:
                self._expect(TokenType.RPAREN)
            body = self._parse_block()
            return ForStatement(
                var=synth_name2,
                vars=[synth_name2],
                iterable=iterable, body=body,
                is_async=is_async,
                _obj_destruct_node=dest_node2,
                line=tok.line, column=tok.column,
            )
        var_tok = self._expect_ident()
        # Destructured: for i, v in enumerate(...)
        extra_vars: list[str] = []
        if self._match(TokenType.COMMA):
            extra_vars.append(self._expect_ident().value)
            while self._match(TokenType.COMMA):
                extra_vars.append(self._expect_ident().value)
        # Support both `for x in ...` and `for x of ...` (of is a contextual keyword)
        if (self._check(TokenType.IDENTIFIER) and self._current().value == "of"):
            self._advance()  # consume 'of'
        else:
            self._expect(TokenType.IN)
        iterable = self._parse_value_expression()
        # Range shorthand: for i in 0..5  (iterable is the start of a range expression)
        if self._check(TokenType.DOTDOT):
            self._advance()
            end_expr = self._parse_value_expression()
            from .ast_nodes import BinaryExpression
            iterable = BinaryExpression(op="..", left=iterable, right=end_expr,
                                        line=iterable.line, column=iterable.column)
        if has_paren:
            self._expect(TokenType.RPAREN)
        body = self._parse_block()
        all_vars = [var_tok.value] + extra_vars
        return ForStatement(
            var=var_tok.value,
            vars=all_vars,
            iterable=iterable, body=body,
            is_async=is_async,
            line=tok.line, column=tok.column,
        )

    def _parse_while(self) -> WhileStatement:
        tok = self._expect(TokenType.WHILE)
        condition = self._parse_value_expression()
        body = self._parse_block_or_stmt()
        return WhileStatement(
            condition=condition, body=body,
            line=tok.line, column=tok.column,
        )

    def _parse_repeat_until(self) -> RepeatUntilStatement:
        tok = self._expect(TokenType.REPEAT)
        body = self._parse_block()
        self._expect(TokenType.UNTIL)
        condition = self._parse_value_expression()
        return RepeatUntilStatement(
            body=body, condition=condition,
            line=tok.line, column=tok.column,
        )

    def _parse_match(self) -> MatchStatement:
        tok = self._expect(TokenType.MATCH)
        subject = self._parse_value_expression()
        self._expect(TokenType.LBRACE)
        arms: list[MatchArm] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            arm_tok = self._current()
            # wildcard: _
            if self._check(TokenType.UNDERSCORE):
                self._advance()
                guard = None
                if self._check(TokenType.WHEN):
                    self._advance()
                    guard = self._parse_expression()
                self._expect(TokenType.FAT_ARROW)
                body = self._parse_match_arm_body()
                arms.append(MatchArm(pattern=None, is_wildcard=True, body=body,
                                     guard=guard,
                                     line=arm_tok.line, column=arm_tok.column))
            else:
                pattern = self._parse_expression()
                range_end = None
                # range pattern: lo..hi =>
                if self._check(TokenType.DOTDOT):
                    self._advance()
                    range_end = self._parse_expression()
                guard = None
                if self._check(TokenType.WHEN):
                    self._advance()
                    guard = self._parse_expression()
                self._expect(TokenType.FAT_ARROW)
                body = self._parse_match_arm_body()
                arms.append(MatchArm(pattern=pattern, is_wildcard=False,
                                     range_end=range_end, guard=guard, body=body,
                                     line=arm_tok.line, column=arm_tok.column))
        self._expect(TokenType.RBRACE)
        return MatchStatement(subject=subject, arms=arms, line=tok.line, column=tok.column)

    def _parse_match_arm_body(self) -> Block:
        """Match arm body can be a block or a single statement terminated by newline/next-arm."""
        tok = self._current()
        if self._check(TokenType.LBRACE):
            return self._parse_block()
        # Single statement — wrap in a Block
        stmt = self._parse_statement()
        body: list[Node] = []
        if stmt is not None:
            body.append(stmt)
        return Block(body=body, line=tok.line, column=tok.column)

    def _parse_assert(self) -> AssertStatement:
        tok = self._expect(TokenType.ASSERT)
        condition = self._parse_null_coalesce()
        message = None
        if self._match(TokenType.COMMA):
            message = self._parse_null_coalesce()
        return AssertStatement(condition=condition, message=message,
                               line=tok.line, column=tok.column)

    def _parse_import(self) -> ImportStatement:
        tok = self._expect(TokenType.IMPORT)
        # import { a, b } from "module"
        if self._check(TokenType.LBRACE):
            self._advance()
            names: list[str] = []
            while not self._check(TokenType.RBRACE) and not self._at_end():
                names.append(self._expect_ident().value)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RBRACE)
            self._expect(TokenType.FROM)
            module_tok = self._expect(TokenType.STRING)
            return ImportStatement(module=module_tok.value, names=names,
                                   line=tok.line, column=tok.column)
        # import "module" [as alias]  or  import name [as alias]
        if self._check(TokenType.STRING):
            module = self._advance().value
        else:
            module = self._expect_ident().value
        alias = None
        if self._check(TokenType.AS) or (self._check(TokenType.IDENTIFIER) and self._current().value == "as"):
            self._advance()
            alias = self._expect_ident().value
        return ImportStatement(module=module, alias=alias,
                               line=tok.line, column=tok.column)

    def _parse_throw(self) -> ThrowStatement:
        tok = self._expect(TokenType.THROW)
        value = self._parse_expression()
        return ThrowStatement(value=value, line=tok.line, column=tok.column)

    def _parse_enum(self) -> EnumDeclaration:
        tok = self._expect(TokenType.ENUM)
        name_tok = self._expect_ident()
        self._expect(TokenType.LBRACE)
        variants: list[str] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            variants.append(self._expect_ident().value)
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE)
        return EnumDeclaration(name=name_tok.value, variants=variants,
                               line=tok.line, column=tok.column)

    def _parse_struct(self) -> StructDeclaration:
        tok = self._expect(TokenType.STRUCT)
        name_tok = self._expect_ident()
        self._expect(TokenType.LBRACE)
        fields: list[tuple[str, str | None]] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            fname = self._expect_ident()
            ftype = None
            if self._match(TokenType.COLON):
                ftype = self._parse_type_name()
            fields.append((fname.value, ftype))
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE)
        return StructDeclaration(name=name_tok.value, fields=fields,
                                 line=tok.line, column=tok.column)

    def _parse_class(self) -> ClassDeclaration:
        tok = self._expect(TokenType.CLASS)
        name_tok = self._expect_ident()
        superclass = None
        interfaces: list[str] = []
        mixins: list[str] = []
        if self._check(TokenType.EXTENDS):
            self._advance()
            superclass = self._expect_ident().value
        if self._check(TokenType.MIXIN):
            self._advance()
            mixins.append(self._expect_ident().value)
            while self._match(TokenType.COMMA):
                mixins.append(self._expect_ident().value)
        if self._check(TokenType.IMPLEMENTS):
            self._advance()
            interfaces.append(self._expect_ident().value)
            while self._match(TokenType.COMMA):
                interfaces.append(self._expect_ident().value)
        body = self._parse_class_body()
        return ClassDeclaration(name=name_tok.value, superclass=superclass,
                                interfaces=interfaces, mixins=mixins, body=body,
                                line=tok.line, column=tok.column)

    def _parse_class_body(self) -> Block:
        """Parse a class body, recognising contextual `get`/`set`/`static` keywords."""
        tok = self._expect(TokenType.LBRACE)
        body: list[Node] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            # Skip statement-separator semicolons inside class bodies
            while self._check(TokenType.SEMICOLON):
                self._advance()
            if self._check(TokenType.RBRACE) or self._at_end():
                break
            cur = self._current()
            # Contextual `get propName() { ... }`
            if (cur.type == TokenType.IDENTIFIER and cur.value == "get"
                    and self._peek(1).type in self._IDENTIFIER_LIKE):
                self._advance()  # consume 'get'
                name_tok = self._expect_ident()
                self._expect(TokenType.LPAREN)
                self._expect(TokenType.RPAREN)
                # optional return type annotation
                if self._check(TokenType.ARROW):
                    self._advance()
                    self._parse_type_name()
                getter_body = self._parse_block()
                body.append(GetterDeclaration(name=name_tok.value, body=getter_body,
                                              line=cur.line, column=cur.column))
                continue
            # Contextual `get [expr]() { ... }` — computed getter
            if (cur.type == TokenType.IDENTIFIER and cur.value == "get"
                    and self._peek(1).type == TokenType.LBRACKET):
                self._advance()  # consume 'get'
                self._advance()  # consume '['
                cg_key = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                self._expect(TokenType.LPAREN)
                self._expect(TokenType.RPAREN)
                if self._check(TokenType.ARROW):
                    self._advance()
                    self._parse_type_name()
                cg_body = self._parse_block()
                body.append(ComputedMethodDeclaration(
                    key=cg_key, params=[], body=cg_body,
                    is_getter=True, defaults={}, rest_param=None,
                    line=cur.line, column=cur.column,
                ))
                continue
            # Contextual `set propName(param) { ... }`
            if (cur.type == TokenType.IDENTIFIER and cur.value == "set"
                    and self._peek(1).type in self._IDENTIFIER_LIKE):
                self._advance()  # consume 'set'
                name_tok = self._expect_ident()
                self._expect(TokenType.LPAREN)
                param_tok = self._expect_ident()
                self._expect(TokenType.RPAREN)
                setter_body = self._parse_block()
                body.append(SetterDeclaration(name=name_tok.value, param=param_tok.value,
                                              body=setter_body,
                                              line=cur.line, column=cur.column))
                continue
            # Contextual `set [expr](param) { ... }` — computed setter
            if (cur.type == TokenType.IDENTIFIER and cur.value == "set"
                    and self._peek(1).type == TokenType.LBRACKET):
                self._advance()  # consume 'set'
                self._advance()  # consume '['
                cs_key = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                self._expect(TokenType.LPAREN)
                cs_param = self._expect_ident().value
                self._expect(TokenType.RPAREN)
                cs_body = self._parse_block()
                body.append(ComputedMethodDeclaration(
                    key=cs_key, params=[(cs_param, None)], body=cs_body,
                    is_setter=True, defaults={}, rest_param=None,
                    line=cur.line, column=cur.column,
                ))
                continue
            # `fn get propName() { ... }` or `fn set propName(v) { ... }` — JS-compatible getter/setter
            if cur.type == TokenType.FN:
                if (self._peek(1).type == TokenType.IDENTIFIER and self._peek(1).value in ("get", "set")
                        and self._peek(2).type in self._IDENTIFIER_LIKE):
                    self._advance()  # consume 'fn'
                    accessor_tok = self._advance()  # consume 'get' or 'set'
                    if accessor_tok.value == "get":
                        name_tok = self._expect_ident()
                        self._expect(TokenType.LPAREN)
                        self._expect(TokenType.RPAREN)
                        if self._check(TokenType.ARROW):
                            self._advance()
                            self._parse_type_name()
                        getter_body = self._parse_block()
                        body.append(GetterDeclaration(name=name_tok.value, body=getter_body,
                                                      line=cur.line, column=cur.column))
                    else:  # 'set'
                        name_tok = self._expect_ident()
                        self._expect(TokenType.LPAREN)
                        param_tok = self._expect_ident()
                        self._expect(TokenType.RPAREN)
                        setter_body = self._parse_block()
                        body.append(SetterDeclaration(name=name_tok.value, param=param_tok.value,
                                                      body=setter_body,
                                                      line=cur.line, column=cur.column))
                    continue
                # fn [Symbol.iterator]() { ... } — computed method with fn keyword
                if self._peek(1).type == TokenType.LBRACKET:
                    self._advance()  # consume 'fn'
                    self._advance()  # consume '['
                    key_expr = self._parse_expression()
                    self._expect(TokenType.RBRACKET)
                    self._expect(TokenType.LPAREN)
                    comp_params: list[tuple[str, str | None]] = []
                    comp_defaults: dict = {}
                    comp_rest: str | None = None
                    while not self._check(TokenType.RPAREN) and not self._at_end():
                        if self._check(TokenType.ELLIPSIS):
                            self._advance()
                            comp_rest = self._expect_ident().value
                            break
                        pname = self._expect_ident().value
                        ptype = None
                        if self._match(TokenType.COLON):
                            ptype = self._parse_type_name()
                        comp_params.append((pname, ptype))
                        if self._check(TokenType.EQ):
                            self._advance()
                            comp_defaults[pname] = self._parse_expression()
                        if not self._match(TokenType.COMMA):
                            break
                    self._expect(TokenType.RPAREN)
                    if self._check(TokenType.ARROW):
                        self._advance()
                        self._parse_type_name()
                    comp_body = self._parse_block()
                    body.append(ComputedMethodDeclaration(
                        key=key_expr, params=comp_params, body=comp_body,
                        defaults=comp_defaults, rest_param=comp_rest,
                        line=cur.line, column=cur.column,
                    ))
                    continue
            if (cur.type == TokenType.IDENTIFIER and cur.value == "static"):
                next_tok = self._peek(1)
                # static { ... } — class static initialization block
                if next_tok.type == TokenType.LBRACE:
                    self._advance()  # consume 'static'
                    static_block = self._parse_block()
                    # Represent as a FunctionDeclaration named "__static_init__"
                    body.append(FunctionDeclaration(
                        name="__static_init__",
                        params=[],
                        body=static_block,
                        defaults={},
                        rest_param=None,
                        is_async=False,
                        is_generator=False,
                        line=cur.line,
                        column=cur.column,
                    ))
                    continue
                # static get propName() { ... } or static set propName(v) { ... }
                if (next_tok.type == TokenType.IDENTIFIER
                        and next_tok.value in ("get", "set")
                        and self._peek(2).type in self._IDENTIFIER_LIKE):
                    self._advance()  # consume 'static'
                    accessor_tok = self._advance()  # consume 'get' or 'set'
                    if accessor_tok.value == "get":
                        name_tok = self._expect_ident()
                        self._expect(TokenType.LPAREN)
                        self._expect(TokenType.RPAREN)
                        if self._check(TokenType.ARROW):
                            self._advance()
                            self._parse_type_name()
                        getter_body = self._parse_block()
                        body.append(GetterDeclaration(name=f"__static__{name_tok.value}",
                                                      body=getter_body,
                                                      line=cur.line, column=cur.column))
                    else:  # set
                        name_tok = self._expect_ident()
                        self._expect(TokenType.LPAREN)
                        param_tok = self._expect_ident()
                        self._expect(TokenType.RPAREN)
                        setter_body = self._parse_block()
                        body.append(SetterDeclaration(name=f"__static__{name_tok.value}",
                                                      param=param_tok.value,
                                                      body=setter_body,
                                                      line=cur.line, column=cur.column))
                    continue
                # static [expr]() { ... } — static computed method (e.g. static [Symbol.hasInstance]())
                if next_tok.type == TokenType.LBRACKET:
                    self._advance()  # consume 'static'
                    self._advance()  # consume '['
                    sc_key = self._parse_expression()
                    self._expect(TokenType.RBRACKET)
                    self._expect(TokenType.LPAREN)
                    sc_params: list[tuple[str, str | None]] = []
                    sc_defaults: dict = {}
                    sc_rest: str | None = None
                    while not self._check(TokenType.RPAREN) and not self._at_end():
                        if self._check(TokenType.ELLIPSIS):
                            self._advance()
                            sc_rest = self._expect_ident().value
                            break
                        pname = self._expect_ident().value
                        sc_params.append((pname, None))
                        if not self._match(TokenType.COMMA):
                            break
                    self._expect(TokenType.RPAREN)
                    sc_body = self._parse_block()
                    body.append(ComputedMethodDeclaration(
                        key=sc_key, params=sc_params, body=sc_body,
                        is_static=True, defaults=sc_defaults, rest_param=sc_rest,
                        line=cur.line, column=cur.column,
                    ))
                    continue
                if next_tok.type in self._IDENTIFIER_LIKE or next_tok.type == TokenType.FN:
                    self._advance()  # consume 'static'
                    if self._check(TokenType.FN):
                        # static fn name(...) { ... }
                        fn_node = self._parse_fn()
                        body.append(fn_node)
                        continue
                    if self._check(TokenType.FN_STAR):
                        fn_node = self._parse_fn(is_generator=True)
                        body.append(fn_node)
                        continue
                    name_tok = self._expect_ident()
                    # static name() { ... } — static method shorthand (no fn keyword)
                    if self._check(TokenType.LPAREN):
                        sm_params, sm_defaults, sm_rest = self._parse_method_params()
                        # optional return type annotation
                        if self._check(TokenType.ARROW):
                            self._advance()
                            self._parse_type_name()
                        sm_body = self._parse_block()
                        # Static methods use plain name (same convention as `static fn name()`)
                        body.append(FunctionDeclaration(
                            name=name_tok.value,
                            params=sm_params,
                            body=sm_body,
                            defaults=sm_defaults,
                            rest_param=sm_rest,
                            is_async=False,
                            is_generator=False,
                            line=cur.line,
                            column=cur.column,
                        ))
                        continue
                    value_node = None
                    if self._match(TokenType.EQ):
                        value_node = self._parse_expression()
                    body.append(VarDeclaration(
                        name=name_tok.value,
                        type_annotation=None,
                        value=value_node,
                        line=cur.line,
                        column=cur.column,
                    ))
                    continue
                # static #field = value  or  static #method() { }
                if next_tok.type == TokenType.PRIVATE_IDENT:
                    self._advance()  # consume 'static'
                    sp_tok = self._advance()  # consume the PRIVATE_IDENT token
                    sp_name = f"__static_private__{sp_tok.value}"
                    if self._check(TokenType.LPAREN):
                        # static #method(...) { ... } — static private method
                        spm_params, spm_defaults, spm_rest = self._parse_method_params()
                        if self._check(TokenType.ARROW):
                            self._advance()
                            self._parse_type_name()
                        spm_body = self._parse_block()
                        body.append(FunctionDeclaration(
                            name=sp_name,
                            params=spm_params,
                            body=spm_body,
                            defaults=spm_defaults,
                            rest_param=spm_rest,
                            is_async=False,
                            is_generator=False,
                            line=cur.line,
                            column=cur.column,
                        ))
                    else:
                        # static #field = value — static private field
                        sp_value = None
                        if self._match(TokenType.EQ):
                            sp_value = self._parse_expression()
                        body.append(VarDeclaration(
                            name=sp_name,
                            type_annotation=None,
                            value=sp_value,
                            line=cur.line,
                            column=cur.column,
                        ))
                    continue
            # Computed method: [Symbol.iterator]() { ... }
            if self._check(TokenType.LBRACKET):
                self._advance()  # consume '['
                key_expr = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                self._expect(TokenType.LPAREN)
                comp_params: list[tuple[str, str | None]] = []
                comp_defaults: dict = {}
                comp_rest: str | None = None
                while not self._check(TokenType.RPAREN) and not self._at_end():
                    if self._check(TokenType.ELLIPSIS):
                        self._advance()
                        comp_rest = self._expect_ident().value
                        break
                    pname = self._expect_ident().value
                    comp_params.append((pname, None))
                    if not self._match(TokenType.COMMA):
                        break
                self._expect(TokenType.RPAREN)
                comp_body = self._parse_block()
                body.append(ComputedMethodDeclaration(
                    key=key_expr, params=comp_params, body=comp_body,
                    defaults=comp_defaults, rest_param=comp_rest,
                    line=cur.line, column=cur.column,
                ))
                continue
            # Method shorthand: name() { ... }  (without fn keyword)
            # Must come after get/set/fn/static/computed checks to avoid conflicts.
            # Also handles: async name() { ... } and *name() { ... } generator methods.
            ms_is_async = False
            ms_is_gen = False
            cur = self._current()  # refresh after the previous checks may have advanced
            # #methodName() { ... } — private instance method shorthand
            if cur.type == TokenType.PRIVATE_IDENT and self._peek(1).type == TokenType.LPAREN:
                pm_tok = self._advance()  # consume PRIVATE_IDENT
                pm_name = f"__private__{pm_tok.value}"
                pm_params, pm_defaults, pm_rest = self._parse_method_params()
                if self._check(TokenType.ARROW):
                    self._advance()
                    self._parse_type_name()
                pm_body = self._parse_block()
                body.append(FunctionDeclaration(
                    name=pm_name,
                    params=pm_params,
                    body=pm_body,
                    defaults=pm_defaults,
                    rest_param=pm_rest,
                    is_async=False,
                    is_generator=False,
                    line=pm_tok.line,
                    column=pm_tok.column,
                ))
                continue
            if cur.type == TokenType.IDENTIFIER and cur.value == "async":
                # async name() { ... } — look-ahead to confirm it's a method
                if self._peek(1).type in self._IDENTIFIER_LIKE and self._peek(2).type == TokenType.LPAREN:
                    ms_is_async = True
                    self._advance()  # consume 'async'
                    cur = self._current()
            if cur.type == TokenType.STAR:
                # *name() { ... } — generator method shorthand
                if self._peek(1).type in self._IDENTIFIER_LIKE and self._peek(2).type == TokenType.LPAREN:
                    ms_is_gen = True
                    self._advance()  # consume '*'
                    cur = self._current()
                # *[expr]() { ... } — generator computed method shorthand
                elif self._peek(1).type == TokenType.LBRACKET:
                    self._advance()  # consume '*'
                    self._advance()  # consume '['
                    gc_key = self._parse_expression()
                    self._expect(TokenType.RBRACKET)
                    gc_params, gc_defaults, gc_rest = self._parse_method_params()
                    if self._check(TokenType.ARROW):
                        self._advance()
                        self._parse_type_name()
                    gc_body = self._parse_block()
                    body.append(ComputedMethodDeclaration(
                        key=gc_key, params=gc_params, body=gc_body,
                        defaults=gc_defaults, rest_param=gc_rest,
                        is_generator=True,
                        line=cur.line, column=cur.column,
                    ))
                    continue
            if cur.type in self._IDENTIFIER_LIKE and self._peek(1).type == TokenType.LPAREN:
                ms_tok = self._advance()
                ms_params, ms_defaults, ms_rest = self._parse_method_params()
                # optional return type
                if self._check(TokenType.ARROW):
                    self._advance()
                    self._parse_type_name()
                ms_body = self._parse_block()
                body.append(FunctionDeclaration(
                    name=ms_tok.value,
                    params=ms_params,
                    body=ms_body,
                    defaults=ms_defaults,
                    rest_param=ms_rest,
                    is_async=ms_is_async,
                    is_generator=ms_is_gen,
                    line=ms_tok.line,
                    column=ms_tok.column,
                ))
                continue
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        self._expect(TokenType.RBRACE)
        return Block(body=body, line=tok.line, column=tok.column)

    def _parse_method_params(self) -> tuple[list[tuple[str, str | None]], dict, str | None]:
        """Parse ``(params)`` for a class method shorthand.

        Expects the opening ``(`` to be current; consumes up to and including
        the closing ``)``.  Returns ``(params, defaults, rest_param)``.
        """
        self._expect(TokenType.LPAREN)
        params: list[tuple[str, str | None]] = []
        defaults: dict = {}
        rest_param: str | None = None
        while not self._check(TokenType.RPAREN) and not self._at_end():
            if self._check(TokenType.ELLIPSIS):
                self._advance()
                rest_param = self._expect_ident().value
                break
            if self._check(TokenType.LBRACE):
                param_names, param_defaults = self._parse_dict_destruct_param()
                params.append(("__destruct__:" + ",".join(param_names), None))
                for _fname, _dflt in param_defaults.items():
                    defaults[f"__destruct_default__{_fname}"] = _dflt
                if not self._match(TokenType.COMMA):
                    break
                continue
            if self._check(TokenType.LBRACKET):
                self._advance()
                arr_names: list[str] = []
                arr_rest: str | None = None
                while not self._check(TokenType.RBRACKET) and not self._at_end():
                    if self._check(TokenType.ELLIPSIS):
                        self._advance()
                        arr_rest = self._expect_ident().value
                        break
                    arr_names.append(self._expect_ident().value)
                    if not self._match(TokenType.COMMA):
                        break
                self._expect(TokenType.RBRACKET)
                synth = "__array_destruct__:" + ",".join(arr_names)
                if arr_rest:
                    synth += "..." + arr_rest
                params.append((synth, None))
                if not self._match(TokenType.COMMA):
                    break
                continue
            pname = self._expect_ident()
            ptype = None
            if self._match(TokenType.COLON):
                ptype = self._parse_type_name()
            default_expr = None
            if self._match(TokenType.EQ):
                default_expr = self._parse_null_coalesce()
            params.append((pname.value, ptype))
            if default_expr is not None:
                defaults[pname.value] = default_expr
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RPAREN)
        return params, defaults, rest_param

    def _parse_interface(self) -> InterfaceDeclaration:
        tok = self._expect(TokenType.INTERFACE)
        name_tok = self._expect_ident()
        # Interface body: method signatures (fn without body) and full methods
        tok2 = self._expect(TokenType.LBRACE)
        body_stmts: list[Node] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            if self._check(TokenType.FN):
                # fn name(params) [-> ReturnType]  — body is optional in interface
                fn = self._parse_fn_signature_or_full()
                body_stmts.append(fn)
            else:
                stmt = self._parse_statement()
                if stmt is not None:
                    body_stmts.append(stmt)
        self._expect(TokenType.RBRACE)
        body = Block(body=body_stmts, line=tok2.line, column=tok2.column)
        return InterfaceDeclaration(name=name_tok.value, body=body,
                                    line=tok.line, column=tok.column)

    def _parse_fn_signature_or_full(self) -> FunctionDeclaration:
        """Parse a fn declaration; body is optional (for interface signatures)."""
        tok = self._expect(TokenType.FN)
        name_tok = self._expect_ident()
        self._expect(TokenType.LPAREN)
        params: list[tuple[str, str | None]] = []
        defaults: dict[str, Node] = {}
        rest_param: str | None = None
        while not self._check(TokenType.RPAREN) and not self._at_end():
            if self._check(TokenType.ELLIPSIS):
                self._advance()
                rest_tok = self._expect_ident()
                rest_param = rest_tok.value
                break
            pname = self._expect_ident()
            ptype = None
            if self._match(TokenType.COLON):
                ptype = self._parse_type_name()
            if not self._match(TokenType.COMMA):
                break
            params.append((pname.value, ptype))
        self._expect(TokenType.RPAREN)
        return_type = None
        if self._match(TokenType.ARROW):
            return_type = self._parse_type_name()
        # Body is optional — if not present, create an empty block (signature only)
        if self._check(TokenType.LBRACE):
            body = self._parse_block()
        elif self._check(TokenType.FAT_ARROW):
            self._advance()
            expr = self._parse_expression()
            body = Block(body=[ReturnStatement(value=expr, line=tok.line, column=tok.column)])
        else:
            body = Block(body=[], line=tok.line, column=tok.column)
        return FunctionDeclaration(
            name=name_tok.value,
            params=params,
            return_type=return_type,
            body=body,
            defaults=defaults,
            rest_param=rest_param,
            line=tok.line,
            column=tok.column,
        )

    def _parse_switch(self) -> SwitchStatement:
        """switch <expr> { case <val>: <body> ... default: <body> }
        
        Both colon syntax (case 1: ...) and brace syntax (case 1 { ... }) are supported.
        """
        tok = self._expect(TokenType.SWITCH)
        subject = self._parse_expression()
        self._expect(TokenType.LBRACE)
        cases: list[SwitchCase] = []
        default_body: Block | None = None
        while not self._check(TokenType.RBRACE) and not self._at_end():
            if self._check(TokenType.CASE):
                case_tok = self._advance()
                value = self._parse_expression()
                if self._check(TokenType.LBRACE):
                    # Brace-style body: case 1 { ... }
                    case_body = self._parse_block()
                else:
                    self._expect(TokenType.COLON)
                    # If body starts with '{', treat it as a brace-delimited block
                    if self._check(TokenType.LBRACE):
                        case_body = self._parse_block()
                    else:
                        stmts: list[Node] = []
                        while (not self._check(TokenType.CASE)
                               and not self._check(TokenType.DEFAULT)
                               and not self._check(TokenType.RBRACE)
                               and not self._at_end()):
                            # Skip statement-separator semicolons
                            while self._check(TokenType.SEMICOLON):
                                self._advance()
                            if (self._check(TokenType.CASE)
                                    or self._check(TokenType.DEFAULT)
                                    or self._check(TokenType.RBRACE)
                                    or self._at_end()):
                                break
                            stmt = self._parse_statement()
                            if stmt is not None:
                                stmts.append(stmt)
                        case_body = Block(body=stmts, line=case_tok.line, column=case_tok.column)
                cases.append(SwitchCase(value=value, body=case_body,
                                        line=case_tok.line, column=case_tok.column))
            elif self._check(TokenType.DEFAULT):
                def_tok = self._advance()
                if self._check(TokenType.LBRACE):
                    default_body = self._parse_block()
                else:
                    self._expect(TokenType.COLON)
                    # If body starts with '{', treat it as a brace-delimited block
                    if self._check(TokenType.LBRACE):
                        default_body = self._parse_block()
                    else:
                        stmts2: list[Node] = []
                        while (not self._check(TokenType.CASE)
                               and not self._check(TokenType.DEFAULT)
                               and not self._check(TokenType.RBRACE)
                               and not self._at_end()):
                            # Skip statement-separator semicolons
                            while self._check(TokenType.SEMICOLON):
                                self._advance()
                            if (self._check(TokenType.CASE)
                                    or self._check(TokenType.DEFAULT)
                                    or self._check(TokenType.RBRACE)
                                    or self._at_end()):
                                break
                            stmt = self._parse_statement()
                            if stmt is not None:
                                stmts2.append(stmt)
                        default_body = Block(body=stmts2, line=def_tok.line, column=def_tok.column)
            else:
                break
        self._expect(TokenType.RBRACE)
        return SwitchStatement(subject=subject, cases=cases, default_body=default_body,
                               line=tok.line, column=tok.column)

    def _parse_do_while(self) -> DoWhileStatement:
        """do { <body> } while <condition>"""
        tok = self._expect(TokenType.DO)
        body = self._parse_block()
        self._expect(TokenType.WHILE)
        condition = self._parse_expression()
        return DoWhileStatement(body=body, condition=condition,
                                line=tok.line, column=tok.column)

    def _parse_spawn(self) -> SpawnStatement:
        """spawn <call_expr>"""
        tok = self._expect(TokenType.SPAWN)
        call = self._parse_expression()
        return SpawnStatement(call=call, line=tok.line, column=tok.column)

    def _parse_websocket(self) -> WebSocketStatement:
        """websocket <name> <url_expr> { <body> }"""
        tok = self._expect(TokenType.WEBSOCKET)
        name_tok = self._expect_ident()
        url = self._parse_expression()
        body = self._parse_block()
        return WebSocketStatement(name=name_tok.value, url=url, body=body,
                                  line=tok.line, column=tok.column)

    def _parse_with(self) -> WithStatement:
        """with <expr> as <name> { <body> }"""
        tok = self._expect(TokenType.WITH)
        expr = self._parse_expression()
        alias = ""
        # Check for 'as name'
        if self._check(TokenType.AS):
            self._advance()  # consume 'as'
            alias = self._expect_ident().value
        elif self._check(TokenType.IDENTIFIER) and self._current().value == "as":
            self._advance()  # consume 'as' identifier
            alias = self._expect_ident().value
        body = self._parse_block()
        return WithStatement(expr=expr, alias=alias, body=body,
                             line=tok.line, column=tok.column)

    def _parse_debit(self) -> DebitStatement:
        """debit account <account_expr> amount <amount_expr>"""
        tok = self._expect(TokenType.DEBIT)
        # optional 'account' keyword
        if self._check(TokenType.IDENTIFIER) and self._current().value == "account":
            self._advance()
        account = self._parse_expression()
        # optional 'amount' keyword
        if self._check(TokenType.IDENTIFIER) and self._current().value == "amount":
            self._advance()
        amount = self._parse_expression()
        return DebitStatement(account=account, amount=amount,
                              line=tok.line, column=tok.column)

    def _parse_credit(self) -> CreditStatement:
        """credit account <account_expr> amount <amount_expr>"""
        tok = self._expect(TokenType.CREDIT)
        # optional 'account' keyword
        if self._check(TokenType.IDENTIFIER) and self._current().value == "account":
            self._advance()
        account = self._parse_expression()
        # optional 'amount' keyword
        if self._check(TokenType.IDENTIFIER) and self._current().value == "amount":
            self._advance()
        amount = self._parse_expression()
        return CreditStatement(account=account, amount=amount,
                               line=tok.line, column=tok.column)

    def _parse_list_destructure(self, let_tok: Token, mutable: bool) -> ListDestructure:
        """Parse let [a, b = default, ...rest] = expr  — list destructuring with defaults"""
        self._expect(TokenType.LBRACKET)
        names: list[str] = []
        rest_name: str | None = None
        defaults: dict[str, "Node"] = {}
        nested_destruct: dict[int, "Node"] = {}
        while not self._check(TokenType.RBRACKET) and not self._at_end():
            if self._check(TokenType.ELLIPSIS):
                self._advance()
                rest_name = self._expect_ident().value
                if not self._check(TokenType.RBRACKET):
                    raise ParseError(
                        "Rest element must be the last element in a list destructuring pattern",
                        self._current(),
                    )
                break  # rest must be last
            # Elision / hole: [a, , b] — a comma with no name skips an element
            if self._check(TokenType.COMMA):
                names.append("__hole__")
                self._advance()  # consume the comma
                continue
            idx = len(names)
            if self._check(TokenType.LBRACKET):
                # Nested array destructuring: [[a, b], c]
                inner = self._parse_list_destructure(let_tok, mutable)
                inner.value = None
                nested_destruct[idx] = inner
                names.append(f"__nested_arr_{idx}__")
            elif self._check(TokenType.LBRACE):
                # Nested object destructuring: [{x, y}, c]
                inner = self._parse_object_destructure(let_tok, mutable)
                inner.value = None
                nested_destruct[idx] = inner
                names.append(f"__nested_obj_{idx}__")
            else:
                name = self._expect_ident().value
                names.append(name)
                # Default value: [a = expr, b]
                if self._match(TokenType.EQ):
                    defaults[name] = self._parse_expression()
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACKET)
        # Only consume = value at top-level (not nested inline patterns)
        if self._check(TokenType.EQ):
            self._advance()
            value: "Node | None" = self._parse_expression()
        else:
            value = None
        return ListDestructure(names=names, value=value, mutable=mutable,
                               rest_name=rest_name, defaults=defaults,
                               nested=nested_destruct,
                               line=let_tok.line, column=let_tok.column)

    def _parse_object_destructure(self, let_tok: Token, mutable: bool) -> ObjectDestructure:
        """Parse let {a, b: alias, c = default, d: {e}, ...rest} = expr"""
        self._expect(TokenType.LBRACE)
        names: list[str] = []
        aliases: dict[str, str] = {}
        nested: dict[str, "Node"] = {}
        defaults: dict[str, "Node"] = {}
        rest_name: str | None = None
        while not self._check(TokenType.RBRACE) and not self._at_end():
            # Rest element: ...rest
            if self._check(TokenType.ELLIPSIS):
                self._advance()
                rest_name = self._expect_ident().value
                break  # rest must be last
            name = self._expect_ident().value
            names.append(name)
            if self._match(TokenType.COLON):
                # {key: alias}  or  {key: {nested}}  or  {key: [nested]}
                if self._check(TokenType.LBRACE):
                    # Nested object destructuring: {a: {b, c}}
                    inner = self._parse_object_destructure(let_tok, mutable)
                    # inner has value=None; we'll fill it at runtime from obj[name]
                    inner.value = None
                    nested[name] = inner
                elif self._check(TokenType.LBRACKET):
                    # Nested array destructuring: {a: [b, c]}
                    inner = self._parse_list_destructure(let_tok, mutable)
                    inner.value = None
                    nested[name] = inner
                else:
                    alias = self._expect_ident().value
                    aliases[name] = alias
                    # Default after alias: {key: alias = default}
                    if self._match(TokenType.EQ):
                        defaults[alias] = self._parse_expression()
            elif self._match(TokenType.EQ):
                # Default value: {key = default}
                defaults[name] = self._parse_expression()
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE)
        # Only consume = value if this is a top-level destructure (not nested inline)
        if self._check(TokenType.EQ):
            self._advance()
            value: "Node | None" = self._parse_expression()
        else:
            value = None
        return ObjectDestructure(names=names, aliases=aliases, nested=nested,
                                 defaults=defaults, value=value,
                                 rest_name=rest_name,
                                 mutable=mutable, line=let_tok.line, column=let_tok.column)

    # ------------------------------------------------------------------
    # File creation / archive
    # ------------------------------------------------------------------

    def _parse_create(self) -> CreateStatement:
        tok = self._expect(TokenType.CREATE)
        target_type = "file"
        if self._check(TokenType.FILE_TYPE):
            self._advance()
        elif self._check(TokenType.FOLDER_TYPE):
            self._advance()
            target_type = "folder"
        path = self._parse_value_expression()
        content = None
        if self._match(TokenType.WITH):
            content = self._parse_value_expression()
        return CreateStatement(
            target_type=target_type, path=path, content=content,
            line=tok.line, column=tok.column,
        )

    def _parse_compress(self) -> CompressStatement:
        tok = self._expect(TokenType.COMPRESS)
        if self._check(TokenType.FOLDER_TYPE):
            self._advance()
        source = self._parse_value_expression()
        self._expect(TokenType.TO)
        destination = self._parse_value_expression()
        return CompressStatement(
            source=source, destination=destination,
            line=tok.line, column=tok.column,
        )

    def _parse_extract(self) -> ExtractStatement:
        tok = self._expect(TokenType.EXTRACT)
        source = self._parse_value_expression()
        self._expect(TokenType.TO)
        if self._check(TokenType.FOLDER_TYPE):
            self._advance()
        destination = self._parse_value_expression()
        return ExtractStatement(
            source=source, destination=destination,
            line=tok.line, column=tok.column,
        )

    # ------------------------------------------------------------------
    # Sleep / schedule
    # ------------------------------------------------------------------

    def _parse_sleep(self) -> SleepStatement:
        tok = self._expect(TokenType.SLEEP)
        duration = self._parse_value_expression()
        unit = "s"
        # Optional unit suffix token directly after the number: "5s", "500ms"
        if self._check(TokenType.IDENTIFIER) and self._current().value in ("s", "ms"):
            unit = self._advance().value
        return SleepStatement(duration=duration, unit=unit, line=tok.line, column=tok.column)

    def _parse_schedule(self) -> ScheduleStatement:
        tok = self._expect(TokenType.SCHEDULE)
        # frequency token — e.g. "daily", or an identifier
        freq_tok = self._current()
        frequency = self._advance().value   # consume "daily" / identifier
        at_time = ""
        if self._check(TokenType.AT):
            self._advance()
            at_time = self._expect(TokenType.STRING).value
        body: Block | None = None
        if self._check(TokenType.LBRACE):
            body = self._parse_block()
        return ScheduleStatement(
            frequency=frequency, at_time=at_time, body=body,
            line=tok.line, column=tok.column,
        )

    # ------------------------------------------------------------------
    # Test blocks
    # ------------------------------------------------------------------

    def _parse_test_block(self) -> TestBlock:
        tok = self._expect(TokenType.TEST)
        name = self._expect(TokenType.STRING).value
        body = self._parse_block()
        return TestBlock(name=name, body=body, line=tok.line, column=tok.column)

    def _parse_expect(self) -> ExpectStatement:
        tok = self._expect(TokenType.EXPECT)

        # expect rollback { ... }
        if self._check(TokenType.ROLLBACK):
            self._advance()
            block = self._parse_block()
            return ExpectStatement(kind="rollback", block=block, line=tok.line, column=tok.column)

        # expect denied { ... }
        if self._check(TokenType.DENIED):
            self._advance()
            block = self._parse_block()
            return ExpectStatement(kind="denied", block=block, line=tok.line, column=tok.column)

        # expect [not] exists <path>
        negated = False
        if self._check(TokenType.NOT):
            self._advance()
            negated = True
        if self._check(TokenType.EXISTS):
            self._advance()
            path_expr = self._parse_value_expression()
            return ExpectStatement(
                kind="exists", condition=path_expr, negated=negated,
                line=tok.line, column=tok.column,
            )

        # expect <expression>
        condition = self._parse_value_expression()
        return ExpectStatement(
            kind="truthy", condition=condition, negated=negated,
            line=tok.line, column=tok.column,
        )

    # ------------------------------------------------------------------
    # Fraud check
    # ------------------------------------------------------------------

    def _parse_fraud_check(self) -> FraudCheckStatement:
        tok = self._expect(TokenType.FRAUD)
        self._expect(TokenType.CHECK)
        # "transaction" keyword or expression
        if self._check(TokenType.TRANSACTION):
            self._advance()
        target = self._parse_expression()
        self._expect(TokenType.LBRACE)
        reason = ""
        case_id = ""
        scope = "minimal"
        redact_personal = False
        while not self._check(TokenType.RBRACE) and not self._at_end():
            field_tok = self._current()
            if field_tok.value == "reason":
                self._advance()
                reason = self._expect(TokenType.STRING).value
            elif field_tok.value == "case":
                self._advance()
                case_id = self._expect(TokenType.STRING).value
            elif field_tok.value == "scope":
                self._advance()
                scope = self._advance().value
            elif field_tok.value == "redact":
                self._advance()
                self._advance()  # personalData
                redact_personal = True
            else:
                self._advance()  # skip unknown
        self._expect(TokenType.RBRACE)
        return FraudCheckStatement(
            target=target,
            reason=reason,
            case_id=case_id,
            scope=scope,
            redact_personal=redact_personal,
            line=tok.line,
            column=tok.column,
        )

    # ------------------------------------------------------------------
    # Built-in keyword statement forms
    # ------------------------------------------------------------------

    def _parse_encode_stmt(self) -> Node:
        """Parse: encode "format" value  —→  CallExpression(encode, [format, value])"""
        tok = self._expect(TokenType.ENCODE)
        callee = Identifier(name="encode", line=tok.line, column=tok.column)
        fmt = self._expect(TokenType.STRING)
        fmt_node = StringLiteral(value=fmt.value, line=fmt.line, column=fmt.column)
        # Value arg is optional (might be used in pipeline without explicit arg)
        if self._check(TokenType.EOF, TokenType.RBRACE, TokenType.PIPE_ARROW):
            return CallExpression(callee=callee, args=[fmt_node], line=tok.line, column=tok.column)
        value = self._parse_value_expression()
        return CallExpression(callee=callee, args=[fmt_node, value], line=tok.line, column=tok.column)

    def _parse_http_stmt(self) -> Node:
        """Parse: http.get "url"  or  http.post "url" with { ... }"""
        tok = self._expect(TokenType.HTTP)
        http_ident = Identifier(name="http", line=tok.line, column=tok.column)
        self._expect(TokenType.DOT)
        method_tok = self._advance()   # get / post / put / delete / patch
        method = method_tok.value
        callee = MemberExpression(object=http_ident, property=method, line=method_tok.line, column=method_tok.column)
        # URL argument
        url = self._parse_value_expression()
        args: list[Node] = [url]
        if self._match(TokenType.WITH):
            body = self._parse_value_expression()
            args.append(body)
        return CallExpression(callee=callee, args=args, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Expression / Assignment
    # ------------------------------------------------------------------

    def _parse_lambda_body(self) -> Node:
        """Parse a lambda body expression: handles assignments but stops before |> pipelines.
        
        Unlike _parse_expr_or_assignment (which calls _parse_pipeline and thus consumes |>),
        this uses _parse_null_coalesce as base so pipelines after the lambda remain independent.
        """
        expr = self._parse_null_coalesce()

        # Simple assignment: name = value
        if self._check(TokenType.EQ) and isinstance(expr, Identifier):
            self._advance()
            value = self._parse_null_coalesce()
            return Assignment(
                name=expr.name, value=value, line=expr.line, column=expr.column
            )

        # Member assignment: obj.prop = value  (incl. self.prop = value)
        if self._check(TokenType.EQ) and isinstance(expr, MemberExpression):
            self._advance()
            value = self._parse_null_coalesce()
            return MemberAssignment(
                object=expr.object, property=expr.property, value=value,
                line=expr.line, column=expr.column,
            )

        # Index assignment: arr[i] = value
        if self._check(TokenType.EQ) and isinstance(expr, IndexExpression):
            self._advance()
            value = self._parse_null_coalesce()
            return IndexAssignment(
                object=expr.object, index=expr.index, value=value,
                line=expr.line, column=expr.column,
            )

        # Compound assignments: name += value, etc.
        _compound_ops = {
            TokenType.PLUS_EQ: "+",
            TokenType.MINUS_EQ: "-",
            TokenType.STAR_EQ: "*",
            TokenType.SLASH_EQ: "/",
            TokenType.PERCENT_EQ: "%",
            TokenType.AMP_EQ: "&",
            TokenType.PIPE_EQ: "|",
            TokenType.CARET_EQ: "^",
            TokenType.LSHIFT_EQ: "<<",
            TokenType.RSHIFT_EQ: ">>",
            TokenType.AND_AND_EQ: "&&",
            TokenType.OR_OR_EQ: "||",
            TokenType.STAR_STAR_EQ: "**",
        }
        if self._current().type in _compound_ops and isinstance(expr, Identifier):
            op = _compound_ops[self._current().type]
            self._advance()
            value = self._parse_null_coalesce()
            return CompoundAssignment(
                name=expr.name, op=op, value=value, line=expr.line, column=expr.column
            )

        if self._current().type in _compound_ops and isinstance(expr, MemberExpression):
            op = _compound_ops[self._current().type]
            self._advance()
            value = self._parse_null_coalesce()
            return CompoundMemberAssignment(
                object=expr.object, property=expr.property, op=op, value=value,
                line=expr.line, column=expr.column,
            )

        return expr

    def _parse_expr_or_assignment(self) -> Node:
        expr = self._parse_pipeline()

        # Simple assignment: name = value
        if self._check(TokenType.EQ) and isinstance(expr, Identifier):
            self._advance()
            value = self._parse_expr_or_assignment()
            return Assignment(
                name=expr.name, value=value, line=expr.line, column=expr.column
            )

        # Member assignment: obj.prop = value  (incl. self.prop = value)
        if self._check(TokenType.EQ) and isinstance(expr, MemberExpression):
            self._advance()
            value = self._parse_expr_or_assignment()
            return MemberAssignment(
                object=expr.object, property=expr.property, value=value,
                line=expr.line, column=expr.column,
            )

        # Index assignment: arr[i] = value
        if self._check(TokenType.EQ) and isinstance(expr, IndexExpression):
            self._advance()
            value = self._parse_expr_or_assignment()
            return IndexAssignment(
                object=expr.object, index=expr.index, value=value,
                line=expr.line, column=expr.column,
            )

        # Compound assignments: name += value, name -= value, name *= value, name /= value, name %= value
        _compound_ops = {
            TokenType.PLUS_EQ: "+",
            TokenType.MINUS_EQ: "-",
            TokenType.STAR_EQ: "*",
            TokenType.SLASH_EQ: "/",
            TokenType.PERCENT_EQ: "%",
            TokenType.AMP_EQ: "&",
            TokenType.PIPE_EQ: "|",
            TokenType.CARET_EQ: "^",
            TokenType.LSHIFT_EQ: "<<",
            TokenType.RSHIFT_EQ: ">>",
            TokenType.AND_AND_EQ: "&&",
            TokenType.OR_OR_EQ: "||",
            TokenType.STAR_STAR_EQ: "**",
        }
        if self._current().type in _compound_ops and isinstance(expr, Identifier):
            op = _compound_ops[self._current().type]
            self._advance()
            value = self._parse_expression()
            return CompoundAssignment(
                name=expr.name, op=op, value=value, line=expr.line, column=expr.column
            )

        # Compound member assignments: obj.prop += value
        if self._current().type in _compound_ops and isinstance(expr, MemberExpression):
            op = _compound_ops[self._current().type]
            self._advance()
            value = self._parse_expression()
            return CompoundMemberAssignment(
                object=expr.object, property=expr.property, op=op, value=value,
                line=expr.line, column=expr.column,
            )

        # Null-coalescing assignment: name ??= value
        if self._current().type == TokenType.QUESTION_QUESTION_EQ and isinstance(expr, Identifier):
            self._advance()
            value = self._parse_expression()
            # Desugar: x ??= v  →  if x == null { x = v }
            return CompoundAssignment(
                name=expr.name, op="??", value=value, line=expr.line, column=expr.column
            )

        # Null-coalescing assignment on member: obj.prop ??= value
        if self._current().type == TokenType.QUESTION_QUESTION_EQ and isinstance(expr, MemberExpression):
            self._advance()
            value = self._parse_expression()
            return CompoundMemberAssignment(
                object=expr.object, property=expr.property, op="??",
                value=value, line=expr.line, column=expr.column,
            )

        # Array destructuring assignment: [a, b] = expr
        if self._check(TokenType.EQ) and isinstance(expr, ArrayLiteral):
            # Validate that all elements are simple identifiers (or ...rest)
            names: list[str] = []
            rest_name: str | None = None
            all_simple = True
            for item in expr.items:
                if isinstance(item, SpreadElement) and isinstance(item.expr, Identifier):
                    rest_name = item.expr.name
                elif isinstance(item, Identifier):
                    names.append(item.name)
                else:
                    all_simple = False
                    break
            if all_simple:
                self._advance()  # consume '='
                value = self._parse_expression()
                return ListDestructureAssignment(
                    names=names, value=value, rest_name=rest_name,
                    line=expr.line, column=expr.column,
                )

        return expr

    def _parse_expression(self) -> Node:
        return self._parse_pipeline()

    def _parse_value_expression(self) -> Node:
        """Parse an expression that does NOT consume pipeline operators.

        Used for parsing arguments to file operations (paths, data values),
        so that ``|>`` at the statement level is handled by the outer pipeline parser.
        """
        return self._parse_null_coalesce()

    def _parse_pipeline(self) -> Node:
        left = self._parse_null_coalesce()
        if self._check(TokenType.PIPE_ARROW):
            stages = [left]
            while self._check(TokenType.PIPE_ARROW):
                self._advance()
                stages.append(self._parse_pipeline_stage())
            return PipelineExpression(stages=stages, line=left.line, column=left.column)
        return left

    def _parse_pipeline_stage(self) -> Node:
        """Parse a pipeline stage: keyword-based operation or expression."""
        tok = self._current()

        if tok.type == TokenType.FILTER:
            self._advance()
            # Support both: `filter x => expr`  and  `filter(x => expr)`
            if self._check(TokenType.LPAREN):
                self._advance()  # consume '('
                lam = self._parse_lambda()
                self._expect(TokenType.RPAREN)
            else:
                lam = self._parse_lambda()
            lam.operation = "filter"
            return lam
        if tok.type == TokenType.MAP:
            self._advance()
            # Support both: `map x => expr`  and  `map(x => expr)`
            if self._check(TokenType.LPAREN):
                self._advance()
                lam = self._parse_lambda()
                self._expect(TokenType.RPAREN)
            else:
                lam = self._parse_lambda()
            lam.operation = "map"
            return lam
        if tok.type == TokenType.EACH:
            self._advance()
            if self._check(TokenType.LPAREN):
                self._advance()
                lam = self._parse_lambda()
                self._expect(TokenType.RPAREN)
            else:
                lam = self._parse_lambda()
            lam.operation = "each"
            return lam
        if tok.type == TokenType.REDUCE:
            self._advance()
            # reduce (acc, x) => expr  or  reduce init (acc, x) => expr
            # Check if next token is '(' — then it's the lambda directly (no init)
            # or if it's an expression — it's the initial value
            if self._check(TokenType.LPAREN):
                # (acc, x) => expr — use first element as seed, reduce rest
                lam = self._parse_multi_param_lambda()
                lam.operation = "reduce"
                return lam
            else:
                # init (acc, x) => expr
                # Parse init as a simple primary (literal/identifier) only,
                # to avoid `init (...)` being mistaken for a function call.
                init = self._parse_reduce_init()
                lam = self._parse_multi_param_lambda()
                lam.operation = "reduce_with_init"
                lam.init = init  # type: ignore[attr-defined]
                return lam
        if tok.type == TokenType.PARSE:
            return self._parse_parse_stmt()
        if tok.type == TokenType.WRITE:
            return self._parse_write()
        if tok.type == TokenType.READ:
            return self._parse_read()
        if tok.type == TokenType.TAKE:
            self._advance()
            count = self._parse_null_coalesce()  # use limited parse to not eat |> pipeline
            # Wrap as a TakeStage node — use an Identifier with metadata
            stage = Identifier(name="__take__", line=tok.line, column=tok.column)
            stage._take_count = count  # type: ignore[attr-defined]
            return stage
        if tok.type == TokenType.SKIP:
            self._advance()
            count = self._parse_null_coalesce()  # use limited parse to not eat |> pipeline
            stage = Identifier(name="__skip__", line=tok.line, column=tok.column)
            stage._skip_count = count  # type: ignore[attr-defined]
            return stage
        if tok.type == TokenType.GROUPBY:
            self._advance()
            if self._check(TokenType.LPAREN):
                self._advance()
                lam = self._parse_lambda()
                self._expect(TokenType.RPAREN)
            else:
                lam = self._parse_lambda()
            lam.operation = "groupBy"  # type: ignore[attr-defined]
            return lam
        if tok.type == TokenType.SORT_BY:
            self._advance()
            if self._check(TokenType.LPAREN):
                self._advance()
                lam = self._parse_lambda()
                self._expect(TokenType.RPAREN)
            else:
                lam = self._parse_lambda()
            lam.operation = "sortBy"  # type: ignore[attr-defined]
            return lam

        return self._parse_null_coalesce()

    def _parse_reduce_init(self) -> Node:
        """Parse a simple literal/identifier as reduce initial value.
        Deliberately stops before postfix to avoid `0 (a, b)` being parsed
        as a function call `0(a, b)`.
        """
        tok = self._current()
        if tok.type == TokenType.NUMBER:
            self._advance()
            val = float(tok.value)
            return NumberLiteral(value=val, line=tok.line, column=tok.column)
        if tok.type == TokenType.STRING:
            self._advance()
            return StringLiteral(value=tok.value, line=tok.line, column=tok.column)
        if tok.type == TokenType.BOOL:
            self._advance()
            return BoolLiteral(value=tok.value == "true", line=tok.line, column=tok.column)
        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            return Identifier(name=tok.value, line=tok.line, column=tok.column)
        if tok.type == TokenType.LBRACKET:
            return self._parse_array_literal()
        if tok.type == TokenType.LBRACE:
            return self._parse_object_literal()
        # Fallback (e.g. null, negative number)
        return self._parse_unary()

    def _parse_multi_param_lambda(self) -> MultiParamLambda:
        """Parse (acc, x) => expr"""
        tok = self._expect(TokenType.LPAREN)
        params: list[str] = []
        if not self._check(TokenType.RPAREN):
            params.append(self._expect_ident().value)
            while self._match(TokenType.COMMA):
                params.append(self._expect_ident().value)
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.FAT_ARROW)
        if self._check(TokenType.LBRACE):
            body: Node = self._parse_block()
        else:
            body = self._parse_lambda_body()
        return MultiParamLambda(params=params, body=body, line=tok.line, column=tok.column)

    def _parse_lambda(self) -> LambdaExpression:
        tok = self._current()
        param = self._expect_ident().value
        self._expect(TokenType.FAT_ARROW)
        # Lambda body: if '{' follows, parse as block; otherwise expression (incl. assignment)
        if self._check(TokenType.LBRACE):
            body: Node = self._parse_block()
        else:
            # Lambda body must NOT consume pipeline operators (|>) at this level.
            body = self._parse_lambda_body()
        return LambdaExpression(param=param, body=body, line=tok.line, column=tok.column)

    def _parse_lambda_body(self) -> Node:
        """Parse the non-block body of an arrow function.

        Allows assignment expressions (e.g. ``x => a = x``) in addition to
        regular expressions, while still not consuming pipeline operators (|>)
        at the outer level so that arrows can appear inside pipeline stages.
        """
        expr = self._parse_null_coalesce()

        # Simple assignment: name = value
        if self._check(TokenType.EQ) and isinstance(expr, Identifier):
            self._advance()
            value = self._parse_null_coalesce()
            return Assignment(name=expr.name, value=value, line=expr.line, column=expr.column)

        # Member assignment: obj.prop = value
        if self._check(TokenType.EQ) and isinstance(expr, MemberExpression):
            self._advance()
            value = self._parse_null_coalesce()
            return MemberAssignment(
                object=expr.object, property=expr.property, value=value,
                line=expr.line, column=expr.column,
            )

        # Index assignment: arr[i] = value
        if self._check(TokenType.EQ) and isinstance(expr, IndexExpression):
            self._advance()
            value = self._parse_null_coalesce()
            return IndexAssignment(
                object=expr.object, index=expr.index, value=value,
                line=expr.line, column=expr.column,
            )

        # Compound assignments: name += value, name -= value, etc.
        _compound_ops = {
            TokenType.PLUS_EQ: "+",
            TokenType.MINUS_EQ: "-",
            TokenType.STAR_EQ: "*",
            TokenType.SLASH_EQ: "/",
            TokenType.PERCENT_EQ: "%",
            TokenType.AMP_EQ: "&",
            TokenType.PIPE_EQ: "|",
            TokenType.CARET_EQ: "^",
            TokenType.LSHIFT_EQ: "<<",
            TokenType.RSHIFT_EQ: ">>",
            TokenType.AND_AND_EQ: "&&",
            TokenType.OR_OR_EQ: "||",
            TokenType.STAR_STAR_EQ: "**",
        }
        if self._current().type in _compound_ops and isinstance(expr, Identifier):
            op = _compound_ops[self._current().type]
            self._advance()
            value = self._parse_null_coalesce()
            return CompoundAssignment(
                name=expr.name, op=op, value=value, line=expr.line, column=expr.column
            )

        # Compound member assignments: obj.prop += value
        # Restricted to the operator set that the interpreter's CompoundMemberAssignment supports.
        _member_compound_ops = {
            TokenType.PLUS_EQ: "+",
            TokenType.MINUS_EQ: "-",
            TokenType.STAR_EQ: "*",
            TokenType.SLASH_EQ: "/",
            TokenType.AMP_EQ: "&",
            TokenType.PIPE_EQ: "|",
            TokenType.CARET_EQ: "^",
            TokenType.LSHIFT_EQ: "<<",
            TokenType.RSHIFT_EQ: ">>",
        }
        if self._current().type in _member_compound_ops and isinstance(expr, MemberExpression):
            op = _member_compound_ops[self._current().type]
            self._advance()
            value = self._parse_null_coalesce()
            return CompoundMemberAssignment(
                object=expr.object, property=expr.property, op=op, value=value,
                line=expr.line, column=expr.column,
            )

        return expr

    def _parse_null_coalesce(self) -> Node:
        """left ?? right"""
        left = self._parse_ternary()
        while self._check(TokenType.QUESTION_QUESTION):
            op_tok = self._advance()
            right = self._parse_ternary()
            left = NullCoalesceExpression(left=left, right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_ternary(self) -> Node:
        """condition ? then_expr : else_expr (right-associative for nesting)"""
        condition = self._parse_or()
        if self._check(TokenType.QUESTION):
            op_tok = self._advance()
            then_expr = self._parse_ternary()
            self._expect(TokenType.COLON)
            else_expr = self._parse_ternary()
            return TernaryExpression(
                condition=condition, then_expr=then_expr, else_expr=else_expr,
                line=op_tok.line, column=op_tok.column,
            )
        return condition

    def _parse_or(self) -> Node:
        left = self._parse_and()
        while self._check(TokenType.OR_OR):
            op_tok = self._advance()
            right = self._parse_and()
            left = BinaryExpression(left=left, op="||", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_and(self) -> Node:
        left = self._parse_bitwise_or()
        while self._check(TokenType.AND_AND):
            op_tok = self._advance()
            right = self._parse_bitwise_or()
            left = BinaryExpression(left=left, op="&&", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_bitwise_or(self) -> Node:
        left = self._parse_bitwise_xor()
        while self._check(TokenType.PIPE):
            op_tok = self._advance()
            right = self._parse_bitwise_xor()
            left = BinaryExpression(left=left, op="|", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_bitwise_xor(self) -> Node:
        left = self._parse_bitwise_and()
        while self._check(TokenType.CARET):
            op_tok = self._advance()
            right = self._parse_bitwise_and()
            left = BinaryExpression(left=left, op="^", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_bitwise_and(self) -> Node:
        left = self._parse_equality()
        while self._check(TokenType.AMP):
            op_tok = self._advance()
            right = self._parse_equality()
            left = BinaryExpression(left=left, op="&", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_shift(self) -> Node:
        left = self._parse_addition()
        while self._check(TokenType.LSHIFT, TokenType.RSHIFT, TokenType.URSHIFT):
            op_tok = self._advance()
            right = self._parse_addition()
            left = BinaryExpression(left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_equality(self) -> Node:
        left = self._parse_in()
        while self._check(TokenType.EQ_EQ, TokenType.BANG_EQ, TokenType.EQ_EQ_EQ, TokenType.BANG_EQ_EQ):
            op_tok = self._advance()
            right = self._parse_in()
            left = BinaryExpression(
                left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column
            )
        return left

    def _parse_in(self) -> Node:
        """item in collection  OR  item not in collection"""
        # Handle 'not expr in collection' as 'not (expr in collection)'
        if self._check(TokenType.NOT):
            op_tok = self._advance()  # consume 'not'
            inner_left = self._parse_comparison()
            if self._check(TokenType.IN):
                self._advance()  # consume 'in'
                right = self._parse_comparison()
                in_expr = InExpression(item=inner_left, collection=right, line=op_tok.line, column=op_tok.column)
                return UnaryExpression(op="!", operand=in_expr, line=op_tok.line, column=op_tok.column)
            # Plain 'not expr' without 'in'
            return UnaryExpression(op="!", operand=inner_left, line=op_tok.line, column=op_tok.column)
        left = self._parse_comparison()
        if self._check(TokenType.NOT) and self._peek().type == TokenType.IN:
            op_tok = self._advance()  # not
            self._advance()           # in
            right = self._parse_comparison()
            # "not in" → negate the InExpression
            inner = InExpression(item=left, collection=right, line=op_tok.line, column=op_tok.column)
            return UnaryExpression(op="!", operand=inner, line=op_tok.line, column=op_tok.column)
        if self._check(TokenType.IN):
            op_tok = self._advance()
            right = self._parse_comparison()
            return InExpression(item=left, collection=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_comparison(self) -> Node:
        left = self._parse_shift()
        while self._check(TokenType.LT, TokenType.GT, TokenType.LT_EQ, TokenType.GT_EQ):
            op_tok = self._advance()
            right = self._parse_shift()
            left = BinaryExpression(
                left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column
            )
        return left

    def _parse_addition(self) -> Node:
        left = self._parse_multiplication()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            right = self._parse_multiplication()
            left = BinaryExpression(
                left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column
            )
        return left

    def _parse_multiplication(self) -> Node:
        left = self._parse_power()
        while self._check(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self._advance()
            right = self._parse_power()
            left = BinaryExpression(
                left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column
            )
        return left

    def _parse_power(self) -> Node:
        """Right-associative: 2 ** 3 ** 2  →  2 ** (3 ** 2)"""
        base = self._parse_unary()
        if self._check(TokenType.STAR_STAR):
            op_tok = self._advance()
            exp = self._parse_power()   # right-assoc
            return BinaryExpression(left=base, op="**", right=exp, line=op_tok.line, column=op_tok.column)
        return base

    def _parse_unary(self) -> Node:
        if self._check(TokenType.BANG, TokenType.MINUS):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op=op_tok.value, operand=operand, line=op_tok.line, column=op_tok.column)
        if self._check(TokenType.PLUS):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op="+", operand=operand, line=op_tok.line, column=op_tok.column)
        if self._check(TokenType.NOT):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op="!", operand=operand, line=op_tok.line, column=op_tok.column)
        if self._check(TokenType.TILDE):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op="~", operand=operand, line=op_tok.line, column=op_tok.column)
        # void <expr> — evaluate and return null
        if self._check(TokenType.VOID):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op="void", operand=operand, line=op_tok.line, column=op_tok.column)
        # Prefix ++ / --
        if self._check(TokenType.PLUS_PLUS, TokenType.MINUS_MINUS):
            op_tok = self._advance()
            operand = self._parse_postfix()
            # prefix: treat as PostfixExpression with a "pre" flag encoded in op
            return PostfixExpression(
                operand=operand,
                op="pre" + op_tok.value,
                line=op_tok.line,
                column=op_tok.column,
            )
        return self._parse_postfix()

    def _parse_postfix(self) -> Node:
        expr = self._parse_primary()
        # Track the line of the last consumed token — used for ASI-like disambiguation:
        # a '[' on a different line is not a subscript on the previous expression.
        _last_line = self.tokens[self.pos - 1].line if self.pos > 0 else 0
        while True:
            if self._check(TokenType.DOT):
                _dot_tok = self._advance()
                _last_line = _dot_tok.line
                prop_tok = self._current()
                # Handle private field access: self.#name  (DOT followed by PRIVATE_IDENT)
                if prop_tok.type == TokenType.PRIVATE_IDENT:
                    self._advance()
                    prop = f"__private__{prop_tok.value}"
                else:
                    # Property can be any identifier or keyword used as a property
                    prop = self._advance().value
                _last_line = self.tokens[self.pos - 1].line
                if self._check(TokenType.LPAREN):
                    # Method call
                    self._advance()
                    args = self._parse_arg_list()
                    self._expect(TokenType.RPAREN)
                    _last_line = self.tokens[self.pos - 1].line
                    callee = MemberExpression(
                        object=expr, property=prop, line=prop_tok.line, column=prop_tok.column
                    )
                    expr = CallExpression(
                        callee=callee, args=args, line=prop_tok.line, column=prop_tok.column
                    )
                else:
                    expr = MemberExpression(
                        object=expr, property=prop, line=prop_tok.line, column=prop_tok.column
                    )
            elif self._check(TokenType.QUESTION_DOT):
                # Optional chaining: obj?.prop
                qt = self._advance()
                _last_line = qt.line
                if self._check(TokenType.LPAREN):
                    # Optional call: fn?.() — call fn only if non-null
                    self._advance()  # consume '('
                    args = self._parse_arg_list()
                    self._expect(TokenType.RPAREN)
                    _last_line = self.tokens[self.pos - 1].line
                    expr = OptionalCallExpression(callee=expr, args=args, line=qt.line, column=qt.column)
                elif self._check(TokenType.LBRACKET):
                    # Optional index: arr?.[i]
                    self._advance()  # consume [
                    index = self._parse_expression()
                    self._expect(TokenType.RBRACKET)
                    _last_line = self.tokens[self.pos - 1].line
                    expr = OptionalIndexExpression(object=expr, index=index, line=qt.line, column=qt.column)
                else:
                    prop_tok = self._current()
                    prop = self._advance().value
                    _last_line = self.tokens[self.pos - 1].line
                    if self._check(TokenType.LPAREN):
                        # Optional method call: obj?.method(args)
                        # Parsed as OptionalCallExpression so callee=None short-circuits the call
                        self._advance()
                        args = self._parse_arg_list()
                        self._expect(TokenType.RPAREN)
                        _last_line = self.tokens[self.pos - 1].line
                        callee = OptionalMemberExpression(
                            object=expr, property=prop, line=qt.line, column=qt.column
                        )
                        expr = OptionalCallExpression(
                            callee=callee, args=args, line=qt.line, column=qt.column
                        )
                    else:
                        expr = OptionalMemberExpression(
                            object=expr, property=prop, line=qt.line, column=qt.column
                        )
            elif self._check(TokenType.LBRACKET):
                # ASI: if '[' is on a different line from the end of the previous expression,
                # don't treat it as a subscript — it's the start of a new statement.
                if self._current().line != _last_line:
                    break
                op_tok = self._advance()
                _last_line = op_tok.line
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                _last_line = self.tokens[self.pos - 1].line
                expr = IndexExpression(object=expr, index=index, line=op_tok.line, column=op_tok.column)
            elif self._check(TokenType.LPAREN):
                op_tok = self._advance()
                _last_line = op_tok.line
                args = self._parse_arg_list()
                self._expect(TokenType.RPAREN)
                _last_line = self.tokens[self.pos - 1].line
                expr = CallExpression(callee=expr, args=args, line=op_tok.line, column=op_tok.column)
            elif self._check(TokenType.FAILED):
                # result.failed shorthand
                op_tok = self._advance()
                _last_line = op_tok.line
                expr = MemberExpression(
                    object=expr,
                    property="failed",
                    line=op_tok.line,
                    column=op_tok.column,
                )
            elif self._check(TokenType.PLUS_PLUS, TokenType.MINUS_MINUS):
                # Only apply postfix ++/-- to lvalues (Identifier or MemberExpression)
                if not isinstance(expr, (Identifier, MemberExpression)):
                    break
                op_tok = self._advance()
                _last_line = op_tok.line
                expr = PostfixExpression(
                    operand=expr,
                    op=op_tok.value,
                    line=op_tok.line,
                    column=op_tok.column,
                )
            elif self._check(TokenType.INSTANCEOF):
                inst_tok = self._advance()
                type_tok = self._advance()  # consume the type name token
                _last_line = type_tok.line
                expr = InstanceofExpression(
                    operand=expr,
                    type_name=type_tok.value,
                    line=inst_tok.line,
                    column=inst_tok.column,
                )
            elif self._check(TokenType.FSTRING):
                # Tagged template literal: tag`...`
                tmpl_tok = self._advance()
                _last_line = tmpl_tok.line
                # Token value is "processed\x00raw" from the lexer
                _parts = tmpl_tok.value.split("\x00", 1)
                _processed = _parts[0]
                _raw = _parts[1] if len(_parts) > 1 else _parts[0]
                expr = TaggedTemplateExpression(
                    tag=expr,
                    template=_processed,
                    raw_template=_raw,
                    line=tmpl_tok.line,
                    column=tmpl_tok.column,
                )
            elif self._check(TokenType.AS):
                # Type cast: expr as TypeName — only if next token is a known type name
                # (avoids conflict with `with expr as alias` and `import "mod" as alias`)
                _type_tokens = {
                    TokenType.NUMBER_TYPE, TokenType.INT_TYPE, TokenType.FLOAT_TYPE,
                    TokenType.BOOL_TYPE, TokenType.TEXT, TokenType.RESULT_TYPE,
                    TokenType.LIST_TYPE,
                }
                next_tok = self._peek()  # token after 'as'
                if (
                    next_tok.type in _type_tokens
                    or (next_tok.type == TokenType.IDENTIFIER and next_tok.value[0].isupper())
                ):
                    as_tok = self._advance()  # consume 'as'
                    type_tok = self._current()
                    self._advance()  # consume the type name
                    expr = TypeCastExpression(
                        operand=expr,
                        type_name=type_tok.value,
                        line=as_tok.line,
                        column=as_tok.column,
                    )
                else:
                    break
            else:
                break
        return expr

    def _parse_primary(self) -> Node:
        tok = self._current()

        # typeof <expr>
        if tok.type == TokenType.TYPEOF:
            self._advance()
            operand = self._parse_postfix()  # allow chaining: typeof items[0]
            return TypeofExpression(operand=operand, line=tok.line, column=tok.column)

        # debit / credit as expressions (inside transactions or let/var)
        if tok.type == TokenType.DEBIT:
            stmt = self._parse_debit()
            return stmt  # DebitStatement also acts as expression (returns dict)
        if tok.type == TokenType.CREDIT:
            stmt = self._parse_credit()
            return stmt  # CreditStatement also acts as expression (returns dict)

        # match as expression: let v = match x { ... }
        if tok.type == TokenType.MATCH:
            return self._parse_match()

        # with as expression: let v = with {x:1} { x + 1 }
        if tok.type == TokenType.WITH:
            return self._parse_with()

        # yield as expression: let r = yield 1
        if tok.type == TokenType.YIELD:
            return self._parse_yield()

        # class as expression: let X = class { ... } or let X = class Foo { ... }
        if tok.type == TokenType.CLASS:
            self._advance()  # consume 'class'
            name = "anonymous"
            if self._current().type in self._IDENTIFIER_LIKE:
                name = self._expect_ident().value
            superclass: str | None = None
            if self._check(TokenType.EXTENDS):
                self._advance()
                superclass = self._expect_ident().value
            body = self._parse_class_body()
            return ClassExpression(name=name, superclass=superclass, body=body, line=tok.line, column=tok.column)

        if tok.type == TokenType.STRING:
            self._advance()
            return StringLiteral(value=tok.value, line=tok.line, column=tok.column)

        if tok.type == TokenType.NUMBER:
            self._advance()
            if tok.value.endswith("n"):
                # BigInt literal: 42n → store as integer in NumberLiteral
                val = float(int(tok.value[:-1]))
                return NumberLiteral(value=val, raw=tok.value, line=tok.line, column=tok.column)
            val = float(tok.value)
            return NumberLiteral(value=val, raw=tok.value, line=tok.line, column=tok.column)

        if tok.type == TokenType.BOOL:
            self._advance()
            return BoolLiteral(value=tok.value == "true", line=tok.line, column=tok.column)

        if tok.type == TokenType.SECRET:
            self._advance()
            key = self._expect(TokenType.STRING).value
            return SecretLiteral(key=key, line=tok.line, column=tok.column)

        # Regex literal: /pattern/flags
        if tok.type == TokenType.REGEX:
            self._advance()
            raw = tok.value
            sep = raw.find("\x00")
            if sep >= 0:
                pattern = raw[:sep]
                flags = raw[sep + 1:]
            else:
                pattern = raw
                flags = ""
            return RegexLiteral(pattern=pattern, flags=flags, line=tok.line, column=tok.column)

        # Anonymous function expression: fn(params) { body } or fn(params) => expr
        if tok.type == TokenType.FN:
            # Only parse as expression if NOT followed by a named identifier
            # (named functions are statements; anonymous ones are expressions)
            if self._peek().type != TokenType.LPAREN:
                # It's a named function statement — shouldn't be here, fall through
                raise ParseError("Unexpected token in expression", tok)
            self._advance()  # consume fn
            self._expect(TokenType.LPAREN)
            params: list[tuple[str, str | None]] = []
            defaults: dict[str, Node] = {}
            rest_param: str | None = None
            while not self._check(TokenType.RPAREN) and not self._at_end():
                if self._check(TokenType.ELLIPSIS):
                    self._advance()
                    rest_tok = self._expect_ident()
                    rest_param = rest_tok.value
                    break
                if self._check(TokenType.LBRACE):
                    param_names, param_defaults = self._parse_dict_destruct_param()
                    params.append(("__destruct__:" + ",".join(param_names), None))
                    for _fname, _dflt in param_defaults.items():
                        defaults[f"__destruct_default__{_fname}"] = _dflt
                    if not self._match(TokenType.COMMA):
                        break
                    continue
                pname = self._expect_ident()
                ptype = None
                if self._match(TokenType.COLON):
                    ptype = self._parse_type_name()
                default_expr = None
                if self._match(TokenType.EQ):
                    default_expr = self._parse_null_coalesce()
                params.append((pname.value, ptype))
                if default_expr is not None:
                    defaults[pname.value] = default_expr
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RPAREN)
            return_type = None
            if self._match(TokenType.ARROW):
                return_type = self._parse_type_name()
            if self._check(TokenType.FAT_ARROW):
                self._advance()
                expr = self._parse_expression()
                fn_body = Block(body=[ReturnStatement(value=expr, line=tok.line, column=tok.column)])
            else:
                fn_body = self._parse_block()
            return AnonymousFunctionExpression(
                params=params, return_type=return_type, body=fn_body,
                defaults=defaults, rest_param=rest_param,
                line=tok.line, column=tok.column,
            )

        if tok.type == TokenType.LPAREN:
            self._advance()
            # Check for lambda: () => expr  or  (x) => expr  or  (a, b) => expr
            # Also supports destructured params: ([a,b]) => or ({name}) => or (a, [b,c]) =>
            saved_pos = self.pos
            try:
                params: list[str] = []
                rest_param: str | None = None
                # Collect params until RPAREN
                while not self._check(TokenType.RPAREN) and not self._at_end():
                    # Rest param: ...name
                    if self._check(TokenType.ELLIPSIS):
                        self._advance()
                        rest_param = self._expect_ident().value
                        break
                    # Array destructure param: [a, b, ...rest]
                    if self._check(TokenType.LBRACKET):
                        self._advance()
                        arr_names: list[str] = []
                        arr_rest: str | None = None
                        while not self._check(TokenType.RBRACKET) and not self._at_end():
                            if self._check(TokenType.ELLIPSIS):
                                self._advance()
                                arr_rest = self._expect_ident().value
                                break
                            arr_names.append(self._expect_ident().value)
                            if not self._match(TokenType.COMMA):
                                break
                        self._expect(TokenType.RBRACKET)
                        synth = "__array_destruct__:" + ",".join(arr_names)
                        if arr_rest:
                            synth += "..." + arr_rest
                        params.append(synth)
                    # Object destructure param: {name, key: alias, name = default}
                    elif self._check(TokenType.LBRACE):
                        self._advance()
                        obj_parts: list[str] = []
                        while not self._check(TokenType.RBRACE) and not self._at_end():
                            name_tok2 = self._expect_ident()
                            key2 = name_tok2.value
                            if self._match(TokenType.COLON):
                                alias_tok2 = self._expect_ident()
                                obj_parts.append(key2 + "|" + alias_tok2.value)
                            elif self._match(TokenType.EQ):
                                self._parse_expression()  # consume default (ignored for now)
                                obj_parts.append(key2)
                            else:
                                obj_parts.append(key2)
                            if not self._match(TokenType.COMMA):
                                break
                        self._expect(TokenType.RBRACE)
                        params.append("__destruct__:" + ",".join(obj_parts))
                    elif self._current().type in self._IDENTIFIER_LIKE:
                        params.append(self._advance().value)
                    else:
                        raise ParseError("expected param", self._current())
                    if not self._match(TokenType.COMMA):
                        break
                if self._check(TokenType.RPAREN):
                    self._advance()  # )
                    if self._check(TokenType.FAT_ARROW):
                        self._advance()  # =>
                        if self._check(TokenType.LBRACE):
                            body: Node = self._parse_block()
                        else:
                            body = self._parse_lambda_body()
                        # Attach rest param encoding if present
                        if rest_param is not None:
                            params.append("__rest__:" + rest_param)
                        if len(params) == 0:
                            # Zero-arg lambda: () => expr  — modelled as MultiParamLambda
                            # with an empty params list (no binding needed on call)
                            return MultiParamLambda(params=[], body=body,
                                                   line=tok.line, column=tok.column)
                        if len(params) == 1 and not params[0].startswith("__"):
                            return LambdaExpression(param=params[0], body=body,
                                                    line=tok.line, column=tok.column)
                        return MultiParamLambda(params=params, body=body,
                                               line=tok.line, column=tok.column)
            except Exception:
                pass
            # Not a lambda — restore and parse as grouped expression or comma expression
            self.pos = saved_pos
            expr = self._parse_expr_or_assignment()
            if self._check(TokenType.COMMA):
                # Comma operator: (a, b, c) — evaluates all, returns last
                expressions = [expr]
                while self._match(TokenType.COMMA):
                    expressions.append(self._parse_expr_or_assignment())
                self._expect(TokenType.RPAREN)
                return SequenceExpression(expressions=expressions,
                                          line=tok.line, column=tok.column)
            self._expect(TokenType.RPAREN)
            return expr
        if tok.type == TokenType.LBRACE:
            return self._parse_object_literal()

        if tok.type == TokenType.LBRACKET:
            return self._parse_array_literal()

        if tok.type == TokenType.FSTRING:
            self._advance()
            # Token value is "processed\x00raw" — FStringExpression uses the processed part
            _fstr_val = tok.value.split("\x00", 1)[0]
            return FStringExpression(raw_template=_fstr_val, line=tok.line, column=tok.column)

        if tok.type == TokenType.OK:
            self._advance()
            return Identifier(name="ok", line=tok.line, column=tok.column)

        # self keyword → Identifier
        if tok.type == TokenType.SELF:
            self._advance()
            return Identifier(name="self", line=tok.line, column=tok.column)

        # super keyword → SuperExpression
        if tok.type == TokenType.SUPER:
            self._advance()
            if self._check(TokenType.DOT):
                # super.method form → parse as member access on a special "super" identifier
                return Identifier(name="super", line=tok.line, column=tok.column)
            # super(args) form
            args: list[Node] = []
            if self._check(TokenType.LPAREN):
                self._advance()
                while not self._check(TokenType.RPAREN) and not self._at_end():
                    args.append(self._parse_expression())
                    if not self._match(TokenType.COMMA):
                        break
                self._expect(TokenType.RPAREN)
            return SuperExpression(args=args, line=tok.line, column=tok.column)

        # new ClassName(args) → CallExpression on ClassName
        if tok.type == TokenType.IDENTIFIER and tok.value == "new":
            self._advance()   # consume 'new'
            # next token is the class name identifier
            name_tok = self._expect_ident()
            return Identifier(name=name_tok.value, line=name_tok.line, column=name_tok.column)

        # null keyword → NullLiteral
        if tok.type == TokenType.IDENTIFIER and tok.value == "null":
            self._advance()
            return NullLiteral(line=tok.line, column=tok.column)

        # encode/http in expression context: encode("json", val) or http.get(url)
        if tok.type == TokenType.ENCODE:
            # Peek ahead: if next is '(' treat as function call (standard form)
            # If next is STRING, treat as keyword-style: encode "format" value
            if self._peek().type == TokenType.LPAREN:
                self._advance()
                return Identifier(name="encode", line=tok.line, column=tok.column)
            else:
                return self._parse_encode_stmt()
        if tok.type == TokenType.HTTP:
            # If followed by '.', parse as http.method "url" call expression
            if self._peek().type == TokenType.DOT:
                return self._parse_http_stmt()
            self._advance()
            return Identifier(name="http", line=tok.line, column=tok.column)

        # File/folder operations used as expressions: let result = read file "..."
        if tok.type == TokenType.READ:
            return self._parse_read()
        if tok.type == TokenType.WRITE:
            return self._parse_write()
        if tok.type == TokenType.MOVE:
            return self._parse_move()
        if tok.type == TokenType.COPY:
            return self._parse_copy()
        if tok.type == TokenType.DELETE:
            return self._parse_delete()
        if tok.type == TokenType.STREAM:
            return self._parse_stream()
        if tok.type == TokenType.PARSE:
            return self._parse_parse_stmt()
        # Statement keywords that can appear in lambda bodies / expression context
        if tok.type == TokenType.LOG:
            # `log` as a statement keyword: only when followed by a message expression.
            # When followed by `.`, `(`, operators, etc. `log` is treated as an identifier.
            _LOG_ARG_START = {
                TokenType.STRING, TokenType.FSTRING, TokenType.NUMBER,
                TokenType.IDENTIFIER, TokenType.LBRACKET, TokenType.LBRACE,
                TokenType.BOOL,
                TokenType.INFO, TokenType.WARN, TokenType.ERROR,
                TokenType.MINUS, TokenType.NOT,
            }
            if self._peek().type in _LOG_ARG_START:
                return self._parse_log()
            # Otherwise: treat as identifier
            self._advance()
            if self._check(TokenType.FAT_ARROW):
                self._advance()
                if self._check(TokenType.LBRACE):
                    body: Node = self._parse_block()
                else:
                    body = self._parse_lambda_body()
                return LambdaExpression(param="log", body=body, line=tok.line, column=tok.column)
            return Identifier(name="log", line=tok.line, column=tok.column)
        if tok.type == TokenType.VALIDATE:
            return self._parse_validate()
        if tok.type == TokenType.REDACT:
            return self._parse_redact()

        # FILE_TYPE and FOLDER_TYPE tokens used as identifiers in expression context
        if tok.type in (TokenType.FILE_TYPE, TokenType.FOLDER_TYPE):
            self._advance()
            return Identifier(name=tok.value, line=tok.line, column=tok.column)

        # await expr — unwrap SpryPromise; synchronous passthrough for non-Promise values
        if tok.type == TokenType.AWAIT:
            self._advance()
            operand = self._parse_postfix()
            return AwaitExpression(operand=operand, line=tok.line, column=tok.column)

        # result ok <expr>  or  result fail <expr>
        if tok.type == TokenType.RESULT:
            self._advance()  # consume 'result'
            if self._check(TokenType.OK):
                self._advance()  # consume 'ok'
                value_node = self._parse_null_coalesce()
                return ResultLiteral(is_ok=True, value=value_node,
                                     line=tok.line, column=tok.column)
            if self._check(TokenType.FAIL):
                self._advance()  # consume 'fail'
                value_node = self._parse_null_coalesce()
                return ResultLiteral(is_ok=False, value=value_node,
                                     line=tok.line, column=tok.column)
            # Bare 'result' — treat as identifier
            return Identifier(name="result", line=tok.line, column=tok.column)

        # Private field identifiers #name — used inside class methods
        if tok.type == TokenType.PRIVATE_IDENT:
            self._advance()
            return Identifier(name=f"__private__{tok.value}", line=tok.line, column=tok.column)

        # Allow identifiers and type-keywords used as identifiers
        if tok.type in self._IDENTIFIER_LIKE:
            self._advance()
            # Check for lambda: ident => expr  or  ident => { block }
            if self._check(TokenType.FAT_ARROW):
                self._advance()
                if self._check(TokenType.LBRACE):
                    body: Node = self._parse_block()
                else:
                    body = self._parse_lambda_body()
                return LambdaExpression(param=tok.value, body=body, line=tok.line, column=tok.column)
            return Identifier(name=tok.value, line=tok.line, column=tok.column)

        raise ParseError(f"Unexpected token in expression", tok)

    def _parse_object_literal(self) -> ObjectLiteral | DictComprehension:
        tok = self._expect(TokenType.LBRACE)
        pairs: dict[str, Node] = {}
        entries: list = []
        has_spread = False
        has_computed = False
        # Empty object
        if self._check(TokenType.RBRACE):
            self._advance()
            return ObjectLiteral(pairs={}, line=tok.line, column=tok.column)
        # Check for dict comprehension: {key_expr: val_expr for var in iterable [if cond]}
        # We speculatively parse the first key, then check for FOR
        if not self._check(TokenType.ELLIPSIS) and not self._check(TokenType.LBRACKET):
            saved_pos = self.pos
            try:
                key_tok = self._current()
                key_expr_node = self._parse_expression()
                if self._match(TokenType.COLON):
                    val_expr_node = self._parse_expression()
                    if self._check(TokenType.FOR):
                        # Dict comprehension: {k: v for x in ...}
                        self._advance()  # consume 'for'
                        comp_var_tok = self._expect_ident()
                        in_kw = self._current()
                        if in_kw.type == TokenType.IN or (in_kw.type == TokenType.IDENTIFIER and in_kw.value == "in"):
                            self._advance()
                        else:
                            raise ParseError("Expected 'in' in dict comprehension", in_kw)
                        comp_iterable = self._parse_expression()
                        comp_condition: Node | None = None
                        if self._check(TokenType.IF):
                            self._advance()
                            comp_condition = self._parse_expression()
                        self._expect(TokenType.RBRACE)
                        return DictComprehension(
                            key_expr=key_expr_node,
                            val_expr=val_expr_node,
                            var=comp_var_tok.value,
                            iterable=comp_iterable,
                            condition=comp_condition,
                            line=tok.line, column=tok.column,
                        )
                    # Not a comprehension; restore and fall through
                    # to regular object parsing with first pair already parsed
                    # Reset and re-parse (simpler than threading through)
                    self.pos = saved_pos
                else:
                    self.pos = saved_pos
            except ParseError:
                self.pos = saved_pos
        while not self._check(TokenType.RBRACE) and not self._at_end():
            if self._check(TokenType.ELLIPSIS):
                has_spread = True
                spread_tok = self._advance()
                expr = self._parse_expression()
                spread = SpreadElement(expr=expr, line=spread_tok.line, column=spread_tok.column)
                entries.append((None, spread))
            elif self._check(TokenType.LBRACKET):
                # Computed key: { [expr]: value }
                has_computed = True
                self._advance()  # consume '['
                key_expr = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                if self._check(TokenType.LPAREN):
                    # Computed method shorthand: { [key](...params) { body } }
                    self._advance()  # consume '('
                    cmp_params: list[tuple[str, str | None]] = []
                    cmp_defaults: dict = {}
                    cmp_rest: str | None = None
                    while not self._check(TokenType.RPAREN) and not self._at_end():
                        if self._check(TokenType.ELLIPSIS):
                            self._advance()
                            cmp_rest = self._expect_ident().value
                            break
                        pname = self._expect_ident().value
                        if self._match(TokenType.EQ):
                            cmp_defaults[pname] = self._parse_expression()
                        cmp_params.append((pname, None))
                        if not self._match(TokenType.COMMA):
                            break
                    self._expect(TokenType.RPAREN)
                    cmp_body = self._parse_block()
                    cmp_fn = AnonymousFunctionExpression(
                        params=cmp_params, return_type=None, body=cmp_body,
                        defaults=cmp_defaults, rest_param=cmp_rest,
                        line=key_expr.line, column=key_expr.column,
                    )
                    entries.append(("__computed__", (key_expr, cmp_fn)))
                else:
                    self._expect(TokenType.COLON)
                    value = self._parse_expression()
                    # Use a placeholder key in pairs; runtime will evaluate key_expr
                    entries.append(("__computed__", (key_expr, value)))
            else:
                key_tok = self._current()
                key = self._advance().value
                # Object getter: get propName() { ... }
                if (key in ("get", "set")
                        and self._current().type in self._IDENTIFIER_LIKE
                        and not self._check(TokenType.COLON)
                        and not self._check(TokenType.LPAREN)
                        and not self._check(TokenType.COMMA)
                        and not self._check(TokenType.RBRACE)):
                    accessor_kind = key
                    name_tok2 = self._expect_ident()
                    self._expect(TokenType.LPAREN)
                    if accessor_kind == "get":
                        self._expect(TokenType.RPAREN)
                        acc_body = self._parse_block()
                        fn_val = AnonymousFunctionExpression(
                            params=[], return_type=None, body=acc_body,
                            defaults={}, rest_param=None,
                            line=name_tok2.line, column=name_tok2.column,
                        )
                        getter_key = f"__getter__{name_tok2.value}"
                        pairs[getter_key] = fn_val
                        entries.append((getter_key, fn_val))
                    else:  # set
                        param_name = self._expect_ident().value
                        self._expect(TokenType.RPAREN)
                        acc_body = self._parse_block()
                        fn_val = AnonymousFunctionExpression(
                            params=[(param_name, None)], return_type=None, body=acc_body,
                            defaults={}, rest_param=None,
                            line=name_tok2.line, column=name_tok2.column,
                        )
                        setter_key = f"__setter__{name_tok2.value}"
                        pairs[setter_key] = fn_val
                        entries.append((setter_key, fn_val))
                elif self._check(TokenType.LPAREN):
                    # Method shorthand: { greet(x) { return x } }
                    self._advance()  # consume '('
                    params: list[tuple[str, str | None]] = []
                    defaults: dict[str, Any] = {}
                    rest_param: str | None = None
                    while not self._check(TokenType.RPAREN) and not self._at_end():
                        p_tok = self._current()
                        if p_tok.type == TokenType.ELLIPSIS:
                            self._advance()
                            rest_param = self._expect_ident().value
                            break
                        pname = self._expect_ident().value
                        if self._match(TokenType.EQ):
                            defaults[pname] = self._parse_expression()
                        params.append((pname, None))
                        if not self._match(TokenType.COMMA):
                            break
                    self._expect(TokenType.RPAREN)
                    fn_body = self._parse_block()
                    value = AnonymousFunctionExpression(
                        params=params, return_type=None, body=fn_body,
                        defaults=defaults, rest_param=rest_param,
                        line=key_tok.line, column=key_tok.column,
                    )
                    pairs[key] = value
                    entries.append((key, value))
                elif self._match(TokenType.COLON):
                    value = self._parse_expression()
                    pairs[key] = value
                    entries.append((key, value))
                else:
                    # Shorthand: { name } → { name: name }
                    value = Identifier(name=key, line=key_tok.line, column=key_tok.column)
                    pairs[key] = value
                    entries.append((key, value))
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE)
        result = ObjectLiteral(pairs=pairs, line=tok.line, column=tok.column)
        if has_spread or has_computed:
            result.entries = entries
        return result

    def _parse_array_literal(self) -> ArrayLiteral | ListComprehension:
        tok = self._expect(TokenType.LBRACKET)
        items: list[Node] = []
        if self._check(TokenType.RBRACKET):
            self._advance()
            return ArrayLiteral(items=[], line=tok.line, column=tok.column)
        # Parse first expression — may begin a comprehension
        if self._check(TokenType.ELLIPSIS):
            spread_tok = self._advance()
            first_expr = self._parse_expression()
            first: Node = SpreadElement(expr=first_expr, line=spread_tok.line, column=spread_tok.column)
        else:
            first = self._parse_expression()
        # List comprehension: [expr for var in iterable [if cond]]
        if self._check(TokenType.FOR):
            self._advance()  # consume 'for'
            var_tok = self._expect_ident()
            # Expect 'in'
            in_kw = self._current()
            if in_kw.type == TokenType.IN or (in_kw.type == TokenType.IDENTIFIER and in_kw.value == "in"):
                self._advance()
            else:
                raise ParseError("Expected 'in' in list comprehension", in_kw)
            iterable = self._parse_expression()
            condition: Node | None = None
            if self._check(TokenType.IF):
                self._advance()
                condition = self._parse_expression()
            self._expect(TokenType.RBRACKET)
            return ListComprehension(
                expr=first, var=var_tok.value, iterable=iterable,
                condition=condition, line=tok.line, column=tok.column,
            )
        # Regular array literal
        items.append(first)
        if not self._match(TokenType.COMMA):
            self._expect(TokenType.RBRACKET)
            return ArrayLiteral(items=items, line=tok.line, column=tok.column)
        while not self._check(TokenType.RBRACKET) and not self._at_end():
            if self._check(TokenType.ELLIPSIS):
                spread_tok = self._advance()
                expr = self._parse_expression()
                items.append(SpreadElement(expr=expr, line=spread_tok.line, column=spread_tok.column))
            else:
                items.append(self._parse_expression())
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACKET)
        return ArrayLiteral(items=items, line=tok.line, column=tok.column)

    def _parse_arg_list(self) -> list[Node]:
        args: list[Node] = []
        while not self._check(TokenType.RPAREN) and not self._at_end():
            if self._check(TokenType.ELLIPSIS):
                # Spread arg: ...expr
                ellipsis_tok = self._advance()
                expr = self._parse_expression()
                args.append(SpreadElement(expr=expr, line=ellipsis_tok.line, column=ellipsis_tok.column))
            else:
                args.append(self._parse_expression())
            if not self._match(TokenType.COMMA):
                break
        return args

    def _parse_type_name(self) -> str:
        """Parse a type annotation — may be a keyword or identifier."""
        tok = self._advance()
        return tok.value
