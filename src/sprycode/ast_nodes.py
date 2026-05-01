"""
SpryCode AST Nodes

Defines the abstract syntax tree node types for SpryCode programs.
All nodes are immutable dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """Base class for all AST nodes."""
    line: int = field(default=0, kw_only=True)
    column: int = field(default=0, kw_only=True)


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


@dataclass
class Program(Node):
    """Root node of a SpryCode program."""
    body: list[Node] = field(default_factory=list)


@dataclass
class AppDeclaration(Node):
    """app <Name> version <version_string>"""
    name: str = ""
    version: str = ""


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass
class Block(Node):
    """A block of statements enclosed in { }."""
    body: list[Node] = field(default_factory=list)


@dataclass
class LetDeclaration(Node):
    """let <name>[: <type>] = <value>"""
    name: str = ""
    type_annotation: str | None = None
    value: Node | None = None
    privacy: str | None = None  # "private" | "sensitive" | None


@dataclass
class VarDeclaration(Node):
    """var <name>[: <type>] = <value>"""
    name: str = ""
    type_annotation: str | None = None
    value: Node | None = None


@dataclass
class Assignment(Node):
    """<name> = <value>"""
    name: str = ""
    value: Node | None = None


@dataclass
class CompoundAssignment(Node):
    """<name> += | -= | *= | /= <value>"""
    name: str = ""
    op: str = ""     # "+", "-", "*", "/"
    value: Node | None = None


@dataclass
class FunctionDeclaration(Node):
    """fn <name>(<params>) [-> <return_type>] { <body> }"""
    name: str = ""
    params: list[tuple[str, str | None]] = field(default_factory=list)
    return_type: str | None = None
    body: Block | None = None
    short_form: bool = False   # fn double(x) => x * 2


@dataclass
class TaskDeclaration(Node):
    """task <name> { <body> }"""
    name: str = ""
    body: Block | None = None


@dataclass
class ReturnStatement(Node):
    """return [<value>]"""
    value: Node | None = None


@dataclass
class StopStatement(Node):
    """stop"""
    pass


@dataclass
class IfStatement(Node):
    """if <condition> { <then> } [else { <else_> }]"""
    condition: Node | None = None
    then_block: Block | None = None
    else_block: Block | None = None


@dataclass
class TryCatchStatement(Node):
    """try { <body> } catch <err_name> { <handler> }"""
    body: Block | None = None
    error_name: str = ""
    handler: Block | None = None


@dataclass
class AtomicStatement(Node):
    """atomic { <body> }"""
    body: Block | None = None


@dataclass
class TransactionStatement(Node):
    """transaction <target> { <body> }"""
    target: Node | None = None
    body: Block | None = None
    compensate: Block | None = None


@dataclass
class CompensateStatement(Node):
    """compensate { <body> }"""
    body: Block | None = None


# ---------------------------------------------------------------------------
# Permission / Privacy
# ---------------------------------------------------------------------------


@dataclass
class AllowStatement(Node):
    """allow <permission_path> [<argument>]"""
    permission: str = ""
    argument: str | None = None


@dataclass
class DenyStatement(Node):
    """deny <permission_path> [<argument>]"""
    permission: str = ""
    argument: str | None = None


@dataclass
class PrivateDataDeclaration(Node):
    """private data <name>: <type>"""
    name: str = ""
    type_annotation: str = ""


@dataclass
class SensitiveDataDeclaration(Node):
    """sensitive data <name>: <type>"""
    name: str = ""
    type_annotation: str = ""


# ---------------------------------------------------------------------------
# File / Folder / Data Operations
# ---------------------------------------------------------------------------


@dataclass
class MoveStatement(Node):
    """move file|folder <source> to <destination> [verify checksum <alg>] [preserve metadata] [parallel <n>] [retry <n>]"""
    target_type: str = "file"  # "file" | "folder" | "files"
    source: Node | None = None
    destination: Node | None = None
    verify_checksum: str | None = None
    preserve_metadata: bool = False
    parallel: int | None = None
    retry: int | None = None
    where_clause: Node | None = None


@dataclass
class CopyStatement(Node):
    """copy file|folder <source> to <destination>"""
    target_type: str = "file"
    source: Node | None = None
    destination: Node | None = None
    verify_checksum: str | None = None
    preserve_metadata: bool = False


@dataclass
class ReadStatement(Node):
    """read file <path>"""
    target_type: str = "file"
    path: Node | None = None


@dataclass
class WriteStatement(Node):
    """write file <path> with <data>"""
    target_type: str = "file"
    path: Node | None = None
    data: Node | None = None


@dataclass
class DeleteStatement(Node):
    """delete file|folder <path>"""
    target_type: str = "file"
    path: Node | None = None


@dataclass
class StreamStatement(Node):
    """stream file|folder <source> |> ..."""
    target_type: str = "file"
    source: Node | None = None
    pipeline: list[Node] = field(default_factory=list)


@dataclass
class SyncStatement(Node):
    """sync folder <src> with <dst> [mode mirror] [compare checksum] [encrypt true]"""
    source: Node | None = None
    destination: Node | None = None
    mode: str | None = None
    compare: str | None = None
    encrypt: bool = False


@dataclass
class WatchStatement(Node):
    """watch folder <path>"""
    path: Node | None = None


# ---------------------------------------------------------------------------
# Data manipulation
# ---------------------------------------------------------------------------


@dataclass
class ParseStatement(Node):
    """parse <format> <data>"""
    format: str = ""
    data: Node | None = None


@dataclass
class ValidateStatement(Node):
    """validate <data> using <schema>"""
    data: Node | None = None
    schema: Node | None = None


@dataclass
class RedactStatement(Node):
    """redact <data> fields [<field_list>]"""
    data: Node | None = None
    fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


@dataclass
class LogStatement(Node):
    """log info|warn|error <message>"""
    level: str = "info"
    message: Node | None = None


# ---------------------------------------------------------------------------
# Adapter / Connector
# ---------------------------------------------------------------------------


@dataclass
class UseStatement(Node):
    """use adapter <name> [as <alias>]"""
    kind: str = "adapter"
    name: str = ""
    alias: str | None = None


@dataclass
class AdapterDeclaration(Node):
    """adapter <name> [sandboxed] { <body> }"""
    name: str = ""
    sandboxed: bool = False
    body: Block | None = None


@dataclass
class ConnectorDeclaration(Node):
    """connector <name> { <body> }"""
    name: str = ""
    body: Block | None = None


# ---------------------------------------------------------------------------
# Fraud check
# ---------------------------------------------------------------------------


@dataclass
class FraudCheckStatement(Node):
    """fraud check transaction <id> { reason <r> case <c> scope <s> redact ... }"""
    target: Node | None = None
    reason: str = ""
    case_id: str = ""
    scope: str = "minimal"
    redact_personal: bool = False


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass
class BinaryExpression(Node):
    """<left> <op> <right>"""
    left: Node | None = None
    op: str = ""
    right: Node | None = None


@dataclass
class UnaryExpression(Node):
    """<op> <operand>"""
    op: str = ""
    operand: Node | None = None


@dataclass
class CallExpression(Node):
    """<callee>(<args>)"""
    callee: Node | None = None
    args: list[Node] = field(default_factory=list)
    kwargs: dict[str, Node] = field(default_factory=dict)


@dataclass
class MemberExpression(Node):
    """<object>.<property>"""
    object: Node | None = None
    property: str = ""


@dataclass
class IndexExpression(Node):
    """<object>[<index>]"""
    object: Node | None = None
    index: Node | None = None


@dataclass
class PipelineExpression(Node):
    """<left> |> <right>"""
    stages: list[Node] = field(default_factory=list)


@dataclass
class LambdaExpression(Node):
    """<param> => <body>"""
    param: str = ""
    body: Node | None = None
    operation: str = "map"  # "map" | "filter" | "each"


@dataclass
class ObjectLiteral(Node):
    """{ key: value, ... }"""
    pairs: dict[str, Node] = field(default_factory=dict)


@dataclass
class ArrayLiteral(Node):
    """[item, ...]  — items may include SpreadElement nodes"""
    items: list[Node] = field(default_factory=list)


@dataclass
class SpreadElement(Node):
    """...expr  — used inside array/object literals"""
    expr: Node | None = None


@dataclass
class TernaryExpression(Node):
    """condition ? then_expr : else_expr"""
    condition: Node | None = None
    then_expr: Node | None = None
    else_expr: Node | None = None


@dataclass
class NullCoalesceExpression(Node):
    """left ?? right  — returns left if not null/None, else right"""
    left: Node | None = None
    right: Node | None = None


@dataclass
class InExpression(Node):
    """item in collection  — membership test"""
    item: Node | None = None
    collection: Node | None = None


@dataclass
class FStringExpression(Node):
    """f\"Hello {name}!\"  — interpolated string
    raw_template: the template string with {expr} markers as-is.
    """
    raw_template: str = ""


# ---------------------------------------------------------------------------
# Literals / Identifiers
# ---------------------------------------------------------------------------


@dataclass
class Identifier(Node):
    """A variable or function name."""
    name: str = ""


@dataclass
class StringLiteral(Node):
    value: str = ""


@dataclass
class NumberLiteral(Node):
    value: float = 0.0
    raw: str = ""


@dataclass
class BoolLiteral(Node):
    value: bool = False


@dataclass
class NullLiteral(Node):
    pass


@dataclass
class SecretLiteral(Node):
    """secret "ENV_VAR_NAME" """
    key: str = ""


# ---------------------------------------------------------------------------
# Loops
# ---------------------------------------------------------------------------


@dataclass
class ForStatement(Node):
    """for <var> in <iterable> { <body> }"""
    var: str = ""
    iterable: Node | None = None
    body: Block | None = None


@dataclass
class WhileStatement(Node):
    """while <condition> { <body> }"""
    condition: Node | None = None
    body: Block | None = None


@dataclass
class BreakStatement(Node):
    """break"""
    pass


@dataclass
class ContinueStatement(Node):
    """continue"""
    pass


# ---------------------------------------------------------------------------
# File creation / compression
# ---------------------------------------------------------------------------


@dataclass
class CreateStatement(Node):
    """create file <path> [with <content>]"""
    target_type: str = "file"
    path: Node | None = None
    content: Node | None = None


@dataclass
class CompressStatement(Node):
    """compress folder <path> to <archive>"""
    source: Node | None = None
    destination: Node | None = None


@dataclass
class ExtractStatement(Node):
    """extract <archive> to <folder>"""
    source: Node | None = None
    destination: Node | None = None


# ---------------------------------------------------------------------------
# Time / scheduling
# ---------------------------------------------------------------------------


@dataclass
class SleepStatement(Node):
    """sleep <duration>[s|ms]"""
    duration: Node | None = None
    unit: str = "s"   # "s" | "ms"


@dataclass
class ScheduleStatement(Node):
    """schedule daily at "HH:MM" { <body> }"""
    frequency: str = "daily"
    at_time: str = ""
    body: Block | None = None


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------


@dataclass
class TestBlock(Node):
    """test "name" { <body> }"""
    name: str = ""
    body: Block | None = None


@dataclass
class ExpectStatement(Node):
    """expect [not] <condition>  |  expect exists <path>  |  expect denied { }  |  expect rollback { }"""
    condition: Node | None = None
    negated: bool = False
    kind: str = "truthy"   # "truthy" | "exists" | "denied" | "rollback"
    block: "Block | None" = None
