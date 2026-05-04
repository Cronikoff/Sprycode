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
class DeclarationList(Node):
    """A list of declarations from ``var a=1, b=2`` — executed in the *current* env (no new scope)."""
    body: list[Node] = field(default_factory=list)


@dataclass
class LetDeclaration(Node):
    """let <name>[: <type>] = <value>  (mutable block-scoped binding)
    const <name> = <value>            (immutable binding, is_const=True)
    """
    name: str = ""
    type_annotation: str | None = None
    value: Node | None = None
    privacy: str | None = None  # "private" | "sensitive" | None
    is_const: bool = False  # True when declared with 'const'


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
    defaults: dict[str, "Node"] = field(default_factory=dict)  # param -> default expr
    rest_param: str | None = None  # name of the ...rest parameter
    is_generator: bool = False     # fn* generator function
    is_async: bool = False         # async fn — wraps return in SpryPromise


@dataclass
class YieldStatement(Node):
    """yield [<value>]  or  yield* <iterable>"""
    value: "Node | None" = None
    delegate: bool = False  # True for yield*


@dataclass
class ExportStatement(Node):
    """export <declaration>  — marks a declaration as exported"""
    declaration: "Node | None" = None


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
    """try { <body> } catch <err_name> { <handler> } [finally { <finally_block> }]"""
    body: Block | None = None
    error_name: str = ""
    handler: Block | None = None
    finally_block: "Block | None" = None
    error_pattern: "Node | None" = None  # ListDestructure/ObjectDestructure for catch ({a,b}) / catch ([a,b])


@dataclass
class DoWhileStatement(Node):
    """do { <body> } while <condition>"""
    body: Block | None = None
    condition: "Node | None" = None


@dataclass
class TypeofExpression(Node):
    """typeof <expr>  — returns a string describing the type"""
    operand: "Node | None" = None


@dataclass
class InstanceofExpression(Node):
    """<expr> instanceof <TypeName>  — returns bool"""
    operand: "Node | None" = None
    type_name: str = ""


@dataclass
class SpawnStatement(Node):
    """spawn <call_expr>  — fire-and-forget async execution"""
    call: "Node | None" = None


@dataclass
class DebitStatement(Node):
    """debit account <name> amount <expr>"""
    account: "Node | None" = None
    amount: "Node | None" = None


@dataclass
class CreditStatement(Node):
    """credit account <name> amount <expr>"""
    account: "Node | None" = None
    amount: "Node | None" = None


@dataclass
class WebSocketStatement(Node):
    """websocket <name> <url> { <body> }"""
    name: str = ""
    url: "Node | None" = None
    body: "Block | None" = None


@dataclass
class WithStatement(Node):
    """with <expr> as <name> { <body> }"""
    expr: "Node | None" = None
    alias: str = ""
    body: "Block | None" = None


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
    """{ key: value, ...spread, ... }
    entries is an ordered list of (key_or_None, value_or_spread_node)
    For regular pairs: (key: str, value: Node)
    For spread: (None, SpreadElement)
    """
    pairs: dict[str, Node] = field(default_factory=dict)
    # ordered entries — used when spread is present; supersedes pairs
    entries: list = field(default_factory=list)  # list of (str | None, Node)


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
class SequenceExpression(Node):
    """Comma expression: (a, b, c) — evaluates each expression in order and returns the last value."""
    expressions: list = field(default_factory=list)


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
    """for <var> [, <var2>] in <iterable> { <body> }"""
    var: str = ""
    vars: list[str] = field(default_factory=list)  # for destructured: for i, v in ...
    iterable: Node | None = None
    body: Block | None = None
    label: str | None = None  # set by LabeledStatement when wrapping this loop
    is_async: bool = False  # for await...of loops
    _list_destruct_node: "Any | None" = None  # for let [a,b] of ...
    _obj_destruct_node: "Any | None" = None   # for let {a,b} of ...


@dataclass
class ForCStyleStatement(Node):
    """for <init>; <condition>; <update> { <body> }"""
    init: "Node | None" = None
    condition: "Node | None" = None
    update: "Node | None" = None
    body: "Block | None" = None
    label: str | None = None


@dataclass
class WhileStatement(Node):
    """while <condition> { <body> }"""
    condition: Node | None = None
    body: Block | None = None
    label: str | None = None  # set by LabeledStatement when wrapping this loop


@dataclass
class BreakStatement(Node):
    """break [label]"""
    label: str | None = None


@dataclass
class ContinueStatement(Node):
    """continue [label]"""
    label: str | None = None


@dataclass
class LabeledStatement(Node):
    """label: statement"""
    label: str = ""
    body: "Node | None" = None


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


# ---------------------------------------------------------------------------
# New features: match, repeat..until, destructuring, assert, import, reduce
# ---------------------------------------------------------------------------


@dataclass
class MatchArm(Node):
    """pattern => body_stmt"""
    pattern: Node | None = None    # expression to compare, or None for wildcard
    is_wildcard: bool = False      # _ arm
    range_end: Node | None = None  # if set, this is a range arm: pattern..range_end
    body: Block | None = None
    guard: Node | None = None      # optional `when condition` guard clause


@dataclass
class SuperExpression(Node):
    """super(args) or super.method(args)"""
    args: list = field(default_factory=list)       # for super(args) — constructor call
    method: str | None = None                       # for super.method — method name


@dataclass
class MatchStatement(Node):
    """match <expr> { pattern => stmt ... }"""
    subject: Node | None = None
    arms: list[MatchArm] = field(default_factory=list)


@dataclass
class RepeatUntilStatement(Node):
    """repeat { <body> } until <condition>"""
    body: Block | None = None
    condition: Node | None = None


@dataclass
class AssertStatement(Node):
    """assert <condition> [, <message>]"""
    condition: Node | None = None
    message: Node | None = None


@dataclass
class ImportStatement(Node):
    """import <name> [as <alias>]  |  import { a, b } from <name>"""
    module: str = ""
    alias: str | None = None
    names: list[str] = field(default_factory=list)   # destructured names


@dataclass
class ListDestructure(Node):
    """let [a, b, c] = expr  — list destructuring"""
    names: list[str] = field(default_factory=list)
    value: Node | None = None
    mutable: bool = False
    rest_name: str | None = None  # name of the ...rest element, if any
    defaults: dict[str, "Node"] = field(default_factory=dict)  # name -> default expr
    nested: dict[int, "Node"] = field(default_factory=dict)  # index -> nested destructure node


@dataclass
class ObjectDestructure(Node):
    """let {a, b} = expr  — object destructuring"""
    names: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)  # {name: alias}
    nested: dict[str, "Node"] = field(default_factory=dict)  # {name: nested destructure node}
    value: Node | None = None
    mutable: bool = False
    defaults: dict[str, "Node"] = field(default_factory=dict)  # name/alias -> default expr
    rest_name: str | None = None  # ...rest element, if any


@dataclass
class ListDestructureAssignment(Node):
    """[a, b] = expr — list destructuring assignment (without let/var)"""
    names: list[str] = field(default_factory=list)
    value: Node | None = None
    rest_name: str | None = None  # ...rest element


@dataclass
class MultiParamLambda(Node):
    """(acc, x) => expr  — multi-param lambda used in reduce etc."""
    params: list[str] = field(default_factory=list)
    body: Node | None = None


@dataclass
class SwitchStatement(Node):
    """switch <expr> { case <val>: <body> ... default: <body> }"""
    subject: Node | None = None
    cases: list["SwitchCase"] = field(default_factory=list)
    default_body: "Block | None" = None


@dataclass
class SwitchCase(Node):
    """case <value>: <body>"""
    value: Node | None = None
    body: "Block | None" = None


@dataclass
class AnonymousFunctionExpression(Node):
    """fn(<params>) { <body> }  — anonymous function used as a value"""
    params: list[tuple[str, str | None]] = field(default_factory=list)
    return_type: str | None = None
    body: "Block | None" = None
    defaults: dict[str, "Node"] = field(default_factory=dict)
    rest_param: str | None = None


@dataclass
class ListComprehension(Node):
    """[<expr> for <var> in <iterable> [if <cond>]]"""
    expr: Node | None = None
    var: str = ""
    iterable: Node | None = None
    condition: Node | None = None  # optional filter


@dataclass
class DictComprehension(Node):
    """{<key_expr>: <val_expr> for <var> in <iterable> [if <cond>]}"""
    key_expr: Node | None = None
    val_expr: Node | None = None
    var: str = ""
    iterable: Node | None = None
    condition: Node | None = None  # optional filter


@dataclass
class RegexLiteral(Node):
    """/<pattern>/<flags>  — regular expression literal"""
    pattern: str = ""
    flags: str = ""


@dataclass
class PostfixExpression(Node):
    """<expr>++  or  <expr>--"""
    operand: Node | None = None
    op: str = ""   # "++" or "--"


# ---------------------------------------------------------------------------
# Round 5: throw, enum, struct, class, optional chaining, default/rest params
# ---------------------------------------------------------------------------


@dataclass
class ThrowStatement(Node):
    """throw <expr>  — raise a user error"""
    value: Node | None = None


@dataclass
class OptionalMemberExpression(Node):
    """obj?.prop  — returns null if obj is null/None"""
    object: Node | None = None
    property: str = ""


@dataclass
class OptionalIndexExpression(Node):
    """obj?.[index]  — returns null if obj is null/None"""
    object: Node | None = None
    index: Node | None = None


@dataclass
class EnumDeclaration(Node):
    """enum Color { Red, Green, Blue }"""
    name: str = ""
    variants: list[str] = field(default_factory=list)


@dataclass
class StructDeclaration(Node):
    """struct Point { x: Number, y: Number }"""
    name: str = ""
    fields: list[tuple[str, str | None]] = field(default_factory=list)


@dataclass
class ClassDeclaration(Node):
    """class Foo { var n = 0; fn method() { ... } }"""
    name: str = ""
    superclass: str | None = None
    interfaces: list[str] = field(default_factory=list)
    mixins: list[str] = field(default_factory=list)
    body: "Block | None" = None


@dataclass
class InterfaceDeclaration(Node):
    """interface Printable { fn print() }"""
    name: str = ""
    body: "Block | None" = None


# ---------------------------------------------------------------------------
# Assignment to member / index paths
# ---------------------------------------------------------------------------


@dataclass
class MemberAssignment(Node):
    """obj.prop = value  (or self.prop = value)"""
    object: Node | None = None
    property: str = ""
    value: Node | None = None


@dataclass
class CompoundMemberAssignment(Node):
    """obj.prop += | -= | *= | /= value"""
    object: Node | None = None
    property: str = ""
    op: str = ""   # "+", "-", "*", "/"
    value: Node | None = None


@dataclass
class IndexAssignment(Node):
    """obj[index] = value"""
    object: Node | None = None
    index: Node | None = None
    value: Node | None = None



@dataclass
class TypeCastExpression(Node):
    """expr as TypeName — cast an expression to a named type"""
    operand: Node | None = None
    type_name: str = ""


@dataclass
class GetterDeclaration(Node):
    """get propName() { ... } inside a class body"""
    name: str = ""
    body: "Block | None" = None


@dataclass
class SetterDeclaration(Node):
    """set propName(param) { ... } inside a class body"""
    name: str = ""
    param: str = ""
    body: "Block | None" = None


@dataclass
class ResultLiteral(Node):
    """result ok <value>  or  result fail <message>"""
    is_ok: bool = True
    value: Node | None = None


@dataclass
class TaggedTemplateExpression(Node):
    """tag`template ${expr}` — a tagged template literal call"""
    tag: "Node | None" = None       # the tag function expression
    template: str = ""              # the processed template string (escape sequences resolved)
    raw_template: str = ""          # the raw template string (escape sequences preserved)


@dataclass
class ClassExpression(Node):
    """Anonymous/named class expression: let X = class Foo { ... }"""
    name: str = "anonymous"
    superclass: str | None = None
    body: "Block | None" = None


@dataclass
class AwaitExpression(Node):
    """await <expr> — unwraps SpryPromise; synchronous passthrough in SpryCode."""
    operand: "Node | None" = None


@dataclass
class OptionalCallExpression(Node):
    """fn?.() — calls fn only if it is not null/None; returns null otherwise."""
    callee: "Node | None" = None
    args: list = field(default_factory=list)


@dataclass
class ComputedMethodDeclaration(Node):
    """[Symbol.iterator]() { ... } — class method with computed name."""
    key: "Node | None" = None        # expression yielding the key
    params: list = field(default_factory=list)
    body: "Block | None" = None
    is_static: bool = False
    is_generator: bool = False
    is_async: bool = False
    is_getter: bool = False          # get [expr]() { ... }
    is_setter: bool = False          # set [expr](v) { ... }
    defaults: dict = field(default_factory=dict)
    rest_param: "str | None" = None



