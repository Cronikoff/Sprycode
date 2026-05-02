"""Phase 9 feature tests — stdlib completions, match guards, super(), static members."""
import math
import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Array methods
# ---------------------------------------------------------------------------


class TestArrayMethods:
    def test_shift(self):
        i = run("let a = [1, 2, 3]\nlet v = a.shift()")
        assert val(i, "v") == 1

    def test_shift_empty(self):
        i = run("let v = [].shift()")
        assert val(i, "v") is None

    def test_findLast(self):
        i = run("let v = [1, 2, 3, 4, 5].findLast(x => x % 2 == 0)")
        assert val(i, "v") == 4

    def test_findLast_none(self):
        i = run("let v = [1, 3, 5].findLast(x => x % 2 == 0)")
        assert val(i, "v") is None

    def test_findLastIndex(self):
        i = run("let v = [1, 2, 3, 4, 5].findLastIndex(x => x % 2 == 0)")
        assert val(i, "v") == 3

    def test_findLastIndex_none(self):
        i = run("let v = [1, 3, 5].findLastIndex(x => x % 2 == 0)")
        assert val(i, "v") == -1

    def test_toReversed(self):
        i = run("let v = [1, 2, 3].toReversed()")
        assert val(i, "v") == [3, 2, 1]

    def test_toReversed_non_mutating(self):
        i = run("let a = [1, 2, 3]\nlet v = a.toReversed()\nlet w = a")
        assert val(i, "v") == [3, 2, 1]
        assert val(i, "w") == [1, 2, 3]

    def test_toSorted_default(self):
        i = run("let v = [3, 1, 2].toSorted()")
        assert val(i, "v") == [1, 2, 3]

    def test_toSorted_by_key(self):
        i = run("let v = [3, 1, 2].toSorted(x => x)")
        assert val(i, "v") == [1, 2, 3]

    def test_with(self):
        i = run("let v = [1, 2, 3].with(1, 99)")
        assert val(i, "v") == [1, 99, 3]

    def test_with_negative_index(self):
        i = run("let v = [1, 2, 3].with(-1, 99)")
        assert val(i, "v") == [1, 2, 99]

    def test_entries(self):
        i = run("let v = [\"a\", \"b\"].entries()")
        assert val(i, "v") == [[0, "a"], [1, "b"]]

    def test_keys(self):
        i = run("let v = [\"a\", \"b\", \"c\"].keys()")
        assert val(i, "v") == [0, 1, 2]

    def test_values(self):
        i = run("let v = [10, 20, 30].values()")
        assert val(i, "v") == [10, 20, 30]

    def test_flat_with_depth(self):
        i = run("let v = [[1, 2], [3, [4, 5]]].flat()")
        assert val(i, "v") == [1, 2, 3, [4, 5]]

    def test_flat_depth_2(self):
        i = run("let v = [[1, [2]], [3, [4, [5]]]].flat(2)")
        assert val(i, "v") == [1, 2, 3, 4, [5]]

    def test_shuffle_returns_same_elements(self):
        i = run("let v = [1, 2, 3, 4, 5].shuffle")
        result = val(i, "v")
        assert sorted(result) == [1, 2, 3, 4, 5]

    def test_sample_single(self):
        i = run("let v = [1, 2, 3, 4, 5].sample()")
        result = val(i, "v")
        assert result in [1, 2, 3, 4, 5]

    def test_sample_multiple(self):
        i = run("let v = [1, 2, 3, 4, 5].sample(3)")
        result = val(i, "v")
        assert len(result) == 3
        assert all(x in [1, 2, 3, 4, 5] for x in result)

    def test_partition(self):
        i = run("let v = [1, 2, 3, 4, 5].partition(x => x % 2 == 0)")
        assert val(i, "v") == [[2, 4], [1, 3, 5]]

    def test_groupBy(self):
        i = run("let v = [1, 2, 3, 4].groupBy(x => x % 2 == 0 ? \"even\" : \"odd\")")
        assert val(i, "v") == {"even": [2, 4], "odd": [1, 3]}

    def test_tally(self):
        i = run("let v = [\"a\", \"b\", \"a\", \"c\", \"a\"].tally")
        assert val(i, "v") == {"a": 3, "b": 1, "c": 1}

    def test_intersect(self):
        i = run("let v = [1, 2, 3, 4].intersect([2, 4, 6])")
        assert val(i, "v") == [2, 4]

    def test_difference(self):
        i = run("let v = [1, 2, 3, 4].difference([2, 4])")
        assert val(i, "v") == [1, 3]

    def test_union(self):
        i = run("let v = [1, 2, 3].union([2, 3, 4, 5])")
        assert val(i, "v") == [1, 2, 3, 4, 5]

    def test_zip_with_fn(self):
        i = run("let v = [1, 2, 3].zip([4, 5, 6], (a, b) => a + b)")
        assert val(i, "v") == [5, 7, 9]

    def test_toSpliced(self):
        i = run("let v = [1, 2, 3, 4].toSpliced(1, 2)")
        assert val(i, "v") == [1, 4]

    def test_toSpliced_with_insert(self):
        i = run("let v = [1, 2, 3].toSpliced(1, 1, 10, 20)")
        assert val(i, "v") == [1, 10, 20, 3]


# ---------------------------------------------------------------------------
# String methods
# ---------------------------------------------------------------------------


class TestStringMethods:
    def test_toCamelCase(self):
        i = run('let v = "hello world foo".toCamelCase()')
        assert val(i, "v") == "helloWorldFoo"

    def test_toSnakeCase(self):
        i = run('let v = "helloWorldFoo".toSnakeCase()')
        assert val(i, "v") == "hello_world_foo"

    def test_toKebabCase(self):
        i = run('let v = "helloWorldFoo".toKebabCase()')
        assert val(i, "v") == "hello-world-foo"

    def test_toPascalCase(self):
        i = run('let v = "hello world".toPascalCase()')
        assert val(i, "v") == "HelloWorld"

    def test_toTitleCase(self):
        i = run('let v = "hello world".toTitleCase()')
        assert val(i, "v") == "Hello World"

    def test_toBase64_encode(self):
        i = run('let v = "hello".toBase64()')
        assert val(i, "v") == "aGVsbG8="

    def test_fromBase64_decode(self):
        i = run('let v = "aGVsbG8=".fromBase64()')
        assert val(i, "v") == "hello"

    def test_base64_roundtrip(self):
        i = run('let encoded = "SpryCode rocks!".toBase64()\nlet v = encoded.fromBase64()')
        assert val(i, "v") == "SpryCode rocks!"

    def test_levenshtein_basic(self):
        i = run('let v = "kitten".levenshtein("sitting")')
        assert val(i, "v") == 3

    def test_levenshtein_same(self):
        i = run('let v = "abc".levenshtein("abc")')
        assert val(i, "v") == 0

    def test_levenshtein_empty(self):
        i = run('let v = "abc".levenshtein("")')
        assert val(i, "v") == 3

    def test_count(self):
        i = run('let v = "hello world".count("l")')
        assert val(i, "v") == 3

    def test_count_zero(self):
        i = run('let v = "hello".count("z")')
        assert val(i, "v") == 0

    def test_truncate_short(self):
        i = run('let v = "hi".truncate(10)')
        assert val(i, "v") == "hi"

    def test_truncate_long(self):
        i = run('let v = "hello world".truncate(8)')
        assert val(i, "v") == "hello..."

    def test_truncate_custom_suffix(self):
        i = run('let v = "hello world".truncate(7, "…")')
        assert val(i, "v") == "hello …"

    def test_isNumeric_true(self):
        i = run('let v = "123.45".isNumeric()')
        assert val(i, "v") is True

    def test_isNumeric_false(self):
        i = run('let v = "abc".isNumeric()')
        assert val(i, "v") is False

    def test_isAlpha_true(self):
        i = run('let v = "hello".isAlpha()')
        assert val(i, "v") is True

    def test_isAlpha_false(self):
        i = run('let v = "hello1".isAlpha()')
        assert val(i, "v") is False

    def test_isAlphaNum(self):
        i = run('let v = "hello123".isAlphaNum()')
        assert val(i, "v") is True

    def test_isLower(self):
        i = run('let v = "hello".isLower()')
        assert val(i, "v") is True

    def test_isUpper(self):
        i = run('let v = "HELLO".isUpper()')
        assert val(i, "v") is True

    def test_center(self):
        i = run('let v = "hi".center(6)')
        assert val(i, "v") == "  hi  "

    def test_wrap(self):
        i = run('let v = "hello world foo bar".wrap(10)')
        result = val(i, "v")
        assert "hello" in result and "world" in result


# ---------------------------------------------------------------------------
# Number methods
# ---------------------------------------------------------------------------


class TestNumberMethods:
    def test_toExponential(self):
        i = run("let v = (1234.5).toExponential(2)")
        assert val(i, "v") == "1.23e+03"

    def test_sign_positive(self):
        i = run("let v = (5).sign")
        assert val(i, "v") == 1

    def test_sign_negative(self):
        i = run("let v = (0 - 3).sign")
        assert val(i, "v") == -1

    def test_sign_zero(self):
        i = run("let v = (0).sign")
        assert val(i, "v") == 0

    def test_clamp_above(self):
        i = run("let v = (15).clamp(0, 10)")
        assert val(i, "v") == 10

    def test_clamp_below(self):
        i = run("let v = (0 - 5).clamp(0, 10)")
        assert val(i, "v") == 0

    def test_clamp_within(self):
        i = run("let v = (5).clamp(0, 10)")
        assert val(i, "v") == 5

    def test_toRadians(self):
        i = run("let v = (180).toRadians()")
        assert abs(val(i, "v") - math.pi) < 1e-10

    def test_toDegrees(self):
        i = run("let v = (3.141592653589793).toDegrees()")
        assert abs(val(i, "v") - 180.0) < 1e-5

    def test_trunc(self):
        i = run("let v = (3.7).trunc")
        assert val(i, "v") == 3

    def test_Number_clamp(self):
        i = run("let v = Number.clamp(15, 0, 10)")
        assert val(i, "v") == 10

    def test_Number_lerp(self):
        i = run("let v = Number.lerp(0, 100, 0.25)")
        assert val(i, "v") == 25.0

    def test_Number_range_default(self):
        i = run("let v = Number.range(1, 5)")
        assert val(i, "v") == [1, 2, 3, 4]

    def test_Number_range_step(self):
        i = run("let v = Number.range(0, 10, 2)")
        assert val(i, "v") == [0, 2, 4, 6, 8]

    def test_Number_random_in_range(self):
        i = run("let v = Number.random(10, 20)")
        r = val(i, "v")
        assert 10 <= r < 20


# ---------------------------------------------------------------------------
# Object methods
# ---------------------------------------------------------------------------


class TestObjectMethods:
    def test_pick(self):
        i = run('let v = Object.pick({a: 1, b: 2, c: 3}, ["a", "c"])')
        assert val(i, "v") == {"a": 1, "c": 3}

    def test_omit(self):
        i = run('let v = Object.omit({a: 1, b: 2, c: 3}, ["b"])')
        assert val(i, "v") == {"a": 1, "c": 3}

    def test_mapKeys(self):
        i = run('let v = Object.mapKeys({a: 1, b: 2}, k => k + "_key")')
        assert val(i, "v") == {"a_key": 1, "b_key": 2}

    def test_mapValues(self):
        i = run('let v = Object.mapValues({a: 1, b: 2}, x => x * 10)')
        assert val(i, "v") == {"a": 10, "b": 20}

    def test_invert(self):
        i = run('let v = Object.invert({a: "x", b: "y"})')
        assert val(i, "v") == {"x": "a", "y": "b"}

    def test_deepClone(self):
        src = 'let src = {a: {b: 1}}\nlet v = Object.deepClone(src)'
        i = run(src)
        assert val(i, "v") == {"a": {"b": 1}}

    def test_deepClone_independent(self):
        src = '''let src = {a: {b: 1}}
let clone = Object.deepClone(src)
src.a.b = 99
let v = clone.a.b'''
        i = run(src)
        # SpryCode dict mutation via member assignment should not affect clone
        assert val(i, "v") == 1

    def test_deepMerge(self):
        i = run('let v = Object.deepMerge({a: {x: 1}}, {a: {y: 2}})')
        assert val(i, "v") == {"a": {"x": 1, "y": 2}}

    def test_deepMerge_override(self):
        i = run('let v = Object.deepMerge({a: 1, b: 2}, {b: 99, c: 3})')
        assert val(i, "v") == {"a": 1, "b": 99, "c": 3}

    def test_seal_passthrough(self):
        i = run('let v = Object.seal({a: 1})')
        assert val(i, "v") == {"a": 1}

    def test_isFrozen(self):
        i = run('let v = Object.isFrozen({a: 1})')
        assert val(i, "v") is False

    def test_isSealed(self):
        i = run('let v = Object.isSealed({a: 1})')
        assert val(i, "v") is False

    def test_getOwnPropertyNames(self):
        i = run('let v = Object.getOwnPropertyNames({x: 1, y: 2})')
        assert sorted(val(i, "v")) == ["x", "y"]


# ---------------------------------------------------------------------------
# Match guard clauses
# ---------------------------------------------------------------------------


class TestMatchGuards:
    def test_wildcard_guard_pass(self):
        i = run('''let x = 5
let v = match x {
  _ when x > 3 => "big"
  _ => "small"
}''')
        assert val(i, "v") == "big"

    def test_wildcard_guard_fail_falls_to_next(self):
        i = run('''let x = 1
let v = match x {
  _ when x > 3 => "big"
  _ => "small"
}''')
        assert val(i, "v") == "small"

    def test_value_guard_pass(self):
        i = run('''let x = 10
let v = match x {
  10 when x > 5 => "ten big"
  10 => "ten small"
  _ => "other"
}''')
        assert val(i, "v") == "ten big"

    def test_value_guard_fail_falls_through(self):
        i = run('''let x = 10
let v = match x {
  10 when x > 100 => "impossible"
  10 => "ten"
  _ => "other"
}''')
        assert val(i, "v") == "ten"

    def test_range_with_guard(self):
        i = run('''let x = 7
let v = match x {
  1..10 when x % 2 == 0 => "even in range"
  1..10 => "odd in range"
  _ => "out of range"
}''')
        assert val(i, "v") == "odd in range"

    def test_multiple_guards(self):
        i = run('''let x = 42
let v = match x {
  42 when x < 0 => "negative"
  42 when x > 100 => "big"
  42 when x == 42 => "the answer"
  _ => "other"
}''')
        assert val(i, "v") == "the answer"


# ---------------------------------------------------------------------------
# super() constructor calls
# ---------------------------------------------------------------------------


class TestSuperConstructor:
    def test_super_passes_args_to_parent_init(self):
        src = '''class Animal {
  fn init(name) {
    self.name = name
  }
}
class Dog extends Animal {
  fn init(name, breed) {
    super(name)
    self.breed = breed
  }
}
let d = Dog.new("Rex", "Lab")
let v = d.name'''
        i = run(src)
        assert val(i, "v") == "Rex"

    def test_super_sets_breed_on_child(self):
        src = '''class Animal {
  fn init(name) { self.name = name }
}
class Dog extends Animal {
  fn init(name, breed) {
    super(name)
    self.breed = breed
  }
}
let d = Dog.new("Rex", "Lab")
let v = d.breed'''
        i = run(src)
        assert val(i, "v") == "Lab"

    def test_super_no_args(self):
        src = '''class Base {
  fn init() { self.x = 10 }
}
class Child extends Base {
  fn init() {
    super()
    self.y = 20
  }
}
let c = Child.new()
let v = c.x + c.y'''
        i = run(src)
        assert val(i, "v") == 30


# ---------------------------------------------------------------------------
# super.method() calls
# ---------------------------------------------------------------------------


class TestSuperMethod:
    def test_super_method_basic(self):
        src = '''class Base {
  fn greet() { return "hello from base" }
}
class Child extends Base {
  fn greet() {
    let parent = super.greet()
    return parent + " and child"
  }
}
let c = Child.new()
let v = c.greet()'''
        i = run(src)
        assert val(i, "v") == "hello from base and child"

    def test_super_method_with_args(self):
        src = '''class Calc {
  fn add(a, b) { return a + b }
}
class AdvCalc extends Calc {
  fn addDouble(a, b) {
    let base_result = super.add(a, b)
    return base_result * 2
  }
}
let c = AdvCalc.new()
let v = c.addDouble(3, 4)'''
        i = run(src)
        assert val(i, "v") == 14


# ---------------------------------------------------------------------------
# Static class members
# ---------------------------------------------------------------------------


class TestStaticMembers:
    def test_static_let_field(self):
        src = '''class Config {
  let version = "1.0.0"
  fn init() { self.data = {} }
}
let v = Config.version'''
        i = run(src)
        assert val(i, "v") == "1.0.0"

    def test_static_number_field(self):
        src = '''class Math2 {
  let PI = 3.14159
  fn init() {}
}
let v = Math2.PI'''
        i = run(src)
        assert abs(val(i, "v") - 3.14159) < 1e-5

    def test_static_method(self):
        src = '''class MathUtils {
  fn square(x) { return x * x }
}
let v = MathUtils.square(5)'''
        i = run(src)
        assert val(i, "v") == 25

    def test_static_field_does_not_affect_instance(self):
        src = '''class Foo {
  let category = "animal"
  fn init() { self.name = "unnamed" }
}
let f = Foo.new()
let v1 = Foo.category
let v2 = f.name'''
        i = run(src)
        assert val(i, "v1") == "animal"
        assert val(i, "v2") == "unnamed"
