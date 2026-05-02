"""
Tests for Phase 4+ features:
- Function default parameters
- Function rest parameters
- Dict-destructuring function params
- Match range arms
- HTTP helper extensions (put, delete, patch, head)
- SQL adapter (sqlite3)
- Structured audit logger
"""

from __future__ import annotations

import pytest

from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.permissions import PermissionSet
from sprycode.runtime.stdlib import AuditLogger, SpryLogger, SpryResult, SqlAdapter


def run(source: str, permissions: PermissionSet | None = None, log_output: list | None = None) -> Interpreter:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    log_out = log_output if log_output is not None else []
    logger = SpryLogger(output=log_out)
    perms = permissions or PermissionSet()
    interp = Interpreter(logger=logger, permissions=perms)
    interp.run(program)
    return interp


def eval_expr(source: str) -> object:
    full = f"let __result = {source}"
    interp = run(full)
    return interp.globals.get("__result")


# ---------------------------------------------------------------------------
# Function default parameters
# ---------------------------------------------------------------------------


class TestFunctionDefaultParams:
    def test_default_string(self):
        interp = run('fn greet(name = "World") { return "Hello, " + name }\nlet r = greet()')
        assert interp.globals.get("r") == "Hello, World"

    def test_default_overridden(self):
        interp = run('fn greet(name = "World") { return "Hello, " + name }\nlet r = greet("Alice")')
        assert interp.globals.get("r") == "Hello, Alice"

    def test_default_number(self):
        interp = run("fn add(x, y = 10) { return x + y }\nlet r = add(5)")
        assert interp.globals.get("r") == 15

    def test_default_number_both_supplied(self):
        interp = run("fn add(x, y = 10) { return x + y }\nlet r = add(5, 3)")
        assert interp.globals.get("r") == 8

    def test_multiple_defaults(self):
        interp = run('fn box(w = 1, h = 2, d = 3) { return w * h * d }\nlet r = box()')
        assert interp.globals.get("r") == 6

    def test_partial_defaults(self):
        interp = run('fn box(w = 1, h = 2, d = 3) { return w * h * d }\nlet r = box(4, 5)')
        assert interp.globals.get("r") == 60  # 4 * 5 * 3

    def test_short_form_with_default(self):
        interp = run("fn double(x = 2) => x * 2\nlet r = double()")
        assert interp.globals.get("r") == 4

    def test_default_bool(self):
        interp = run("fn toggle(flag = false) { return flag }\nlet r = toggle()")
        assert interp.globals.get("r") is False

    def test_default_null(self):
        interp = run("fn get(val = null) { return val }\nlet r = get()")
        assert interp.globals.get("r") is None

    def test_default_expression(self):
        interp = run("let base = 5\nfn inc(n = base + 1) { return n }\nlet r = inc()")
        assert interp.globals.get("r") == 6


# ---------------------------------------------------------------------------
# Function rest parameters
# ---------------------------------------------------------------------------


class TestFunctionRestParams:
    def test_rest_collects_extra_args(self):
        interp = run("fn sum(...nums) {\n    var total = 0\n    for n in nums { total += n }\n    return total\n}\nlet r = sum(1, 2, 3, 4, 5)")
        assert interp.globals.get("r") == 15

    def test_rest_with_leading_param(self):
        interp = run("fn first_and_rest(first, ...rest) {\n    return rest.length\n}\nlet r = first_and_rest(1, 2, 3, 4)")
        assert interp.globals.get("r") == 3

    def test_rest_empty(self):
        interp = run("fn collect(...items) { return items.length }\nlet r = collect()")
        assert interp.globals.get("r") == 0

    def test_rest_is_list(self):
        interp = run("fn collect(...items) { return items }\nlet r = collect(10, 20, 30)")
        assert interp.globals.get("r") == [10, 20, 30]

    def test_rest_with_leading_params(self):
        interp = run("fn build(sep, ...parts) {\n    var result = \"\"\n    for p in parts { result += p + sep }\n    return result\n}\nlet r = build(\"-\", \"a\", \"b\", \"c\")")
        assert interp.globals.get("r") == "a-b-c-"


# ---------------------------------------------------------------------------
# Dict-destructuring function params
# ---------------------------------------------------------------------------


class TestDictDestructuringParams:
    def test_basic_destruct(self):
        interp = run('fn greet({name}) { return "Hello " + name }\nlet r = greet({name: "Alice"})')
        assert interp.globals.get("r") == "Hello Alice"

    def test_multiple_fields(self):
        interp = run("fn area({width, height}) { return width * height }\nlet r = area({width: 4, height: 5})")
        assert interp.globals.get("r") == 20

    def test_missing_field_is_null(self):
        interp = run('fn maybe({x}) { return x ?? "default" }\nlet r = maybe({y: 1})')
        assert interp.globals.get("r") == "default"


# ---------------------------------------------------------------------------
# Match range arms
# ---------------------------------------------------------------------------


class TestMatchRangeArms:
    def test_range_match_low(self):
        log_output = []
        run('match 2 {\n    1..5 => log info "low"\n    6..10 => log info "high"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("low" in l for l in log_output)

    def test_range_match_high(self):
        log_output = []
        run('match 8 {\n    1..5 => log info "low"\n    6..10 => log info "high"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("high" in l for l in log_output)

    def test_range_match_boundary_inclusive(self):
        log_output = []
        run('match 5 {\n    1..5 => log info "in range"\n    _ => log info "out"\n}', log_output=log_output)
        assert any("in range" in l for l in log_output)

    def test_range_no_match_falls_to_wildcard(self):
        log_output = []
        run('match 99 {\n    1..10 => log info "low"\n    _ => log info "other"\n}', log_output=log_output)
        assert any("other" in l for l in log_output)

    def test_range_with_variable(self):
        log_output = []
        run('let score = 75\nmatch score {\n    0..59 => log info "fail"\n    60..79 => log info "pass"\n    80..100 => log info "excellent"\n    _ => log info "unknown"\n}', log_output=log_output)
        assert any("pass" in l for l in log_output)

    def test_range_exact_match_first_boundary(self):
        log_output = []
        run('match 1 {\n    1..3 => log info "yes"\n    _ => log info "no"\n}', log_output=log_output)
        assert any("yes" in l for l in log_output)


# ---------------------------------------------------------------------------
# HTTP helper extensions
# ---------------------------------------------------------------------------


class TestHttpHelperExtensions:
    def test_http_put_method_exists(self):
        interp = run("let h = http")
        h = interp.globals.get("h")
        assert hasattr(h, "put")

    def test_http_delete_method_exists(self):
        interp = run("let h = http")
        h = interp.globals.get("h")
        assert hasattr(h, "delete")

    def test_http_patch_method_exists(self):
        interp = run("let h = http")
        h = interp.globals.get("h")
        assert hasattr(h, "patch")

    def test_http_head_method_exists(self):
        interp = run("let h = http")
        h = interp.globals.get("h")
        assert hasattr(h, "head")

    def test_http_put_no_permission_fails(self):
        """PUT without network.request permission raises PermissionError."""
        from sprycode.permissions import PermissionError as SpryPermError
        perms = PermissionSet()
        perms.enable_secure_mode()
        interp = Interpreter(permissions=perms)
        h = interp.globals.get("http")
        with pytest.raises(SpryPermError):
            h.put("https://example.com", {"key": "val"})

    def test_http_delete_no_permission_fails(self):
        """DELETE without network.request permission raises PermissionError."""
        from sprycode.permissions import PermissionError as SpryPermError
        perms = PermissionSet()
        perms.enable_secure_mode()
        interp = Interpreter(permissions=perms)
        h = interp.globals.get("http")
        with pytest.raises(SpryPermError):
            h.delete("https://example.com")

    def test_http_request_returns_spry_result(self):
        """http._request with a bad URL returns a failed SpryResult (not exception)."""
        perms = PermissionSet()
        perms.add_allow("network.request", "https://localhost:0")
        interp = Interpreter(permissions=perms)
        h = interp.globals.get("http")
        result = h.get("https://localhost:0")
        assert isinstance(result, SpryResult)
        assert not result.ok


# ---------------------------------------------------------------------------
# SQL Adapter
# ---------------------------------------------------------------------------


class TestSqlAdapter:
    def test_connect_memory(self):
        adapter = SqlAdapter()
        conn = adapter.connect(":memory:")
        assert isinstance(conn, dict)
        assert "__sql_conn__" in conn

    def test_execute_create_table(self):
        adapter = SqlAdapter()
        conn = adapter.connect(":memory:")
        result = adapter.execute(conn, "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        assert isinstance(result, SpryResult)
        assert result.ok

    def test_execute_insert_and_query(self):
        adapter = SqlAdapter()
        conn = adapter.connect(":memory:")
        adapter.execute(conn, "CREATE TABLE users (id INTEGER, name TEXT)")
        adapter.execute(conn, "INSERT INTO users VALUES (?, ?)", [1, "Alice"])
        adapter.execute(conn, "INSERT INTO users VALUES (?, ?)", [2, "Bob"])
        rows = adapter.query(conn, "SELECT * FROM users ORDER BY id")
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"

    def test_query_with_params(self):
        adapter = SqlAdapter()
        conn = adapter.connect(":memory:")
        adapter.execute(conn, "CREATE TABLE items (id INTEGER, val TEXT)")
        adapter.execute(conn, "INSERT INTO items VALUES (1, 'x')")
        adapter.execute(conn, "INSERT INTO items VALUES (2, 'y')")
        rows = adapter.query(conn, "SELECT * FROM items WHERE id = ?", [1])
        assert len(rows) == 1
        assert rows[0]["val"] == "x"

    def test_close(self):
        adapter = SqlAdapter()
        conn = adapter.connect(":memory:")
        result = adapter.close(conn)
        assert result.ok

    def test_sql_accessible_in_sprycode(self):
        """sql is accessible as a global identifier."""
        interp = run("let s = sql")
        s = interp.globals.get("s")
        assert isinstance(s, SqlAdapter)

    def test_sql_connect_and_query_via_sprycode(self):
        """Run sql operations via SpryCode syntax."""
        source = """
let db = sql.connect(":memory:")
sql.execute(db, "CREATE TABLE t (n INTEGER)")
sql.execute(db, "INSERT INTO t VALUES (42)")
let rows = sql.query(db, "SELECT * FROM t")
let first = rows.first
"""
        interp = run(source)
        first = interp.globals.get("first")
        assert isinstance(first, dict)
        assert first.get("n") == 42

    def test_sql_invalid_conn_returns_error(self):
        """Passing a non-handle to execute returns a failed SpryResult."""
        adapter = SqlAdapter()
        result = adapter.execute({"bad": "handle"}, "SELECT 1")
        assert isinstance(result, SpryResult)
        assert not result.ok

    def test_use_adapter_sql_registers(self):
        """use adapter sql makes sql accessible as its own identifier."""
        log_output: list = []
        interp = run('use adapter sql as mydb', log_output=log_output)
        # mydb should be bound to the SqlAdapter
        mydb = interp.globals.get("mydb")
        assert isinstance(mydb, SqlAdapter)


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------


class TestAuditLogger:
    def test_log_entry(self):
        audit = AuditLogger()
        entry = audit.log(action="file.read", resource="/data/report.csv")
        assert entry["action"] == "file.read"
        assert entry["resource"] == "/data/report.csv"
        assert entry["outcome"] == "success"
        assert "timestamp" in entry

    def test_entries_returns_all(self):
        audit = AuditLogger()
        audit.log("login", actor="alice")
        audit.log("read", actor="alice", resource="/data")
        audit.log("write", actor="bob", resource="/output")
        entries = audit.entries()
        assert len(entries) == 3

    def test_filter_by_action(self):
        audit = AuditLogger()
        audit.log("read", resource="/a")
        audit.log("write", resource="/b")
        audit.log("read", resource="/c")
        reads = audit.filter(action="read")
        assert len(reads) == 2

    def test_filter_by_actor(self):
        audit = AuditLogger()
        audit.log("read", actor="alice")
        audit.log("write", actor="bob")
        alice_entries = audit.filter(actor="alice")
        assert len(alice_entries) == 1
        assert alice_entries[0]["actor"] == "alice"

    def test_filter_by_outcome(self):
        audit = AuditLogger()
        audit.log("read", outcome="success")
        audit.log("write", outcome="failure")
        audit.log("delete", outcome="failure")
        failures = audit.filter(outcome="failure")
        assert len(failures) == 2

    def test_export_json(self):
        import json
        audit = AuditLogger()
        audit.log("test", resource="/test")
        exported = audit.export_json()
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["action"] == "test"

    def test_output_mirror(self):
        mirror: list = []
        audit = AuditLogger(output=mirror)
        audit.log("deploy", resource="app-v2")
        assert len(mirror) == 1
        assert mirror[0]["action"] == "deploy"

    def test_audit_accessible_in_sprycode(self):
        """audit is accessible as a global identifier in SpryCode."""
        interp = run("let a = audit")
        a = interp.globals.get("a")
        assert isinstance(a, AuditLogger)

    def test_audit_log_via_sprycode(self):
        """audit.log() can be called from SpryCode."""
        source = """
let entry = audit.log("file.read", "/data/report.csv")
let action = entry.action
"""
        interp = run(source)
        assert interp.globals.get("action") == "file.read"

    def test_audit_entries_via_sprycode(self):
        """audit.entries() returns a list from SpryCode."""
        source = """
audit.log("step1")
audit.log("step2")
let items = audit.entries()
let count = items.length
"""
        interp = run(source)
        assert interp.globals.get("count") == 2

    def test_audit_filter_via_sprycode(self):
        """audit.filter() works from SpryCode."""
        source = """
audit.log("read")
audit.log("write")
audit.log("read")
let reads = audit.filter("read")
let n = reads.length
"""
        interp = run(source)
        assert interp.globals.get("n") == 2

    def test_audit_export_json_via_sprycode(self):
        """audit.export_json() returns a JSON string from SpryCode."""
        source = """
audit.log("deploy")
let j = audit.export_json()
"""
        interp = run(source)
        import json
        j = interp.globals.get("j")
        assert j is not None
        data = json.loads(j)
        assert len(data) == 1
        assert data[0]["action"] == "deploy"


# ---------------------------------------------------------------------------
# Integration: function defaults + SQL + audit together
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_function_defaults_with_logic(self):
        source = """
fn classify(score, passing = 60, excellent = 90) {
    if score >= excellent {
        return "excellent"
    }
    if score >= passing {
        return "pass"
    }
    return "fail"
}
let r1 = classify(95)
let r2 = classify(75)
let r3 = classify(45)
let r4 = classify(75, 70)
"""
        interp = run(source)
        assert interp.globals.get("r1") == "excellent"
        assert interp.globals.get("r2") == "pass"
        assert interp.globals.get("r3") == "fail"
        assert interp.globals.get("r4") == "pass"

    def test_rest_params_variadic_log(self):
        log_output: list = []
        source = """
fn logAll(...messages) {
    for msg in messages {
        log info msg
    }
}
logAll("hello", "world", "sprycode")
"""
        run(source, log_output=log_output)
        texts = [l.split("] ")[-1] for l in log_output]
        assert "hello" in texts
        assert "world" in texts
        assert "sprycode" in texts

    def test_match_range_grade(self):
        log_output: list = []
        source = """
fn grade(score) {
    match score {
        90..100 => log info "A"
        80..89 => log info "B"
        70..79 => log info "C"
        60..69 => log info "D"
        0..59 => log info "F"
        _ => log info "invalid"
    }
}
grade(85)
grade(72)
grade(55)
"""
        run(source, log_output=log_output)
        msgs = [l.split("] ")[-1] for l in log_output]
        assert msgs == ["B", "C", "F"]

    def test_sql_crud_workflow(self):
        source = """
let db = sql.connect(":memory:")
sql.execute(db, "CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
sql.execute(db, "INSERT INTO products VALUES (1, 'Widget', 9.99)")
sql.execute(db, "INSERT INTO products VALUES (2, 'Gadget', 24.99)")
sql.execute(db, "INSERT INTO products VALUES (3, 'Doohickey', 4.99)")
let cheap = sql.query(db, "SELECT * FROM products WHERE price < 10 ORDER BY id")
let expensive = sql.query(db, "SELECT * FROM products WHERE price >= 10 ORDER BY id")
let cheap_count = cheap.length
let exp_count = expensive.length
"""
        interp = run(source)
        assert interp.globals.get("cheap_count") == 2
        assert interp.globals.get("exp_count") == 1

    def test_audit_tracks_operations(self):
        audit_entries: list = []
        audit = AuditLogger(output=audit_entries)
        source = """
audit.log("task.start", "main")
audit.log("file.read", "/data/users.csv")
audit.log("file.write", "/output/report.csv")
audit.log("task.end", "main")
"""
        interp = Interpreter(audit_logger=audit)
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        interp.run(program)
        assert len(audit_entries) == 4
        assert audit_entries[0]["action"] == "task.start"
        assert audit_entries[3]["action"] == "task.end"
