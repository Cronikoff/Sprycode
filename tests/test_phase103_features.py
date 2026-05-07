"""Tests for Phase 103: Proxy, Reflect, TextEncoder/TextDecoder, debugger statement,
and REPL debug commands."""
from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from sprycode.ast_nodes import DebuggerStatement
from sprycode.cli import main, _print_env_vars
from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


# ── debugger statement ────────────────────────────────────────────────────────

class TestDebuggerStatement:
    def test_debugger_no_op(self):
        """debugger; executes without error when no hook is set."""
        i = run("let x = 1; debugger; let v = x + 1;")
        assert val(i) == 2

    def test_debugger_parsed_as_statement(self):
        """debugger is parsed as a DebuggerStatement AST node."""
        tokens = Lexer("debugger;").tokenize()
        prog = Parser(tokens).parse()
        assert len(prog.body) == 1
        assert isinstance(prog.body[0], DebuggerStatement)

    def test_debugger_hook_called(self):
        """debugger; invokes the _debugger_hook when set."""
        calls: list[Any] = []

        def hook(env: Any) -> None:
            calls.append(env._vars.get("x"))

        tokens = Lexer("let x = 42; debugger;").tokenize()
        prog = Parser(tokens).parse()
        i = Interpreter()
        i._debugger_hook = hook
        i.run(prog)
        assert calls == [42]

    def test_debugger_hook_sees_scope(self):
        """debugger; inside a block sees the enclosing scope variables."""
        captured: list[int] = []

        def hook(env: Any) -> None:
            # env._vars at block scope should contain 'y'
            if "y" in env._vars:
                captured.append(env._vars["y"])

        tokens = Lexer("""
function foo(y) {
  debugger;
  return y * 2;
}
let v = foo(7);
""").tokenize()
        prog = Parser(tokens).parse()
        i = Interpreter()
        i._debugger_hook = hook
        i.run(prog)
        assert captured == [7]
        assert i.globals.get("v") == 14

    def test_multiple_debugger_statements(self):
        """Multiple debugger; statements all fire the hook."""
        count = [0]

        def hook(env: Any) -> None:
            count[0] += 1

        tokens = Lexer("debugger; debugger; debugger;").tokenize()
        prog = Parser(tokens).parse()
        i = Interpreter()
        i._debugger_hook = hook
        i.run(prog)
        assert count[0] == 3

    def test_debugger_no_hook_still_runs(self):
        """Without hook, debugger; is truly a no-op — program continues."""
        i = run("""
let result = 0;
for (let k = 0; k < 3; k++) {
  debugger;
  result = result + k;
}
let v = result;
""")
        assert val(i) == 3


# ── Proxy — get trap ─────────────────────────────────────────────────────────

class TestProxyGetTrap:
    def test_get_trap_intercepts(self):
        """Proxy get trap intercepts property access."""
        i = run("""
let handler = { get: function(target, key) { return target[key] * 10; } };
let obj = { x: 5 };
let p = new Proxy(obj, handler);
let v = p.x;
""")
        assert val(i) == 50

    def test_get_trap_fallthrough(self):
        """Without get trap, proxy passes through to target."""
        i = run("""
let p = new Proxy({ y: 99 }, {});
let v = p.y;
""")
        assert val(i) == 99

    def test_get_trap_custom_key(self):
        """Get trap receives target and key arguments."""
        i = run("""
let received = [];
let handler = {
  get: function(target, key) {
    received.push(key);
    return target[key];
  }
};
let obj = { a: 1, b: 2 };
let p = new Proxy(obj, handler);
let v1 = p.a;
let v2 = p.b;
let v = received.length;
""")
        assert val(i) == 2

    def test_proxy_callable(self):
        """Proxy() without new still creates a proxy."""
        i = run("""
let obj = { n: 7 };
let p = Proxy(obj, {});
let v = p.n;
""")
        assert val(i) == 7


# ── Proxy — set trap ─────────────────────────────────────────────────────────

class TestProxySetTrap:
    def test_set_trap_intercepts(self):
        """Proxy set trap intercepts property assignment."""
        i = run("""
let log = [];
let handler = {
  set: function(target, key, value) {
    log.push(key);
    target[key] = value;
    return true;
  }
};
let obj = {};
let p = new Proxy(obj, handler);
p.name = "Alice";
p.age = 30;
let v = log.length;
""")
        assert val(i) == 2

    def test_set_trap_modifies_target(self):
        """Proxy set trap can modify the value before setting."""
        i = run("""
let handler = {
  set: function(target, key, value) {
    target[key] = value * 2;
    return true;
  }
};
let obj = {};
let p = new Proxy(obj, handler);
p.x = 5;
let v = obj.x;
""")
        assert val(i) == 10


# ── Proxy — has trap ─────────────────────────────────────────────────────────

class TestProxyHasTrap:
    def test_has_trap_intercepts_in_operator(self):
        """Proxy has trap is invoked by 'in' operator."""
        i = run("""
let handler = {
  has: function(target, key) { return key in target; }
};
let obj = { x: 1 };
let p = new Proxy(obj, handler);
let v = "x" in p;
""")
        assert val(i) is True

    def test_has_trap_missing_key(self):
        """has trap returns false for missing key."""
        i = run("""
let p = new Proxy({ x: 1 }, {});
let v = "z" in p;
""")
        assert val(i) is False

    def test_has_trap_custom(self):
        """has trap can override the default behavior."""
        i = run("""
let handler = {
  has: function(target, key) { return true; }
};
let p = new Proxy({}, handler);
let v = "anything" in p;
""")
        assert val(i) is True


# ── Proxy.revocable ───────────────────────────────────────────────────────────

class TestProxyRevocable:
    def test_revocable_returns_proxy_and_revoke(self):
        """Proxy.revocable returns { proxy, revoke }."""
        i = run("""
let r = Proxy.revocable({ x: 1 }, {});
let v = r.proxy.x;
""")
        assert val(i) == 1


# ── Reflect API ───────────────────────────────────────────────────────────────

class TestReflectOwnKeys:
    def test_own_keys_dict(self):
        """Reflect.ownKeys returns own enumerable keys of a dict."""
        i = run("""
let obj = { a: 1, b: 2, c: 3 };
let v = Reflect.ownKeys(obj).length;
""")
        assert val(i) == 3

    def test_own_keys_empty(self):
        """Reflect.ownKeys on empty object returns []."""
        i = run("""
let v = Reflect.ownKeys({}).length;
""")
        assert val(i) == 0


class TestReflectGetSet:
    def test_reflect_get(self):
        """Reflect.get retrieves a property value."""
        i = run("""
let obj = { x: 42 };
let v = Reflect.get(obj, "x");
""")
        assert val(i) == 42

    def test_reflect_set(self):
        """Reflect.set sets a property and returns true."""
        i = run("""
let obj = { x: 1 };
let ok = Reflect.set(obj, "x", 99);
let v = obj.x;
""")
        assert val(i) == 99
        assert i.globals.get("ok") is True

    def test_reflect_set_new_key(self):
        """Reflect.set can add a new property."""
        i = run("""
let obj = {};
Reflect.set(obj, "name", "Alice");
let v = obj.name;
""")
        assert val(i) == "Alice"


class TestReflectHas:
    def test_reflect_has_true(self):
        """Reflect.has returns true for existing key."""
        i = run("""
let obj = { x: 1 };
let v = Reflect.has(obj, "x");
""")
        assert val(i) is True

    def test_reflect_has_false(self):
        """Reflect.has returns false for missing key."""
        i = run("""
let obj = { x: 1 };
let v = Reflect.has(obj, "y");
""")
        assert val(i) is False


class TestReflectDeleteProperty:
    def test_delete_property(self):
        """Reflect.deleteProperty removes a property."""
        i = run("""
let obj = { x: 1, y: 2 };
let ok = Reflect.deleteProperty(obj, "x");
let v = Reflect.has(obj, "x");
""")
        assert i.globals.get("ok") is True
        assert val(i) is False

    def test_delete_missing_returns_false(self):
        """Reflect.deleteProperty on missing key returns false."""
        i = run("""
let obj = {};
let v = Reflect.deleteProperty(obj, "nonexistent");
""")
        assert val(i) is False


class TestReflectApply:
    def test_reflect_apply(self):
        """Reflect.apply calls a function with given args."""
        i = run("""
function add(a, b) { return a + b; }
let v = Reflect.apply(add, null, [3, 4]);
""")
        assert val(i) == 7


class TestReflectConstruct:
    def test_reflect_construct(self):
        """Reflect.construct creates an instance of a class."""
        i = run("""
class Point {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }
}
let p = Reflect.construct(Point, [3, 4]);
let v = p.x + p.y;
""")
        assert val(i) == 7


# ── TextEncoder / TextDecoder ────────────────────────────────────────────────

class TestTextEncoder:
    def test_encode_returns_bytes(self):
        """TextEncoder.encode returns a byte array."""
        i = run("""
let enc = new TextEncoder();
let bytes = enc.encode("hello");
let v = bytes.length;
""")
        assert val(i) == 5

    def test_encode_ascii(self):
        """ASCII characters encode to single bytes."""
        i = run("""
let enc = new TextEncoder();
let bytes = enc.encode("A");
let v = bytes[0];
""")
        assert val(i) == 65  # ASCII 'A'

    def test_encoding_property(self):
        """TextEncoder.encoding is 'utf-8'."""
        i = run("""
let enc = new TextEncoder();
let v = enc.encoding;
""")
        assert val(i) == "utf-8"

    def test_encoder_callable_without_new(self):
        """TextEncoder() without new also works."""
        i = run("""
let enc = TextEncoder();
let bytes = enc.encode("hi");
let v = bytes.length;
""")
        assert val(i) == 2


class TestTextDecoder:
    def test_decode_utf8(self):
        """TextDecoder.decode converts bytes back to string."""
        i = run("""
let enc = new TextEncoder();
let dec = new TextDecoder();
let bytes = enc.encode("hello");
let v = dec.decode(bytes);
""")
        assert val(i) == "hello"

    def test_decode_empty(self):
        """Decoding empty bytes returns empty string."""
        i = run("""
let dec = new TextDecoder();
let v = dec.decode([]);
""")
        assert val(i) == ""

    def test_decode_unicode(self):
        """TextDecoder handles UTF-8 encoded Unicode."""
        i = run("""
let enc = new TextEncoder();
let dec = new TextDecoder();
let text = "héllo";
let v = dec.decode(enc.encode(text));
""")
        assert val(i) == "héllo"

    def test_encoder_decoder_roundtrip(self):
        """Encoder → decoder round-trip preserves strings."""
        i = run("""
let enc = new TextEncoder();
let dec = new TextDecoder();
let original = "SpryCode 🚀";
let v = dec.decode(enc.encode(original));
""")
        assert val(i) == "SpryCode 🚀"

    def test_decoder_encoding_property(self):
        """TextDecoder.encoding is 'utf-8'."""
        i = run("""
let dec = new TextDecoder("utf-8");
let v = dec.encoding;
""")
        assert val(i) == "utf-8"


# ── REPL debug commands ───────────────────────────────────────────────────────

class TestReplDebugCommands:
    def test_repl_vars_command(self):
        """REPL .vars command shows user-defined variables."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input="let x = 42;\n.vars\n.exit\n")
        assert result.exit_code == 0
        assert "x" in result.output

    def test_repl_reset_command(self):
        """REPL .reset command resets interpreter state."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input="let counter = 99;\n.reset\n.exit\n")
        assert result.exit_code == 0
        assert "reset" in result.output.lower()

    def test_repl_type_command(self):
        """REPL .type command evaluates typeof an expression."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input='.type 42\n.exit\n')
        assert result.exit_code == 0
        assert "number" in result.output

    def test_repl_type_string(self):
        """REPL .type on a string returns 'string'."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input='.type "hello"\n.exit\n')
        assert result.exit_code == 0
        assert "string" in result.output

    def test_repl_ast_command(self):
        """REPL .ast command shows the AST of an expression."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input='.ast 1 + 2\n.exit\n')
        assert result.exit_code == 0
        # Should display some AST representation
        assert "Binary" in result.output or "Number" in result.output

    def test_repl_help_shows_new_commands(self):
        """REPL .help shows the new debug commands."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input=".help\n.exit\n")
        assert result.exit_code == 0
        assert ".vars" in result.output
        assert ".reset" in result.output
        assert ".load" in result.output
        assert ".type" in result.output
        assert ".ast" in result.output

    def test_repl_debug_flag(self):
        """REPL --debug flag enables debug mode."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl", "--debug"], input=".exit\n")
        assert result.exit_code == 0

    def test_repl_load_nonexistent_file(self):
        """REPL .load on a nonexistent file shows an error."""
        runner = CliRunner()
        result = runner.invoke(main, ["repl"], input=".load /nonexistent/path.spry\n.exit\n")
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_repl_multiline_with_debug(self):
        """REPL handles multi-line input in debug mode."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["repl", "--debug"],
            input="let x = 1;\nlet y = 2;\n.vars\n.exit\n",
        )
        assert result.exit_code == 0


# ── spry run --debug flag ────────────────────────────────────────────────────

class TestRunDebugFlag:
    def test_run_debug_help(self):
        """spry run --help shows --debug flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "--debug" in result.output

    def test_print_env_vars_output(self, tmp_path: Any):
        """_print_env_vars prints variables in an environment."""
        from sprycode.interpreter import Environment
        env = Environment()
        env.define("alpha", 1, mutable=True)
        env.define("beta", "hello", mutable=True)

        output_lines: list[str] = []

        import io, contextlib
        buf = io.StringIO()
        # _print_env_vars uses click.echo or print to stderr — capture via monkeypatching
        import sprycode.cli as cli_mod
        orig = cli_mod._debug_print

        def capture(msg: str) -> None:
            output_lines.append(msg)

        cli_mod._debug_print = capture
        try:
            _print_env_vars(env)
        finally:
            cli_mod._debug_print = orig

        combined = "\n".join(output_lines)
        assert "alpha" in combined
        assert "beta" in combined
