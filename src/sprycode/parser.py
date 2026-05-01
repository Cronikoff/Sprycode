"""
SpryCode Parser

Recursive descent parser that builds an AST from a token stream.
"""

from __future__ import annotations

from typing import Sequence

from .ast_nodes import (
    AdapterDeclaration,
    AllowStatement,
    AppDeclaration,
    ArrayLiteral,
    Assignment,
    AtomicStatement,
    BinaryExpression,
    Block,
    BoolLiteral,
    BreakStatement,
    CallExpression,
    CompensateStatement,
    CompoundAssignment,
    CompressStatement,
    ConnectorDeclaration,
    ContinueStatement,
    CopyStatement,
    CreateStatement,
    DeleteStatement,
    DenyStatement,
    ExpectStatement,
    ExtractStatement,
    ForStatement,
    FraudCheckStatement,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    IndexExpression,
    LambdaExpression,
    LetDeclaration,
    LogStatement,
    MemberExpression,
    MoveStatement,
    Node,
    NullLiteral,
    NumberLiteral,
    ObjectLiteral,
    ParseStatement,
    PipelineExpression,
    PrivateDataDeclaration,
    Program,
    ReadStatement,
    RedactStatement,
    ReturnStatement,
    ScheduleStatement,
    SecretLiteral,
    SensitiveDataDeclaration,
    SleepStatement,
    StopStatement,
    StreamStatement,
    StringLiteral,
    SyncStatement,
    TaskDeclaration,
    TestBlock,
    TransactionStatement,
    TryCatchStatement,
    UnaryExpression,
    UseStatement,
    ValidateStatement,
    VarDeclaration,
    WatchStatement,
    WhileStatement,
    WriteStatement,
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
        if tok.type == TokenType.VAR:
            return self._parse_var()
        if tok.type == TokenType.FN:
            return self._parse_fn()
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
            return BreakStatement(line=tok.line, column=tok.column)
        if tok.type == TokenType.CONTINUE:
            self._advance()
            return ContinueStatement(line=tok.line, column=tok.column)
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

        # Expression statement or assignment
        return self._parse_expr_or_assignment()

    def _parse_block(self) -> Block:
        tok = self._expect(TokenType.LBRACE)
        body: list[Node] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        self._expect(TokenType.RBRACE)
        return Block(body=body, line=tok.line, column=tok.column)

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

    def _parse_let(self) -> LetDeclaration:
        tok = self._expect(TokenType.LET)
        name_tok = self._expect_ident()
        type_annotation = None
        if self._match(TokenType.COLON):
            type_annotation = self._parse_type_name()
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        return LetDeclaration(
            name=name_tok.value,
            type_annotation=type_annotation,
            value=value,
            line=tok.line,
            column=tok.column,
        )

    def _parse_var(self) -> VarDeclaration:
        tok = self._expect(TokenType.VAR)
        name_tok = self._expect_ident()
        type_annotation = None
        if self._match(TokenType.COLON):
            type_annotation = self._parse_type_name()
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        return VarDeclaration(
            name=name_tok.value,
            type_annotation=type_annotation,
            value=value,
            line=tok.line,
            column=tok.column,
        )

    def _parse_fn(self) -> FunctionDeclaration:
        tok = self._expect(TokenType.FN)
        name_tok = self._expect_ident()
        self._expect(TokenType.LPAREN)
        params: list[tuple[str, str | None]] = []
        while not self._check(TokenType.RPAREN) and not self._at_end():
            pname = self._expect_ident()
            ptype = None
            if self._match(TokenType.COLON):
                ptype = self._parse_type_name()
            params.append((pname.value, ptype))
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
                line=tok.line,
                column=tok.column,
            )

        body = self._parse_block()
        return FunctionDeclaration(
            name=name_tok.value,
            params=params,
            return_type=return_type,
            body=body,
            line=tok.line,
            column=tok.column,
        )

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
        then_block = self._parse_block()
        else_block = None
        if self._match(TokenType.ELSE):
            if self._check(TokenType.IF):
                # else if — wrap in a block
                nested = self._parse_if()
                else_block = Block(body=[nested], line=nested.line, column=nested.column)
            else:
                else_block = self._parse_block()
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
        self._expect(TokenType.CATCH)
        err_name = self._expect(TokenType.IDENTIFIER).value
        handler = self._parse_block()
        return TryCatchStatement(
            body=body, error_name=err_name, handler=handler, line=tok.line, column=tok.column
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
        if level_tok.type in (TokenType.INFO, TokenType.WARN, TokenType.ERROR, TokenType.IDENTIFIER):
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

    def _parse_for(self) -> ForStatement:
        tok = self._expect(TokenType.FOR)
        var_tok = self._expect_ident()
        self._expect(TokenType.IN)
        iterable = self._parse_value_expression()
        body = self._parse_block()
        return ForStatement(
            var=var_tok.value, iterable=iterable, body=body,
            line=tok.line, column=tok.column,
        )

    def _parse_while(self) -> WhileStatement:
        tok = self._expect(TokenType.WHILE)
        condition = self._parse_value_expression()
        body = self._parse_block()
        return WhileStatement(
            condition=condition, body=body,
            line=tok.line, column=tok.column,
        )

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

    def _parse_expr_or_assignment(self) -> Node:
        expr = self._parse_pipeline()

        # Simple assignment: name = value
        if self._check(TokenType.EQ) and isinstance(expr, Identifier):
            self._advance()
            value = self._parse_expression()
            return Assignment(
                name=expr.name, value=value, line=expr.line, column=expr.column
            )

        # Compound assignments: name += value, name -= value, name *= value, name /= value
        _compound_ops = {
            TokenType.PLUS_EQ: "+",
            TokenType.MINUS_EQ: "-",
            TokenType.STAR_EQ: "*",
            TokenType.SLASH_EQ: "/",
        }
        if self._current().type in _compound_ops and isinstance(expr, Identifier):
            op = _compound_ops[self._current().type]
            self._advance()
            value = self._parse_expression()
            return CompoundAssignment(
                name=expr.name, op=op, value=value, line=expr.line, column=expr.column
            )

        return expr

    def _parse_expression(self) -> Node:
        return self._parse_pipeline()

    def _parse_value_expression(self) -> Node:
        """Parse an expression that does NOT consume pipeline operators.

        Used for parsing arguments to file operations (paths, data values),
        so that ``|>`` at the statement level is handled by the outer pipeline parser.
        """
        return self._parse_or()

    def _parse_pipeline(self) -> Node:
        left = self._parse_or()
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
            lam = self._parse_lambda()
            lam.operation = "filter"
            return lam
        if tok.type == TokenType.MAP:
            self._advance()
            lam = self._parse_lambda()
            lam.operation = "map"
            return lam
        if tok.type == TokenType.EACH:
            self._advance()
            lam = self._parse_lambda()
            lam.operation = "each"
            return lam
        if tok.type == TokenType.PARSE:
            return self._parse_parse_stmt()
        if tok.type == TokenType.WRITE:
            return self._parse_write()
        if tok.type == TokenType.READ:
            return self._parse_read()

        return self._parse_or()

    def _parse_lambda(self) -> LambdaExpression:
        tok = self._current()
        param = self._expect_ident().value
        self._expect(TokenType.FAT_ARROW)
        # Lambda body must NOT consume pipeline operators (|>) at this level.
        # Use _parse_or() instead of _parse_expression() to stop before |>.
        body = self._parse_or()
        return LambdaExpression(param=param, body=body, line=tok.line, column=tok.column)

    def _parse_or(self) -> Node:
        left = self._parse_and()
        while self._check(TokenType.OR_OR):
            op_tok = self._advance()
            right = self._parse_and()
            left = BinaryExpression(left=left, op="||", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_and(self) -> Node:
        left = self._parse_equality()
        while self._check(TokenType.AND_AND):
            op_tok = self._advance()
            right = self._parse_equality()
            left = BinaryExpression(left=left, op="&&", right=right, line=op_tok.line, column=op_tok.column)
        return left

    def _parse_equality(self) -> Node:
        left = self._parse_comparison()
        while self._check(TokenType.EQ_EQ, TokenType.BANG_EQ):
            op_tok = self._advance()
            right = self._parse_comparison()
            left = BinaryExpression(
                left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column
            )
        return left

    def _parse_comparison(self) -> Node:
        left = self._parse_addition()
        while self._check(TokenType.LT, TokenType.GT, TokenType.LT_EQ, TokenType.GT_EQ):
            op_tok = self._advance()
            right = self._parse_addition()
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
        left = self._parse_unary()
        while self._check(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self._advance()
            right = self._parse_unary()
            left = BinaryExpression(
                left=left, op=op_tok.value, right=right, line=op_tok.line, column=op_tok.column
            )
        return left

    def _parse_unary(self) -> Node:
        if self._check(TokenType.BANG, TokenType.MINUS):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op=op_tok.value, operand=operand, line=op_tok.line, column=op_tok.column)
        if self._check(TokenType.NOT):
            op_tok = self._advance()
            operand = self._parse_unary()
            return UnaryExpression(op="!", operand=operand, line=op_tok.line, column=op_tok.column)
        return self._parse_postfix()

    def _parse_postfix(self) -> Node:
        expr = self._parse_primary()
        while True:
            if self._check(TokenType.DOT):
                self._advance()
                prop_tok = self._current()
                # Property can be any identifier or keyword used as a property
                prop = self._advance().value
                if self._check(TokenType.LPAREN):
                    # Method call
                    self._advance()
                    args = self._parse_arg_list()
                    self._expect(TokenType.RPAREN)
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
            elif self._check(TokenType.LBRACKET):
                op_tok = self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                expr = IndexExpression(object=expr, index=index, line=op_tok.line, column=op_tok.column)
            elif self._check(TokenType.LPAREN):
                op_tok = self._advance()
                args = self._parse_arg_list()
                self._expect(TokenType.RPAREN)
                expr = CallExpression(callee=expr, args=args, line=op_tok.line, column=op_tok.column)
            elif self._check(TokenType.FAILED):
                # result.failed shorthand
                self._advance()
                expr = MemberExpression(
                    object=expr,
                    property="failed",
                    line=self._current().line,
                    column=self._current().column,
                )
            else:
                break
        return expr

    def _parse_primary(self) -> Node:
        tok = self._current()

        if tok.type == TokenType.STRING:
            self._advance()
            return StringLiteral(value=tok.value, line=tok.line, column=tok.column)

        if tok.type == TokenType.NUMBER:
            self._advance()
            val = float(tok.value)
            return NumberLiteral(value=val, raw=tok.value, line=tok.line, column=tok.column)

        if tok.type == TokenType.BOOL:
            self._advance()
            return BoolLiteral(value=tok.value == "true", line=tok.line, column=tok.column)

        if tok.type == TokenType.SECRET:
            self._advance()
            key = self._expect(TokenType.STRING).value
            return SecretLiteral(key=key, line=tok.line, column=tok.column)

        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        if tok.type == TokenType.LBRACE:
            return self._parse_object_literal()

        if tok.type == TokenType.LBRACKET:
            return self._parse_array_literal()

        if tok.type == TokenType.OK:
            self._advance()
            return Identifier(name="ok", line=tok.line, column=tok.column)

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
            return self._parse_log()
        if tok.type == TokenType.VALIDATE:
            return self._parse_validate()
        if tok.type == TokenType.REDACT:
            return self._parse_redact()

        # FILE_TYPE and FOLDER_TYPE tokens used as identifiers in expression context
        if tok.type in (TokenType.FILE_TYPE, TokenType.FOLDER_TYPE):
            self._advance()
            return Identifier(name=tok.value, line=tok.line, column=tok.column)

        # Allow identifiers and type-keywords used as identifiers
        if tok.type in self._IDENTIFIER_LIKE:
            self._advance()
            # Check for lambda: ident => expr
            if self._check(TokenType.FAT_ARROW):
                self._advance()
                body = self._parse_expression()
                return LambdaExpression(param=tok.value, body=body, line=tok.line, column=tok.column)
            return Identifier(name=tok.value, line=tok.line, column=tok.column)

        raise ParseError(f"Unexpected token in expression", tok)

    def _parse_object_literal(self) -> ObjectLiteral:
        tok = self._expect(TokenType.LBRACE)
        pairs: dict[str, Node] = {}
        while not self._check(TokenType.RBRACE) and not self._at_end():
            key_tok = self._current()
            key = self._advance().value
            self._expect(TokenType.COLON)
            value = self._parse_expression()
            pairs[key] = value
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACE)
        return ObjectLiteral(pairs=pairs, line=tok.line, column=tok.column)

    def _parse_array_literal(self) -> ArrayLiteral:
        tok = self._expect(TokenType.LBRACKET)
        items: list[Node] = []
        while not self._check(TokenType.RBRACKET) and not self._at_end():
            items.append(self._parse_expression())
            if not self._match(TokenType.COMMA):
                break
        self._expect(TokenType.RBRACKET)
        return ArrayLiteral(items=items, line=tok.line, column=tok.column)

    def _parse_arg_list(self) -> list[Node]:
        args: list[Node] = []
        while not self._check(TokenType.RPAREN) and not self._at_end():
            args.append(self._parse_expression())
            if not self._match(TokenType.COMMA):
                break
        return args

    def _parse_type_name(self) -> str:
        """Parse a type annotation — may be a keyword or identifier."""
        tok = self._advance()
        return tok.value
