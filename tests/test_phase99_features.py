"""Tests for Phase 99: WeakRef and FinalizationRegistry"""
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


# ── WeakRef ────────────────────────────────────────────────────────────────────

class TestWeakRef:
    def test_weakref_typeof(self):
        i = run("let obj = {x: 1}; let wr = new WeakRef(obj); let v = typeof wr;")
        assert val(i) == "object"

    def test_weakref_deref_returns_object(self):
        i = run("let obj = {x: 42}; let wr = new WeakRef(obj); let v = wr.deref().x;")
        assert val(i) == 42

    def test_weakref_deref_same_object(self):
        i = run("""
let obj = {x: 1};
let wr = new WeakRef(obj);
let derefed = wr.deref();
let v = derefed === obj;
""")
        assert val(i) is True

    def test_weakref_deref_multiple_props(self):
        i = run("""
let obj = {a: 10, b: 20};
let wr = new WeakRef(obj);
let v = wr.deref().a + wr.deref().b;
""")
        assert val(i) == 30

    def test_weakref_deref_modifiable(self):
        i = run("""
let obj = {n: 1};
let wr = new WeakRef(obj);
wr.deref().n = 99;
let v = obj.n;
""")
        assert val(i) == 99

    def test_weakref_to_array(self):
        i = run("""
let arr = [1, 2, 3];
let wr = new WeakRef(arr);
let v = wr.deref().length;
""")
        assert val(i) == 3

    def test_weakref_to_class_instance(self):
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
}
let p = new Point(3, 4);
let wr = new WeakRef(p);
let v = wr.deref().x + wr.deref().y;
""")
        assert val(i) == 7

    def test_weakref_to_class_instance_method(self):
        i = run("""
class Counter {
  constructor() { this.n = 0; }
  inc() { this.n++; }
  get() { return this.n; }
}
let c = new Counter();
let wr = new WeakRef(c);
wr.deref().inc();
wr.deref().inc();
let v = wr.deref().get();
""")
        assert val(i) == 2

    def test_weakref_multiple(self):
        i = run("""
let a = {v: 1};
let b = {v: 2};
let wa = new WeakRef(a);
let wb = new WeakRef(b);
let v = wa.deref().v + wb.deref().v;
""")
        assert val(i) == 3

    def test_weakref_valid_returns_object(self):
        i = run("""
let obj = {x: 1};
let wr = new WeakRef(obj);
let v = wr.deref() !== null;
""")
        assert val(i) is True


# ── FinalizationRegistry ───────────────────────────────────────────────────────

class TestFinalizationRegistry:
    def test_registry_typeof(self):
        i = run("let reg = new FinalizationRegistry(() => {}); let v = typeof reg;")
        assert val(i) == "object"

    def test_registry_register_no_error(self):
        i = run("""
let reg = new FinalizationRegistry(() => {});
let obj = {x: 1};
reg.register(obj, \"token\");
let v = true;
""")
        assert val(i) is True

    def test_registry_unregister_no_error(self):
        i = run("""
let reg = new FinalizationRegistry(() => {});
let obj = {x: 1};
reg.register(obj, \"token\");
reg.unregister(\"token\");
let v = true;
""")
        assert val(i) is True

    def test_registry_callback_not_called_immediately(self):
        i = run("""
let called = false;
let reg = new FinalizationRegistry((t) => { called = true; });
let obj = {x: 1};
reg.register(obj, \"t\");
let v = called;
""")
        assert val(i) is False

    def test_registry_multiple_registrations(self):
        i = run("""
let reg = new FinalizationRegistry(() => {});
let a = {x: 1};
let b = {x: 2};
reg.register(a, \"t1\");
reg.register(b, \"t2\");
let v = true;
""")
        assert val(i) is True

    def test_registry_unregister_specific(self):
        i = run("""
let reg = new FinalizationRegistry(() => {});
let a = {x: 1};
let b = {x: 2};
reg.register(a, \"t1\");
reg.register(b, \"t2\");
reg.unregister(\"t1\");
let v = true;
""")
        assert val(i) is True

    def test_registry_callback_provided(self):
        i = run("""
let callback = (t) => t;
let reg = new FinalizationRegistry(callback);
let v = typeof reg;
""")
        assert val(i) == "object"


# ── WeakSet ────────────────────────────────────────────────────────────────────

class TestWeakSet:
    def test_weakset_typeof(self):
        i = run("let ws = new WeakSet(); let v = typeof ws;")
        assert val(i) == "object"

    def test_weakset_add_has(self):
        i = run("""
let ws = new WeakSet();
let obj = {x: 1};
ws.add(obj);
let v = ws.has(obj);
""")
        assert val(i) is True

    def test_weakset_has_absent(self):
        i = run("""
let ws = new WeakSet();
let obj = {x: 1};
let v = ws.has(obj);
""")
        assert val(i) is False

    def test_weakset_delete(self):
        i = run("""
let ws = new WeakSet();
let obj = {x: 1};
ws.add(obj);
ws.delete(obj);
let v = ws.has(obj);
""")
        assert val(i) is False

    def test_weakset_delete_return_true(self):
        i = run("""
let ws = new WeakSet();
let obj = {};
ws.add(obj);
let v = ws.delete(obj);
""")
        assert val(i) is True

    def test_weakset_multiple_objects(self):
        i = run("""
let ws = new WeakSet();
let a = {}; let b = {}; let c = {};
ws.add(a); ws.add(b);
let v = ws.has(a) && ws.has(b) && !ws.has(c);
""")
        assert val(i) is True

    def test_weakset_add_chaining(self):
        i = run("""
let ws = new WeakSet();
let a = {}; let b = {};
ws.add(a).add(b);
let v = ws.has(a) && ws.has(b);
""")
        assert val(i) is True

    def test_weakset_rejects_primitives_number(self):
        i = run("""
let ws = new WeakSet();
let threw = false;
try { ws.add(42); } catch(e) { threw = true; }
let v = threw;
""")
        assert val(i) is True

    def test_weakset_rejects_primitives_string(self):
        i = run("""
let ws = new WeakSet();
let threw = false;
try { ws.add(\"hello\"); } catch(e) { threw = true; }
let v = threw;
""")
        assert val(i) is True

    def test_weakset_rejects_null(self):
        i = run("""
let ws = new WeakSet();
let threw = false;
try { ws.add(null); } catch(e) { threw = true; }
let v = threw;
""")
        assert val(i) is True

    def test_weakset_accepts_array(self):
        i = run("""
let ws = new WeakSet();
let arr = [1, 2, 3];
ws.add(arr);
let v = ws.has(arr);
""")
        assert val(i) is True


# ── WeakMap ────────────────────────────────────────────────────────────────────

class TestWeakMap:
    def test_weakmap_typeof(self):
        i = run("let wm = new WeakMap(); let v = typeof wm;")
        assert val(i) == "object"

    def test_weakmap_set_get(self):
        i = run("""
let wm = new WeakMap();
let key = {id: 1};
wm.set(key, \"value\");
let v = wm.get(key);
""")
        assert val(i) == "value"

    def test_weakmap_has_true(self):
        i = run("""
let wm = new WeakMap();
let key = {};
wm.set(key, 99);
let v = wm.has(key);
""")
        assert val(i) is True

    def test_weakmap_has_false(self):
        i = run("""
let wm = new WeakMap();
let key = {};
let v = wm.has(key);
""")
        assert val(i) is False

    def test_weakmap_delete(self):
        i = run("""
let wm = new WeakMap();
let key = {};
wm.set(key, 1);
wm.delete(key);
let v = wm.has(key);
""")
        assert val(i) is False

    def test_weakmap_delete_returns_bool(self):
        i = run("""
let wm = new WeakMap();
let key = {};
wm.set(key, 1);
let v = wm.delete(key);
""")
        assert val(i) is True

    def test_weakmap_multiple_keys(self):
        i = run("""
let wm = new WeakMap();
let k1 = {id: 1}; let k2 = {id: 2};
wm.set(k1, \"v1\");
wm.set(k2, \"v2\");
let v = wm.get(k1) + wm.get(k2);
""")
        assert val(i) == "v1v2"

    def test_weakmap_update_value(self):
        i = run("""
let wm = new WeakMap();
let key = {};
wm.set(key, 1);
wm.set(key, 2);
let v = wm.get(key);
""")
        assert val(i) == 2

    def test_weakmap_keys_not_iterable(self):
        i = run("""
let wm = new WeakMap();
let key = {};
wm.set(key, 1);
let threw = false;
try { wm.keys(); } catch(e) { threw = true; }
let v = threw;
""")
        assert val(i) is True

    def test_weakmap_complex_key(self):
        i = run("""
let wm = new WeakMap();
let nested = {a: {b: {c: 1}}};
wm.set(nested, \"deep\");
let v = wm.get(nested);
""")
        assert val(i) == "deep"

    def test_weakmap_object_value(self):
        i = run("""
let wm = new WeakMap();
let key = {};
wm.set(key, {result: 42});
let v = wm.get(key).result;
""")
        assert val(i) == 42

    def test_weakmap_with_class_instance_key(self):
        i = run("""
class Node { constructor(v) { this.v = v; } }
let wm = new WeakMap();
let n = new Node(5);
wm.set(n, \"node-data\");
let v = wm.get(n);
""")
        assert val(i) == "node-data"
