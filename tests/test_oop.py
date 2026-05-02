"""
Tests for SpryCode OOP features:
- enum declarations
- struct declarations
- class declarations with self, methods, init
- class inheritance (extends)
- new keyword for class construction
- member assignment (obj.prop = val, self.prop = val)
- compound member assignment (obj.prop += val, self.prop += val)
- index assignment (arr[i] = val, dict[key] = val)
"""

import pytest

from sprycode.interpreter import Interpreter, SpryClass, SpryEnum, SpryInstance, SpryRuntimeError, SpryStruct
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.runtime.stdlib import SpryLogger


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interp = Interpreter(logger=SpryLogger(output=[]))
    interp.run(program)
    return interp


def eval_expr(source: str) -> object:
    full = f"let __result = {source}"
    return run(full).globals.get("__result")


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class TestEnum:
    def test_enum_registered_in_env(self):
        interp = run("enum Color { Red, Green, Blue }")
        val = interp.globals.get("Color")
        assert isinstance(val, SpryEnum)

    def test_enum_variant_access(self):
        interp = run("enum Status { Active, Inactive }\nlet s = Status.Active")
        s = interp.globals.get("s")
        assert isinstance(s, dict)
        assert s["__variant__"] == "Active"

    def test_enum_variant_name(self):
        interp = run("enum Direction { North, South, East, West }\nlet v = Direction.East.__variant__")
        assert interp.globals.get("v") == "East"

    def test_enum_multiple_variants(self):
        interp = run("""
enum Shape { Circle, Square, Triangle }
let a = Shape.Circle.__variant__
let b = Shape.Triangle.__variant__
""")
        assert interp.globals.get("a") == "Circle"
        assert interp.globals.get("b") == "Triangle"

    def test_enum_in_match(self):
        interp = run("""
enum Status { Active, Inactive }
let s = Status.Active
var label = "unknown"
match s.__variant__ {
    "Active"   => label = "yes"
    "Inactive" => label = "no"
    _           => label = "other"
}
""")
        assert interp.globals.get("label") == "yes"

    def test_enum_wrong_variant_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("enum Color { Red }\nlet x = Color.Blue")


# ---------------------------------------------------------------------------
# Struct
# ---------------------------------------------------------------------------


class TestStruct:
    def test_struct_registered(self):
        interp = run("struct Point { x: Number, y: Number }")
        val = interp.globals.get("Point")
        assert isinstance(val, SpryStruct)

    def test_struct_create(self):
        interp = run("""
struct Point { x: Number, y: Number }
let p = Point(3, 4)
let px = p.x
let py = p.y
""")
        assert interp.globals.get("px") == 3
        assert interp.globals.get("py") == 4

    def test_struct_missing_fields_null(self):
        interp = run("""
struct Pair { first: Text, second: Text }
let p = Pair("hello")
let s = p.second
""")
        assert interp.globals.get("s") is None

    def test_struct_as_dict(self):
        interp = run("""
struct User { name: Text, age: Number }
let u = User("Alice", 30)
let name = u.name
let age = u.age
""")
        assert interp.globals.get("name") == "Alice"
        assert interp.globals.get("age") == 30

    def test_struct_sentinel_field(self):
        interp = run("""
struct Config { host: Text, port: Number }
let c = Config("localhost", 8080)
let t = c.__struct__
""")
        assert interp.globals.get("t") == "Config"


# ---------------------------------------------------------------------------
# Class
# ---------------------------------------------------------------------------


class TestClass:
    def test_class_registered(self):
        interp = run("class Animal { var name = \"\" }")
        val = interp.globals.get("Animal")
        assert isinstance(val, SpryClass)

    def test_class_instantiation(self):
        interp = run("""
class Counter {
    var count = 0
}
let c = Counter()
""")
        c = interp.globals.get("c")
        assert isinstance(c, SpryInstance)

    def test_class_default_field(self):
        interp = run("""
class Box {
    var value = 42
}
let b = Box()
let v = b.value
""")
        assert interp.globals.get("v") == 42

    def test_class_method_call(self):
        interp = run("""
class Greeter {
    var name = "World"
    fn greet() {
        return "Hello, " + self.name
    }
}
let g = Greeter()
let msg = g.greet()
""")
        assert interp.globals.get("msg") == "Hello, World"

    def test_class_self_mutation(self):
        interp = run("""
class Counter {
    var count = 0
    fn increment() {
        self.count = self.count + 1
    }
    fn value() {
        return self.count
    }
}
let c = Counter()
c.increment()
c.increment()
c.increment()
let v = c.value()
""")
        assert interp.globals.get("v") == 3

    def test_class_compound_self_mutation(self):
        interp = run("""
class Counter {
    var count = 0
    fn inc() { self.count += 1 }
    fn get() { return self.count }
}
let c = Counter()
c.inc()
c.inc()
let v = c.get()
""")
        assert interp.globals.get("v") == 2

    def test_class_method_with_args(self):
        interp = run("""
class Accumulator {
    var total = 0
    fn add(n) {
        self.total = self.total + n
    }
    fn result() {
        return self.total
    }
}
let a = Accumulator()
a.add(5)
a.add(10)
a.add(3)
let v = a.result()
""")
        assert interp.globals.get("v") == 18

    def test_class_init_method(self):
        interp = run("""
class Person {
    var name = ""
    var age = 0
    fn init(n, a) {
        self.name = n
        self.age = a
    }
    fn greet() {
        return "Hi " + self.name
    }
}
let p = Person("Alice", 30)
let g = p.greet()
let age = p.age
""")
        assert interp.globals.get("g") == "Hi Alice"
        assert interp.globals.get("age") == 30

    def test_class_direct_field_mutation(self):
        """Direct mutation (count += 1 inside method) should sync to instance."""
        interp = run("""
class Acc {
    var total = 0
    fn add(n) {
        total = total + n
    }
    fn get() { return total }
}
let a = Acc()
a.add(7)
a.add(3)
let v = a.get()
""")
        assert interp.globals.get("v") == 10

    def test_class_multiple_instances_independent(self):
        interp = run("""
class Box {
    var value = 0
    fn set(v) { self.value = v }
    fn get() { return self.value }
}
let a = Box()
let b = Box()
a.set(10)
b.set(20)
let va = a.get()
let vb = b.get()
""")
        assert interp.globals.get("va") == 10
        assert interp.globals.get("vb") == 20


# ---------------------------------------------------------------------------
# New keyword
# ---------------------------------------------------------------------------


class TestNewKeyword:
    def test_new_basic(self):
        interp = run("""
class Counter {
    var count = 0
    fn get() { return self.count }
}
let c = new Counter()
let v = c.get()
""")
        assert interp.globals.get("v") == 0

    def test_new_with_init(self):
        interp = run("""
class Box {
    var value = 0
    fn init(v) { self.value = v }
    fn get() { return self.value }
}
let b = new Box(42)
let v = b.get()
""")
        assert interp.globals.get("v") == 42

    def test_new_with_multiple_args(self):
        interp = run("""
class Point {
    var x = 0
    var y = 0
    fn init(px, py) {
        self.x = px
        self.y = py
    }
    fn distance() {
        return self.x * self.x + self.y * self.y
    }
}
let p = new Point(3, 4)
let d = p.distance()
""")
        assert interp.globals.get("d") == 25


# ---------------------------------------------------------------------------
# Class Inheritance
# ---------------------------------------------------------------------------


class TestInheritance:
    def test_basic_inheritance(self):
        interp = run("""
class Animal {
    var name = ""
    fn speak() { return self.name + " says hi" }
}
class Dog extends Animal {
    fn bark() { return self.name + " barks" }
}
let d = new Dog()
d.name = "Rex"
let s = d.speak()
let b = d.bark()
""")
        assert interp.globals.get("s") == "Rex says hi"
        assert interp.globals.get("b") == "Rex barks"

    def test_inherited_fields(self):
        interp = run("""
class Base {
    var x = 10
}
class Child extends Base {
    var y = 20
}
let c = new Child()
let vx = c.x
let vy = c.y
""")
        assert interp.globals.get("vx") == 10
        assert interp.globals.get("vy") == 20

    def test_subclass_init_inherits_fields(self):
        interp = run("""
class Animal {
    var name = ""
    fn speak() { return self.name }
}
class Cat extends Animal {
    fn init(n) { self.name = n }
}
let c = new Cat("Whiskers")
let v = c.speak()
""")
        assert interp.globals.get("v") == "Whiskers"

    def test_method_override(self):
        interp = run("""
class Animal {
    fn speak() { return "generic" }
}
class Dog extends Animal {
    fn speak() { return "woof" }
}
let d = new Dog()
let v = d.speak()
""")
        assert interp.globals.get("v") == "woof"


# ---------------------------------------------------------------------------
# Member Assignment
# ---------------------------------------------------------------------------


class TestMemberAssignment:
    def test_dict_member_assign(self):
        interp = run("""
var obj = {x: 1, y: 2}
obj.x = 99
let v = obj.x
""")
        assert interp.globals.get("v") == 99

    def test_dict_member_compound_assign(self):
        interp = run("""
var obj = {score: 5}
obj.score += 3
let v = obj.score
""")
        assert interp.globals.get("v") == 8

    def test_instance_member_assign(self):
        interp = run("""
class Box { var value = 0 }
let b = new Box()
b.value = 77
let v = b.value
""")
        assert interp.globals.get("v") == 77

    def test_instance_member_compound_assign(self):
        interp = run("""
class Box { var score = 10 }
let b = new Box()
b.score -= 4
let v = b.score
""")
        assert interp.globals.get("v") == 6


# ---------------------------------------------------------------------------
# Index Assignment
# ---------------------------------------------------------------------------


class TestIndexAssignment:
    def test_list_index_assign(self):
        interp = run("""
var arr = [1, 2, 3]
arr[1] = 99
let v = arr[1]
""")
        assert interp.globals.get("v") == 99

    def test_list_index_assign_first(self):
        interp = run("""
var arr = [10, 20, 30]
arr[0] = 0
let v = arr[0]
""")
        assert interp.globals.get("v") == 0

    def test_dict_index_assign(self):
        interp = run("""
var d = {a: 1, b: 2}
d["a"] = 100
let v = d["a"]
""")
        assert interp.globals.get("v") == 100

    def test_index_assign_in_loop(self):
        interp = run("""
var arr = [0, 0, 0, 0, 0]
var i = 0
while i < 5 {
    arr[i] = i * 2
    i += 1
}
let v = arr[4]
""")
        assert interp.globals.get("v") == 8
