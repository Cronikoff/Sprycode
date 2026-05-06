"""Tests for Phase 57 features:
- `new Fn(args)` on plain functions (creates `this` object, binds fields)
- `new Obj.Ns(args)` for dotted-name constructors (e.g. `new Intl.Segmenter(...)`)
- Proxy `has` trap — `in` operator calls `has(target, prop)`
- Proxy `apply` trap — calling a Proxy wrapping a function invokes `apply` trap
- Proxy `ownKeys` trap — `Reflect.ownKeys(proxy)` invokes `ownKeys` trap
- Proxy `deleteProperty` trap — `delete proxy.prop` invokes trap
"""
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


# ---------------------------------------------------------------------------
# `new` on plain functions
# ---------------------------------------------------------------------------

class TestNewOnPlainFunction:
    def test_basic_constructor(self) -> None:
        i = run("""
function Person(name) {
  this.name = name
}
let p = new Person("Alice")
let v = p.name
""")
        assert val(i) == "Alice"

    def test_multiple_fields(self) -> None:
        i = run("""
function Point(x, y) {
  this.x = x
  this.y = y
}
let p = new Point(3, 4)
let v = [p.x, p.y]
""")
        assert val(i) == [3, 4]

    def test_method_assignment_in_constructor(self) -> None:
        i = run("""
function Counter(start) {
  this.count = start
  this.increment = function() { this.count++ }
}
let c = new Counter(0)
c.increment()
c.increment()
c.increment()
let v = c.count
""")
        assert val(i) == 3

    def test_returns_this_by_default(self) -> None:
        i = run("""
function Box(val) {
  this.val = val
}
let b = new Box(99)
let v = b.val
""")
        assert val(i) == 99

    def test_explicit_object_return_used(self) -> None:
        """If constructor returns an object explicitly, that is the result."""
        i = run("""
function makePoint(x, y) {
  return { x: x, y: y }
}
let p = new makePoint(5, 10)
let v = [p.x, p.y]
""")
        assert val(i) == [5, 10]

    def test_constructor_computes_fields(self) -> None:
        i = run("""
function Rectangle(w, h) {
  this.width = w
  this.height = h
  this.area = w * h
}
let r = new Rectangle(5, 3)
let v = r.area
""")
        assert val(i) == 15

    def test_two_instances_are_independent(self) -> None:
        i = run("""
function Node(val) {
  this.val = val
}
let a = new Node(1)
let b = new Node(2)
a.val = 99
let v = b.val
""")
        assert val(i) == 2

    def test_function_keyword_with_new(self) -> None:
        """function keyword works with new."""
        i = run("""
function Animal(name) {
  this.name = name
  this.speak = function() { return this.name + " speaks" }
}
let a = new Animal("Dog")
let v = a.speak()
""")
        assert val(i) == "Dog speaks"

    def test_new_with_default_params(self) -> None:
        i = run("""
function Config(host = "localhost", port = 8080) {
  this.host = host
  this.port = port
}
let c = new Config()
let v = [c.host, c.port]
""")
        assert val(i) == ["localhost", 8080]

    def test_new_with_rest_param(self) -> None:
        i = run("""
function MyList(...items) {
  this.items = items
  this.length = items.length
}
let lst = new MyList(1, 2, 3)
let v = [lst.items, lst.length]
""")
        assert val(i) == [[1, 2, 3], 3]

    def test_nested_new(self) -> None:
        i = run("""
function Inner(x) { this.x = x }
function Outer(y) {
  this.inner = new Inner(y * 2)
}
let o = new Outer(5)
let v = o.inner.x
""")
        assert val(i) == 10

    def test_new_result_accessible_properties(self) -> None:
        i = run("""
function Person(first, last) {
  this.first = first
  this.last = last
  this.fullName = function() { return this.first + " " + this.last }
}
let p = new Person("John", "Doe")
let v = [p.first, p.last, p.fullName()]
""")
        assert val(i) == ["John", "Doe", "John Doe"]

    def test_new_without_args(self) -> None:
        i = run("""
function Empty() {
  this.x = 42
}
let e = new Empty()
let v = e.x
""")
        assert val(i) == 42

    def test_new_with_conditional_field(self) -> None:
        i = run("""
function Flagged(active) {
  this.active = active
  if (active) {
    this.label = "active"
  } else {
    this.label = "inactive"
  }
}
let a = new Flagged(true)
let b = new Flagged(false)
let v = [a.label, b.label]
""")
        assert val(i) == ["active", "inactive"]


# ---------------------------------------------------------------------------
# `new Obj.Namespace(args)` — dotted constructors
# ---------------------------------------------------------------------------

class TestNewDottedConstructor:
    def test_new_intl_segmenter_grapheme(self) -> None:
        i = run("""
let seg = new Intl.Segmenter("en", {granularity: "grapheme"})
let v = typeof seg
""")
        assert val(i) == "object"

    def test_new_intl_segmenter_word(self) -> None:
        i = run("""
let seg = new Intl.Segmenter("en", {granularity: "word"})
let segs = [...seg.segment("hello world")]
let v = segs.length > 0
""")
        assert val(i) is True

    def test_new_map_from_entries(self) -> None:
        i = run("""
let m = new Map([["a", 1], ["b", 2]])
let v = m.get("a")
""")
        assert val(i) == 1

    def test_new_set(self) -> None:
        i = run("""
let s = new Set([1, 2, 3, 2, 1])
let v = s.size
""")
        assert val(i) == 3

    def test_new_weakref(self) -> None:
        i = run("""
let obj = {x: 42}
let ref = new WeakRef(obj)
let v = ref.deref().x
""")
        assert val(i) == 42

    def test_new_error(self) -> None:
        i = run("""
let e = new Error("test message")
let v = e.message
""")
        assert val(i) == "test message"

    def test_new_regexp(self) -> None:
        i = run("""
let r = new RegExp("\\\\d+", "g")
let v = typeof r
""")
        assert val(i) in ("object", "function")

    def test_new_date_no_args(self) -> None:
        i = run("""
let d = new Date()
let v = typeof d
""")
        assert val(i) == "object"


# ---------------------------------------------------------------------------
# Proxy `has` trap
# ---------------------------------------------------------------------------

class TestProxyHasTrap:
    def test_has_trap_returns_true(self) -> None:
        i = run("""
let p = new Proxy({}, {
  has(target, key) { return key === "anything" }
})
let v = "anything" in p
""")
        assert val(i) is True

    def test_has_trap_returns_false(self) -> None:
        i = run("""
let p = new Proxy({}, {
  has(target, key) { return false }
})
let v = "x" in p
""")
        assert val(i) is False

    def test_has_trap_filters_prefix(self) -> None:
        i = run("""
let p = new Proxy({}, {
  has(target, prop) { return prop.startsWith("_") }
})
let v = ["_hidden" in p, "visible" in p]
""")
        assert val(i) == [True, False]

    def test_has_trap_with_target_fallthrough(self) -> None:
        i = run("""
let p = new Proxy({a: 1, b: 2}, {
  has(target, key) { return key in target || key === "virtual" }
})
let v = ["a" in p, "virtual" in p, "c" in p]
""")
        assert val(i) == [True, True, False]

    def test_has_trap_receives_key(self) -> None:
        i = run("""
let checked = []
let p = new Proxy({}, {
  has(target, key) {
    checked.push(key)
    return key === "yes"
  }
})
let _ = "yes" in p
let v = checked
""")
        assert val(i) == ["yes"]

    def test_has_trap_multiple_keys(self) -> None:
        i = run("""
let p = new Proxy({}, {
  has(target, key) { return ["a", "b", "c"].includes(key) }
})
let v = ["a" in p, "d" in p, "c" in p]
""")
        assert val(i) == [True, False, True]

    def test_no_has_trap_fallthrough_to_target(self) -> None:
        i = run("""
let p = new Proxy({x: 1}, {})
let v = ["x" in p, "y" in p]
""")
        assert val(i) == [True, False]

    def test_has_trap_with_reflect_has(self) -> None:
        i = run("""
let p = new Proxy({real: 1}, {
  has(target, key) { return key === "fake" || Reflect.has(target, key) }
})
let v = ["real" in p, "fake" in p, "none" in p]
""")
        assert val(i) == [True, True, False]


# ---------------------------------------------------------------------------
# Proxy `apply` trap
# ---------------------------------------------------------------------------

class TestProxyApplyTrap:
    def test_apply_trap_intercepts_call(self) -> None:
        i = run("""
let calls = 0
let p = new Proxy(function(x) { return x * 2 }, {
  apply(target, thisArg, args) {
    calls++
    return target(...args)
  }
})
let result = p(5)
let v = [result, calls]
""")
        assert val(i) == [10, 1]

    def test_apply_trap_modifies_args(self) -> None:
        i = run("""
let p = new Proxy(function(x) { return x }, {
  apply(target, thisArg, args) {
    return target(args[0] + 100)
  }
})
let v = p(5)
""")
        assert val(i) == 105

    def test_apply_trap_intercepts_multiple_calls(self) -> None:
        i = run("""
let log = []
let p = new Proxy(function(x) { return x }, {
  apply(target, thisArg, args) {
    log.push(args[0])
    return target(...args)
  }
})
p(1)
p(2)
p(3)
let v = log
""")
        assert val(i) == [1, 2, 3]

    def test_apply_trap_returns_modified_result(self) -> None:
        i = run("""
let p = new Proxy(function(x) { return x }, {
  apply(target, thisArg, args) {
    return target(...args) * 10
  }
})
let v = p(7)
""")
        assert val(i) == 70

    def test_apply_trap_can_short_circuit(self) -> None:
        i = run("""
let p = new Proxy(function(x) { return x }, {
  apply(target, thisArg, args) {
    return "intercepted"
  }
})
let v = p("anything")
""")
        assert val(i) == "intercepted"

    def test_no_apply_trap_calls_target(self) -> None:
        i = run("""
let p = new Proxy(function(x) { return x * 3 }, {})
let v = p(7)
""")
        assert val(i) == 21

    def test_apply_trap_with_multiple_args(self) -> None:
        i = run("""
let p = new Proxy(function(a, b) { return a + b }, {
  apply(target, thisArg, args) {
    return target(args[0] * 2, args[1] * 2)
  }
})
let v = p(3, 4)
""")
        assert val(i) == 14

    def test_apply_trap_logging_wrapper(self) -> None:
        i = run("""
function add(a, b) { return a + b }
let log = []
let tracedAdd = new Proxy(add, {
  apply(target, thisArg, args) {
    log.push("called with " + args.join(", "))
    let result = target(...args)
    log.push("returned " + result)
    return result
  }
})
let v = tracedAdd(2, 3)
let vLog = log
""")
        assert val(i, "v") == 5
        assert val(i, "vLog") == ["called with 2, 3", "returned 5"]


# ---------------------------------------------------------------------------
# Proxy `ownKeys` trap
# ---------------------------------------------------------------------------

class TestProxyOwnKeysTrap:
    def test_ownkeys_returns_custom_list(self) -> None:
        i = run("""
let p = new Proxy({x: 1, y: 2}, {
  ownKeys(target) { return ["a", "b", "c"] }
})
let v = Reflect.ownKeys(p)
""")
        assert val(i) == ["a", "b", "c"]

    def test_ownkeys_filters_keys(self) -> None:
        i = run("""
let p = new Proxy({a: 1, _b: 2, c: 3}, {
  ownKeys(target) {
    return Object.keys(target).filter(k => !k.startsWith("_"))
  }
})
let v = Reflect.ownKeys(p)
""")
        assert val(i) == ["a", "c"]

    def test_ownkeys_adds_extra_keys(self) -> None:
        i = run("""
let p = new Proxy({x: 1}, {
  ownKeys(target) {
    return Object.keys(target).concat(["extra"])
  }
})
let v = Reflect.ownKeys(p)
""")
        assert val(i) == ["x", "extra"]

    def test_no_ownkeys_trap_returns_target_keys(self) -> None:
        i = run("""
let p = new Proxy({a: 1, b: 2}, {})
let v = Reflect.ownKeys(p)
""")
        assert val(i) == ["a", "b"]

    def test_ownkeys_empty(self) -> None:
        i = run("""
let p = new Proxy({x: 1}, {
  ownKeys(target) { return [] }
})
let v = Reflect.ownKeys(p)
""")
        assert val(i) == []

    def test_ownkeys_receives_target(self) -> None:
        i = run("""
let received = null
let p = new Proxy({a: 1}, {
  ownKeys(target) {
    received = Object.keys(target)
    return []
  }
})
Reflect.ownKeys(p)
let v = received
""")
        assert val(i) == ["a"]


# ---------------------------------------------------------------------------
# Proxy `deleteProperty` trap
# ---------------------------------------------------------------------------

class TestProxyDeletePropertyTrap:
    def test_delete_invokes_trap(self) -> None:
        i = run("""
let log = []
let p = new Proxy({x: 1, y: 2}, {
  deleteProperty(target, prop) {
    log.push(prop)
    delete target[prop]
    return true
  }
})
delete p.x
let v = log
""")
        assert val(i) == ["x"]

    def test_delete_trap_can_prevent_deletion(self) -> None:
        i = run("""
let target = {x: 1, y: 2}
let p = new Proxy(target, {
  deleteProperty(t, prop) {
    return false
  }
})
delete p.x
let v = target.x
""")
        assert val(i) == 1

    def test_delete_trap_receives_correct_prop(self) -> None:
        i = run("""
let received = null
let p = new Proxy({hello: 1}, {
  deleteProperty(target, prop) {
    received = prop
    return true
  }
})
delete p.hello
let v = received
""")
        assert val(i) == "hello"

    def test_delete_trap_actually_removes_from_target(self) -> None:
        i = run("""
let target = {x: 1, y: 2}
let p = new Proxy(target, {
  deleteProperty(t, prop) {
    delete t[prop]
    return true
  }
})
delete p.x
let v = Object.keys(target)
""")
        assert val(i) == ["y"]

    def test_no_delete_trap_falls_through(self) -> None:
        i = run("""
let target = {x: 1, y: 2}
let p = new Proxy(target, {})
delete p.x
let v = Object.keys(target)
""")
        assert val(i) == ["y"]

    def test_delete_with_reflect_deleteProperty(self) -> None:
        i = run("""
let log = []
let target = {a: 1, b: 2}
let p = new Proxy(target, {
  deleteProperty(t, prop) {
    log.push(prop)
    return Reflect.deleteProperty(t, prop)
  }
})
delete p.a
let v = [log, Object.keys(target)]
""")
        assert val(i) == [["a"], ["b"]]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase57Integration:
    def test_constructor_function_pattern(self) -> None:
        """Simulate a common JS OOP pattern with plain constructor functions."""
        i = run("""
function Stack() {
  this.items = []
  this.push = function(item) { this.items.push(item) }
  this.pop = function() { return this.items.pop() }
  this.size = function() { return this.items.length }
}
let s = new Stack()
s.push(1)
s.push(2)
s.push(3)
let top = s.pop()
let v = [top, s.size()]
""")
        assert val(i) == [3, 2]

    def test_proxy_as_observable(self) -> None:
        """Proxy used to observe get/set."""
        i = run("""
let changes = []
let state = {}
let proxy = new Proxy(state, {
  set(target, prop, value) {
    changes.push(prop + "=" + value)
    target[prop] = value
    return true
  }
})
proxy.name = "Alice"
proxy.age = 30
let v = [changes, state.name, state.age]
""")
        assert val(i) == [["name=Alice", "age=30"], "Alice", 30]

    def test_proxy_apply_memoize(self) -> None:
        """Proxy used to memoize function results."""
        i = run("""
let cache = {}
let calls = 0
function expensiveCalc(n) {
  calls++
  return n * n
}
let memoized = new Proxy(expensiveCalc, {
  apply(target, thisArg, args) {
    let n = args[0]
    let key = "" + n
    if (key in cache) return cache[key]
    let result = target(n)
    cache[key] = result
    return result
  }
})
let a = memoized(5)
let b = memoized(5)
let c = memoized(3)
let v = [a, b, c, calls]
""")
        assert val(i) == [25, 25, 9, 2]

    def test_constructor_with_proxy_observer(self) -> None:
        i = run("""
function Person(name) {
  this.name = name
}
let p = new Person("Alice")
let observed = new Proxy(p, {
  get(target, prop) { return target[prop] },
  set(target, prop, val) { target[prop] = val; return true }
})
observed.name = "Bob"
let v = p.name
""")
        assert val(i) == "Bob"

    def test_proxy_has_trap_access_control(self) -> None:
        """Proxy used as access control layer."""
        i = run("""
let data = {public: 1, _private: 2, internal: 3}
let exposed = new Proxy(data, {
  has(target, key) {
    return !key.startsWith("_") && key in target
  }
})
let v = ["public" in exposed, "_private" in exposed, "internal" in exposed]
""")
        assert val(i) == [True, False, True]

    def test_new_keyword_patterns(self) -> None:
        """Multiple constructor function instantiations."""
        i = run("""
function Vec2(x, y) {
  this.x = x
  this.y = y
  this.add = function(other) { return new Vec2(this.x + other.x, this.y + other.y) }
  this.toString = function() { return "(" + this.x + "," + this.y + ")" }
}
let a = new Vec2(1, 2)
let b = new Vec2(3, 4)
let c = a.add(b)
let v = [c.x, c.y]
""")
        assert val(i) == [4, 6]
