"""Phase 59 feature tests.

Covers:
- Object.assign to SpryInstance target
- SpryFunction.prototype — get/set, method definition via prototype
- `new Fn()` constructor pattern with prototype-based method/property inheritance
- Multi-level prototype chain with Object.create
- new Uint8Array / Int32Array / Float64Array (from size or array)
- new ArrayBuffer(byteLength)
"""

import pytest
import math
from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


# ---------------------------------------------------------------------------
# Object.assign to SpryInstance
# ---------------------------------------------------------------------------

def test_object_assign_to_instance_from_dict():
    """Object.assign merges plain dict properties into a SpryInstance."""
    i = run("""
class Point { constructor(x, y) { this.x = x; this.y = y } }
let p = new Point(1, 2)
Object.assign(p, {z: 3})
let v = [p.x, p.y, p.z]
""")
    assert i.globals["v"] == [1, 2, 3]


def test_object_assign_to_instance_multiple_sources():
    """Object.assign merges multiple plain dicts into a SpryInstance."""
    i = run("""
class Box { constructor() { this.a = 0 } }
let b = new Box()
Object.assign(b, {x: 1, y: 2}, {z: 3})
let v = [b.a, b.x, b.y, b.z]
""")
    assert i.globals["v"] == [0, 1, 2, 3]


def test_object_assign_returns_target_instance():
    """Object.assign returns the target instance (for chaining)."""
    i = run("""
class A { constructor() { this.a = 1 } }
let obj = new A()
let result = Object.assign(obj, {b: 2})
let v = result.b
""")
    assert i.globals["v"] == 2


def test_object_assign_instance_from_instance():
    """Object.assign from one SpryInstance to another copies own non-private fields."""
    i = run("""
class A { constructor() { this.a = 1 } }
class B { constructor() { this.b = 2 } }
let a = new A()
let b = new B()
Object.assign(a, b)
let v = [a.a, a.b]
""")
    assert i.globals["v"] == [1, 2]


def test_object_assign_dict_to_dict_still_works():
    """Object.assign dict → dict still works after the SpryInstance fix."""
    i = run("""
let target = {a: 1}
Object.assign(target, {b: 2, c: 3})
let v = [target.a, target.b, target.c]
""")
    assert i.globals["v"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# SpryFunction.prototype
# ---------------------------------------------------------------------------

def test_spry_function_prototype_typeof():
    """Accessing Fn.prototype should return an object (dict)."""
    i = run("""
function Foo() { this.x = 1 }
let v = typeof Foo.prototype
""")
    assert i.globals["v"] == "object"


def test_spry_function_prototype_set_method():
    """Setting a method on Fn.prototype makes it available on instances."""
    i = run("""
function Animal(name) { this.name = name }
Animal.prototype.speak = function() { return this.name + " speaks" }
let a = new Animal("Cat")
let v = a.speak()
""")
    assert i.globals["v"] == "Cat speaks"


def test_spry_function_prototype_set_property():
    """Setting a property on Fn.prototype makes it accessible on instances."""
    i = run("""
function Animal(name) { this.name = name }
Animal.prototype.type = "animal"
let a = new Animal("Dog")
let v = [a.name, a.type]
""")
    assert i.globals["v"] == ["Dog", "animal"]


def test_spry_function_prototype_counter():
    """Prototype methods can mutate instance state via `this`."""
    i = run("""
function Counter() { this.count = 0 }
Counter.prototype.inc = function() { this.count++ }
Counter.prototype.get = function() { return this.count }
let c = new Counter()
c.inc()
c.inc()
c.inc()
let v = c.get()
""")
    assert i.globals["v"] == 3


def test_spry_function_prototype_multiple_instances_independent():
    """Each instance via new Fn() has its own `this` — mutations don't bleed across."""
    i = run("""
function Counter() { this.count = 0 }
Counter.prototype.inc = function() { this.count++ }
let a = new Counter()
let b = new Counter()
a.inc()
a.inc()
let v = [a.count, b.count]
""")
    assert i.globals["v"] == [2, 0]


def test_spry_function_prototype_own_property_shadows_proto():
    """Own properties shadow prototype properties."""
    i = run("""
function Obj() { this.color = "blue" }
Obj.prototype.color = "red"
let o = new Obj()
let v = o.color
""")
    assert i.globals["v"] == "blue"


def test_spry_function_prototype_replace():
    """Replacing Fn.prototype wholesale works."""
    i = run("""
function Foo() { this.x = 1 }
Foo.prototype = { greet: function() { return "hello " + this.x } }
let f = new Foo()
let v = f.greet()
""")
    assert i.globals["v"] == "hello 1"


def test_spry_function_prototype_constructor_ref():
    """Fn.prototype.constructor references the function itself by default."""
    i = run("""
function Point(x, y) { this.x = x; this.y = y }
let v = typeof Point.prototype.constructor
""")
    assert i.globals["v"] == "function"


# ---------------------------------------------------------------------------
# Multi-level prototype chain with Object.create
# ---------------------------------------------------------------------------

def test_object_create_single_level():
    """Object.create(proto) creates an object that inherits proto properties."""
    i = run("""
let proto = { greet: function() { return "Hello, " + this.name } }
let obj = Object.create(proto)
obj.name = "World"
let v = obj.greet()
""")
    assert i.globals["v"] == "Hello, World"


def test_prototype_chain_two_levels():
    """Two-level prototype chain: Shape → Circle via Object.create."""
    i = run("""
function Shape() {}
Shape.prototype.area = function() { return 0 }

function Circle(r) { this.r = r }
Circle.prototype = Object.create(Shape.prototype)
Circle.prototype.area = function() { return 3.14159 * this.r * this.r }

let c = new Circle(5)
let v = Math.round(c.area())
""")
    assert i.globals["v"] == 79


def test_prototype_chain_inherited_property():
    """Property defined on a parent constructor prototype is inherited."""
    i = run("""
function Vehicle() {}
Vehicle.prototype.wheels = 4

function Car(make) { this.make = make }
Car.prototype = Object.create(Vehicle.prototype)

let c = new Car("Toyota")
let v = [c.make, c.wheels]
""")
    assert i.globals["v"] == ["Toyota", 4]


def test_prototype_chain_method_override():
    """Overriding a proto method works — the overridden one wins."""
    i = run("""
function Animal() {}
Animal.prototype.sound = function() { return "..." }

function Dog() {}
Dog.prototype = Object.create(Animal.prototype)
Dog.prototype.sound = function() { return "woof" }

let d = new Dog()
let v = d.sound()
""")
    assert i.globals["v"] == "woof"


def test_prototype_chain_calling_parent_sound():
    """A deeper prototype chain: Animal → Dog → Husky."""
    i = run("""
function Animal() {}
Animal.prototype.type = "animal"

function Dog() {}
Dog.prototype = Object.create(Animal.prototype)
Dog.prototype.species = "dog"

function Husky() { this.name = "Husky" }
Husky.prototype = Object.create(Dog.prototype)

let h = new Husky()
let v = [h.name, h.species, h.type]
""")
    assert i.globals["v"] == ["Husky", "dog", "animal"]


# ---------------------------------------------------------------------------
# new Uint8Array / Int32Array / Float64Array
# ---------------------------------------------------------------------------

def test_new_uint8array_from_length():
    """new Uint8Array(n) creates a zero-filled array of length n."""
    i = run("""
let a = new Uint8Array(5)
let v = [a.length, a[0], a[4]]
""")
    assert i.globals["v"] == [5, 0, 0]


def test_new_uint8array_from_array():
    """new Uint8Array([...]) creates a typed array from a list."""
    i = run("""
let a = new Uint8Array([10, 20, 30])
let v = [a[0], a[1], a[2], a.length]
""")
    assert i.globals["v"] == [10, 20, 30, 3]


def test_new_uint8array_set_element():
    """Elements can be set via bracket assignment."""
    i = run("""
let a = new Uint8Array(3)
a[0] = 7
a[1] = 8
a[2] = 9
let v = [a[0], a[1], a[2]]
""")
    assert i.globals["v"] == [7, 8, 9]


def test_new_int32array():
    """new Int32Array([1, -2, 3]) stores signed integers."""
    i = run("""
let a = new Int32Array([1, -2, 3])
let v = [a[0], a[1], a.length]
""")
    assert i.globals["v"] == [1, -2, 3]


def test_new_float64array():
    """new Float64Array([1.5, 2.5]) stores floats."""
    i = run("""
let a = new Float64Array([1.5, 2.5, 3.5])
let v = a[1]
""")
    assert i.globals["v"] == 2.5


def test_typed_array_from_still_works():
    """Uint8Array.from(iterable) still works after adding __call__."""
    i = run("""
let a = Uint8Array.from([5, 10, 15])
let v = [a[0], a.length]
""")
    assert i.globals["v"] == [5, 3]


def test_typed_array_bytes_per_element():
    """BYTES_PER_ELEMENT property is correct per type."""
    i = run("""
let v = [Uint8Array.BYTES_PER_ELEMENT, Int32Array.BYTES_PER_ELEMENT, Float64Array.BYTES_PER_ELEMENT]
""")
    assert i.globals["v"] == [1, 4, 8]


def test_array_from_typed_array():
    """Array.from works on a typed array after new Uint8Array fix."""
    i = run("""
let a = new Uint8Array([1, 2, 3])
let v = Array.from(a)
""")
    assert i.globals["v"] == [1, 2, 3]


def test_typed_array_iterate():
    """Typed arrays are iterable via for...of."""
    i = run("""
let a = new Uint8Array([10, 20, 30])
let v = []
for (let x of a) { v.push(x) }
""")
    assert i.globals["v"] == [10, 20, 30]


def test_typed_array_spread():
    """Typed arrays can be spread into a plain array."""
    i = run("""
let a = new Uint8Array([1, 2, 3])
let v = [...a]
""")
    assert i.globals["v"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# new ArrayBuffer
# ---------------------------------------------------------------------------

def test_new_array_buffer():
    """new ArrayBuffer(n) creates a buffer with byteLength == n."""
    i = run("""
let buf = new ArrayBuffer(16)
let v = buf.byteLength
""")
    assert i.globals["v"] == 16


def test_new_array_buffer_zero():
    """new ArrayBuffer(0) is allowed."""
    i = run("""
let buf = new ArrayBuffer(0)
let v = buf.byteLength
""")
    assert i.globals["v"] == 0


def test_new_array_buffer_with_typed_view():
    """ArrayBuffer + Uint8Array view works together."""
    i = run("""
let buf = new ArrayBuffer(4)
let view = new Uint8Array(buf)
view[0] = 42
let v = [view.length, view[0]]
""")
    assert i.globals["v"] == [4, 42]


def test_array_buffer_is_view():
    """ArrayBuffer.isView returns true for typed arrays."""
    i = run("""
let a = new Uint8Array(4)
let v = ArrayBuffer.isView(a)
""")
    assert i.globals["v"] is True
