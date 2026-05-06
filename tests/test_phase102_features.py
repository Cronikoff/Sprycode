"""Tests for Phase 102: Modules / Namespaces (simulated)"""
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


# ── Module-pattern closure returning API ─────────────────────────────────────

class TestModulePattern:
    def test_module_basic(self):
        i = run("""
function createModule() {
  let state = 0;
  return {
    get: function() { return state; },
    set: function(v) { state = v; }
  };
}
let m = createModule();
m.set(42);
let v = m.get();
""")
        assert val(i) == 42

    def test_module_private_state(self):
        i = run("""
function makeAccount(initial) {
  let balance = initial;
  return {
    deposit: function(n) { balance = balance + n; },
    withdraw: function(n) { balance = balance - n; },
    getBalance: function() { return balance; }
  };
}
let acc = makeAccount(100);
acc.deposit(50);
acc.withdraw(30);
let v = acc.getBalance();
""")
        assert val(i) == 120

    def test_module_state_isolated(self):
        i = run("""
function makeCounter(start) {
  let n = start;
  return {
    inc: function() { n++; },
    get: function() { return n; }
  };
}
let c1 = makeCounter(0);
let c2 = makeCounter(10);
c1.inc(); c1.inc();
c2.inc();
let v = c1.get() + c2.get();
""")
        assert val(i) == 13

    def test_module_method_chaining(self):
        i = run("""
function createBuilder() {
  let parts = [];
  return {
    add: function(x) { parts.push(x); return this; },
    build: function() { return parts.join(\",\"); }
  };
}
let b = createBuilder();
b.add(\"a\"); b.add(\"b\"); b.add(\"c\");
let v = b.build();
""")
        assert val(i) == "a,b,c"


# ── Revealing module pattern ──────────────────────────────────────────────────

class TestRevealingModule:
    def test_revealing_basic(self):
        i = run("""
function myModule() {
  let count = 0;
  function increment() { count++; }
  function getCount() { return count; }
  return { increment, getCount };
}
let m = myModule();
m.increment(); m.increment(); m.increment();
let v = m.getCount();
""")
        assert val(i) == 3

    def test_revealing_hides_private(self):
        i = run("""
function calculator() {
  let result = 0;
  function add(n) { result = result + n; }
  function sub(n) { result = result - n; }
  function getResult() { return result; }
  return { add, sub, getResult };
}
let calc = calculator();
calc.add(10); calc.add(5); calc.sub(3);
let v = calc.getResult();
""")
        assert val(i) == 12

    def test_revealing_multiple_methods(self):
        i = run("""
function stringBuilder() {
  let str = \"\";
  function append(s) { str = str + s; }
  function prepend(s) { str = s + str; }
  function get() { return str; }
  return { append, prepend, get };
}
let sb = stringBuilder();
sb.append(\"world\");
sb.prepend(\"hello \");
let v = sb.get();
""")
        assert val(i) == "hello world"


# ── IIFE (Immediately Invoked Function Expression) ───────────────────────────

class TestIIFE:
    def test_iife_basic(self):
        i = run("let v = (function() { return 42; })();")
        assert val(i) == 42

    def test_iife_with_arg(self):
        i = run("let v = (function(x) { return x * 2; })(5);")
        assert val(i) == 10

    def test_iife_closure(self):
        i = run("""
let v = (function() {
  let x = 10;
  let y = 20;
  return x + y;
})();
""")
        assert val(i) == 30

    def test_iife_arrow(self):
        i = run("let v = (() => 99)();")
        assert val(i) == 99

    def test_iife_creates_scope(self):
        i = run("""
let v = (function() {
  let hiddenVal = \"hidden\";
  return hiddenVal.length;
})();
""")
        assert val(i) == 6

    def test_iife_side_effects(self):
        i = run("""
let log = [];
(function() {
  log.push(1);
  log.push(2);
  log.push(3);
})();
let v = log;
""")
        assert val(i) == [1, 2, 3]


# ── Namespace object with methods ─────────────────────────────────────────────

class TestNamespace:
    def test_namespace_basic(self):
        i = run("""
let MathUtils = {
  square: function(x) { return x * x; },
  cube: function(x) { return x * x * x; }
};
let v = MathUtils.square(4) + MathUtils.cube(2);
""")
        assert val(i) == 24

    def test_namespace_string_utils(self):
        i = run("""
let StringUtils = {
  upper: function(s) { return s.toUpperCase(); },
  lower: function(s) { return s.toLowerCase(); },
  trim: function(s) { return s.trim(); }
};
let v = StringUtils.upper(\"hello\");
""")
        assert val(i) == "HELLO"

    def test_namespace_nested(self):
        i = run("""
let Utils = {
  math: {
    add: function(a, b) { return a + b; },
    mul: function(a, b) { return a * b; }
  }
};
let v = Utils.math.add(3, 4) + Utils.math.mul(2, 5);
""")
        assert val(i) == 17


# ── Private state via closure ─────────────────────────────────────────────────

class TestPrivateState:
    def test_private_not_accessible(self):
        i = run("""
function makeObj() {
  let _private = 42;
  return {
    getPrivate: function() { return _private; }
  };
}
let obj = makeObj();
let v = obj.getPrivate();
""")
        assert val(i) == 42

    def test_private_mutable(self):
        i = run("""
function makeObj() {
  let _x = 0;
  return {
    set: function(n) { _x = n; },
    get: function() { return _x; }
  };
}
let obj = makeObj();
obj.set(99);
let v = obj.get();
""")
        assert val(i) == 99

    def test_private_shared_by_methods(self):
        i = run("""
function makeObj() {
  let _log = [];
  return {
    log: function(v) { _log.push(v); },
    getLogs: function() { return _log; }
  };
}
let obj = makeObj();
obj.log(1); obj.log(2); obj.log(3);
let v = obj.getLogs().length;
""")
        assert val(i) == 3


# ── Counter module ────────────────────────────────────────────────────────────

class TestCounterModule:
    def test_counter_increment(self):
        i = run("""
function makeCounter() {
  let count = 0;
  return {
    increment: function() { count++; },
    decrement: function() { count--; },
    reset: function() { count = 0; },
    get: function() { return count; }
  };
}
let c = makeCounter();
c.increment(); c.increment(); c.increment();
let v = c.get();
""")
        assert val(i) == 3

    def test_counter_decrement(self):
        i = run("""
function makeCounter() {
  let count = 0;
  return {
    increment: function() { count++; },
    decrement: function() { count--; },
    get: function() { return count; }
  };
}
let c = makeCounter();
c.increment(); c.increment();
c.decrement();
let v = c.get();
""")
        assert val(i) == 1

    def test_counter_reset(self):
        i = run("""
function makeCounter() {
  let count = 0;
  return {
    increment: function() { count++; },
    reset: function() { count = 0; },
    get: function() { return count; }
  };
}
let c = makeCounter();
c.increment(); c.increment(); c.increment();
c.reset();
let v = c.get();
""")
        assert val(i) == 0

    def test_counter_sequence(self):
        i = run("""
function makeCounter() {
  let count = 0;
  return { inc: () => ++count, get: () => count };
}
let c = makeCounter();
let v = [c.inc(), c.inc(), c.inc()];
""")
        assert val(i) == [1, 2, 3]


# ── Event emitter module ──────────────────────────────────────────────────────

class TestEventEmitter:
    def test_event_emitter_basic(self):
        i = run("""
function createEmitter() {
  let listeners = {};
  return {
    on: function(event, cb) {
      if (!(event in listeners)) listeners[event] = [];
      listeners[event].push(cb);
    },
    emit: function(event, data) {
      if (event in listeners) {
        let cbs = listeners[event];
        let i = 0;
        while (i < cbs.length) { cbs[i](data); i++; }
      }
    }
  };
}
let emitter = createEmitter();
let log = [];
emitter.on(\"data\", d => log.push(d));
emitter.emit(\"data\", 1);
emitter.emit(\"data\", 2);
let v = log;
""")
        assert val(i) == [1, 2]

    def test_event_multiple_listeners(self):
        i = run("""
function createEmitter() {
  let listeners = {};
  return {
    on: function(event, cb) {
      if (!(event in listeners)) listeners[event] = [];
      listeners[event].push(cb);
    },
    emit: function(event, data) {
      if (event in listeners) {
        let cbs = listeners[event];
        let i = 0;
        while (i < cbs.length) { cbs[i](data); i++; }
      }
    }
  };
}
let emitter = createEmitter();
let log = [];
emitter.on(\"click\", d => log.push(\"A:\" + d));
emitter.on(\"click\", d => log.push(\"B:\" + d));
emitter.emit(\"click\", \"x\");
let v = log;
""")
        assert val(i) == ["A:x", "B:x"]


# ── Observer pattern ──────────────────────────────────────────────────────────

class TestObserverPattern:
    def test_observer_basic(self):
        i = run("""
function createObservable() {
  let observers = [];
  return {
    subscribe: function(obs) { observers.push(obs); },
    notify: function(data) {
      let i = 0;
      while (i < observers.length) { observers[i](data); i++; }
    }
  };
}
let obs = createObservable();
let log = [];
obs.subscribe(d => log.push(\"A:\" + d));
obs.subscribe(d => log.push(\"B:\" + d));
obs.notify(\"x\");
let v = log;
""")
        assert val(i) == ["A:x", "B:x"]

    def test_observer_multiple_notify(self):
        i = run("""
function createObservable() {
  let observers = [];
  return {
    subscribe: function(obs) { observers.push(obs); },
    notify: function(data) {
      let i = 0;
      while (i < observers.length) { observers[i](data); i++; }
    }
  };
}
let obs = createObservable();
let sum = 0;
obs.subscribe(d => { sum = sum + d; });
obs.notify(5); obs.notify(3); obs.notify(2);
let v = sum;
""")
        assert val(i) == 10


# ── Pub/sub pattern ───────────────────────────────────────────────────────────

class TestPubSub:
    def test_pubsub_basic(self):
        i = run("""
function createPubSub() {
  let subs = {};
  return {
    subscribe: function(topic, cb) {
      if (!(topic in subs)) subs[topic] = [];
      subs[topic].push(cb);
    },
    publish: function(topic, msg) {
      if (topic in subs) {
        let list = subs[topic];
        let i = 0;
        while (i < list.length) { list[i](msg); i++; }
      }
    }
  };
}
let ps = createPubSub();
let news = [];
ps.subscribe(\"news\", msg => news.push(msg));
ps.publish(\"news\", \"hello\");
ps.publish(\"news\", \"world\");
let v = news;
""")
        assert val(i) == ["hello", "world"]

    def test_pubsub_multiple_topics(self):
        i = run("""
function createPubSub() {
  let subs = {};
  return {
    subscribe: function(topic, cb) {
      if (!(topic in subs)) subs[topic] = [];
      subs[topic].push(cb);
    },
    publish: function(topic, msg) {
      if (topic in subs) {
        let list = subs[topic];
        let i = 0;
        while (i < list.length) { list[i](msg); i++; }
      }
    }
  };
}
let ps = createPubSub();
let log = [];
ps.subscribe(\"a\", m => log.push(\"a:\" + m));
ps.subscribe(\"b\", m => log.push(\"b:\" + m));
ps.publish(\"a\", \"1\");
ps.publish(\"b\", \"2\");
let v = log;
""")
        assert val(i) == ["a:1", "b:2"]


# ── Memoization ───────────────────────────────────────────────────────────────

class TestMemoization:
    def test_memoize_caches_result(self):
        i = run("""
function memoize(f) {
  let cache = {};
  return function(n) {
    let key = n + \"\";
    if (key in cache) return cache[key];
    let result = f(n);
    cache[key] = result;
    return result;
  };
}
let callCount = 0;
let sq = memoize(function(n) { callCount++; return n * n; });
sq(5); sq(5); sq(5);
let v = callCount;
""")
        assert val(i) == 1

    def test_memoize_different_args(self):
        i = run("""
function memoize(f) {
  let cache = {};
  return function(n) {
    let key = n + \"\";
    if (key in cache) return cache[key];
    let result = f(n);
    cache[key] = result;
    return result;
  };
}
let callCount = 0;
let sq = memoize(function(n) { callCount++; return n * n; });
sq(3); sq(4); sq(5);
let v = callCount;
""")
        assert val(i) == 3

    def test_memoize_returns_correct(self):
        i = run("""
function memoize(f) {
  let cache = {};
  return function(n) {
    let key = n + \"\";
    if (key in cache) return cache[key];
    let result = f(n);
    cache[key] = result;
    return result;
  };
}
let double = memoize(n => n * 2);
let v = double(7);
""")
        assert val(i) == 14


# ── Lazy initialization ───────────────────────────────────────────────────────

class TestLazyInitialization:
    def test_lazy_computes_once(self):
        i = run("""
function lazy(compute) {
  let cache = null;
  let isComputed = false;
  return function() {
    if (isComputed === false) {
      cache = compute();
      isComputed = true;
    }
    return cache;
  };
}
let callCount = 0;
let getValue = lazy(function() { callCount++; return 42; });
getValue(); getValue(); getValue();
let v = callCount;
""")
        assert val(i) == 1

    def test_lazy_returns_correct(self):
        i = run("""
function lazy(compute) {
  let cache = null;
  let isComputed = false;
  return function() {
    if (isComputed === false) {
      cache = compute();
      isComputed = true;
    }
    return cache;
  };
}
let getVal = lazy(() => 99);
let v = getVal();
""")
        assert val(i) == 99

    def test_lazy_deferred(self):
        i = run("""
function lazy(compute) {
  let cache = null;
  let isComputed = false;
  return function() {
    if (isComputed === false) { cache = compute(); isComputed = true; }
    return cache;
  };
}
let log = [];
let expensive = lazy(function() { log.push(\"computed\"); return 1; });
let v1 = log.length;
expensive();
let v2 = log.length;
let v = v1 + v2;
""")
        assert val(i) == 1


# ── Partial application ───────────────────────────────────────────────────────

class TestPartialApplication:
    def test_partial_basic(self):
        i = run("""
function partial(f, ...args) {
  return function(...rest) { return f(...args, ...rest); };
}
let add = (a, b) => a + b;
let add5 = partial(add, 5);
let v = add5(3);
""")
        assert val(i) == 8

    def test_partial_three_arg(self):
        i = run("""
function partial(f, ...args) {
  return function(...rest) { return f(...args, ...rest); };
}
let sum = (a, b, c) => a + b + c;
let sum10 = partial(sum, 10);
let v = sum10(3, 2);
""")
        assert val(i) == 15

    def test_partial_multiple_applied(self):
        i = run("""
function partial(f, ...args) {
  return function(...rest) { return f(...args, ...rest); };
}
let mul = (a, b) => a * b;
let double = partial(mul, 2);
let triple = partial(mul, 3);
let v = double(5) + triple(4);
""")
        assert val(i) == 22


# ── Function composition ──────────────────────────────────────────────────────

class TestFunctionComposition:
    def test_compose_two(self):
        i = run("""
function compose(f, g) {
  return function(x) { return f(g(x)); };
}
let double = x => x * 2;
let addOne = x => x + 1;
let doubleAndAdd = compose(addOne, double);
let v = doubleAndAdd(5);
""")
        assert val(i) == 11

    def test_compose_order(self):
        i = run("""
function compose(f, g) {
  return function(x) { return f(g(x)); };
}
let square = x => x * x;
let negate = x => -x;
let negateSquare = compose(negate, square);
let v = negateSquare(3);
""")
        assert val(i) == -9

    def test_pipe_two(self):
        i = run("""
function pipe(f, g) {
  return function(x) { return g(f(x)); };
}
let double = x => x * 2;
let addOne = x => x + 1;
let pipeFn = pipe(double, addOne);
let v = pipeFn(5);
""")
        assert val(i) == 11


# ── Decorator-like wrapper ────────────────────────────────────────────────────

class TestDecoratorWrapper:
    def test_log_wrapper(self):
        i = run("""
let callLog = [];
function withLogging(f) {
  return function(...args) {
    callLog.push(args[0]);
    return f(...args);
  };
}
let greet = withLogging(name => \"Hello, \" + name);
greet(\"Alice\");
greet(\"Bob\");
let v = callLog;
""")
        assert val(i) == ["Alice", "Bob"]

    def test_timing_wrapper(self):
        i = run("""
function withResult(f) {
  return function(...args) {
    let result = f(...args);
    return {result, args};
  };
}
let add = withResult((a, b) => a + b);
let r = add(3, 4);
let v = r.result;
""")
        assert val(i) == 7

    def test_validator_wrapper(self):
        i = run("""
function withCheck(f, check) {
  return function(...args) {
    if (check(args[0])) return f(...args);
    return null;
  };
}
let isPositive = x => x > 0;
let safeSqrt = withCheck(x => x * x, isPositive);
let v1 = safeSqrt(5);
let v2 = safeSqrt(-3);
let v = [v1, v2];
""")
        assert val(i) == [25, None]


# ── Command pattern ───────────────────────────────────────────────────────────

class TestCommandPattern:
    def test_command_execute_undo(self):
        i = run("""
let value = 0;
function makeAddCommand(n) {
  return {
    execute: function() { value = value + n; },
    undo: function() { value = value - n; }
  };
}
let cmd = makeAddCommand(10);
cmd.execute();
cmd.execute();
cmd.undo();
let v = value;
""")
        assert val(i) == 10

    def test_command_history(self):
        i = run("""
let result = 0;
let history = [];
function makeCmd(op, n) {
  return {
    execute: function() { result = op(result, n); history.push(n); },
    undo: function() { result = result - n; history.pop(); }
  };
}
let add = (a, b) => a + b;
let c1 = makeCmd(add, 5);
let c2 = makeCmd(add, 3);
c1.execute(); c2.execute();
let v = result;
""")
        assert val(i) == 8

    def test_command_list(self):
        i = run("""
let total = 0;
function makeAdd(n) {
  return { execute: () => { total = total + n; } };
}
let commands = [makeAdd(1), makeAdd(2), makeAdd(3)];
for (let cmd of commands) { cmd.execute(); }
let v = total;
""")
        assert val(i) == 6


# ── Currying ──────────────────────────────────────────────────────────────────

class TestCurrying:
    def test_curry_two_arg(self):
        i = run("""
function curry(f) {
  return function(a) {
    return function(b) { return f(a, b); };
  };
}
let add = curry((a, b) => a + b);
let v = add(3)(4);
""")
        assert val(i) == 7

    def test_curry_reuse(self):
        i = run("""
function curry(f) {
  return function(a) {
    return function(b) { return f(a, b); };
  };
}
let mul = curry((a, b) => a * b);
let double = mul(2);
let triple = mul(3);
let v = double(5) + triple(4);
""")
        assert val(i) == 22

    def test_curry_string(self):
        i = run("""
function curry(f) {
  return function(a) {
    return function(b) { return f(a, b); };
  };
}
let greet = curry((greeting, name) => greeting + \", \" + name + \"!\");
let hello = greet(\"Hello\");
let v = hello(\"World\");
""")
        assert val(i) == "Hello, World!"

    def test_once_wrapper(self):
        i = run("""
function once(f) {
  let called = false;
  let result = null;
  return function(...args) {
    if (called === false) {
      result = f(...args);
      called = true;
    }
    return result;
  };
}
let callCount = 0;
let doOnce = once(function() { callCount++; return 42; });
doOnce(); doOnce(); doOnce();
let v = callCount;
""")
        assert val(i) == 1

    def test_negate_predicate(self):
        i = run("""
function negate(pred) {
  return function(...args) { return !pred(...args); };
}
let isEven = n => n % 2 === 0;
let isOdd = negate(isEven);
let nums = [1, 2, 3, 4, 5];
let v = nums.filter(isOdd);
""")
        assert val(i) == [1, 3, 5]
