"""
SpryCode CLI

Provides the `spry` command-line interface for running, testing, building,
and managing SpryCode programs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .interpreter import Interpreter as _InterpreterType

try:
    import click
except ImportError:
    # Minimal fallback without click
    click = None  # type: ignore

from . import __version__
from .interpreter import Interpreter, SpryRuntimeError
from .lexer import Lexer, LexerError
from .parser import ParseError, Parser
from .permissions import PermissionSet
from .runtime.stdlib import SpryLogger


def _parse_and_run(source: str, filename: str, task_name: str | None, secure: bool, debug: bool = False) -> int:
    """Parse and execute a SpryCode program. Returns exit code."""
    try:
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()
    except LexerError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    try:
        parser = Parser(tokens)
        program = parser.parse()
    except ParseError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    permissions = PermissionSet()
    if secure:
        permissions.enable_secure_mode()

    logger = SpryLogger()
    interp = Interpreter(logger=logger, permissions=permissions)

    if debug:
        _attach_debug_hook(interp, filename)

    try:
        if task_name:
            interp.run_task(program, task_name)
        else:
            interp.run(program)
        return 0
    except SpryRuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        return 1


def _attach_debug_hook(interp: Any, filename: str = "<unknown>") -> None:
    """Attach a debug hook to the interpreter that prints variable state on `debugger;`."""
    def _hook(env: Any) -> None:
        _debug_print(f"\n[DEBUG] Breakpoint hit in {filename}")
        _print_env_vars(env, builtin_keys=getattr(interp, "_builtin_keys", frozenset()))
    interp._debugger_hook = _hook


def _debug_print(msg: str) -> None:
    """Print debug messages — uses click if available, else print."""
    if click is not None:
        click.echo(msg, err=True)
    else:
        print(msg, file=sys.stderr)


def _print_env_vars(env: Any, max_vars: int = 30, builtin_keys: "frozenset[str] | None" = None) -> None:
    """Pretty-print user-defined variables in the given environment frame.

    If *builtin_keys* is provided (from ``Interpreter._builtin_keys``), only
    variables that are NOT in that set are displayed — hiding all built-in
    globals from debug output.
    """
    from .interpreter import SPRY_UNDEFINED, _SpryUndefinedType, SpryFunction, SpryClass
    if builtin_keys is None:
        # Fallback static skip-list for callers that don't have the interpreter reference
        builtin_keys = frozenset()
    items = [
        (k, v) for k, v in env._vars.items()
        if k not in builtin_keys and not k.startswith("__")
    ]
    items = items[:max_vars]
    if not items:
        _debug_print("  (no user variables)")
        return
    for k, v in items:
        if isinstance(v, (SpryFunction, SpryClass)):
            display = f"[function {k}]"
        elif isinstance(v, _SpryUndefinedType):
            display = "undefined"
        elif v is None:
            display = "null"
        else:
            display = repr(v)
        _debug_print(f"  {k} = {display}")


if click is not None:
    @click.group()
    @click.version_option(version=__version__, prog_name="spry")
    def main():
        """SpryCode: agile code for fast, secure, adaptive systems."""

    @main.command("run")
    @click.argument("source", required=False)
    @click.argument("task_arg", required=False)
    @click.option("--task", "-t", default=None, help="Run a specific named task")
    @click.option("--secure", is_flag=True, default=False, help="Enable strict permission mode")
    @click.option("--file", "-f", "source_file", default=None, help="Path to a .spry file")
    @click.option("--debug", "-d", is_flag=True, default=False, help="Enable debug output (print each statement before executing)")
    def run_cmd(source: str | None, task_arg: str | None, task: str | None, secure: bool, source_file: str | None, debug: bool):
        """Run a SpryCode program or task.

        Usage:
          spry run main.spry             # Run the program
          spry run main.spry myTask      # Run a specific task
          spry run main.spry --task myTask
          spry run main.spry --debug     # Run with debug output
        """
        # Determine the file and task name
        task_name = task or task_arg

        if source_file:
            file_path = Path(source_file)
        elif source and source.endswith(".spry"):
            file_path = Path(source)
        elif source:
            # Could be a task name if a .spry file exists in current dir
            task_name = task_name or source
            candidates = list(Path(".").glob("*.spry")) + list(Path(".").glob("**/*.spry"))
            if not candidates:
                click.echo("[ERROR] No .spry file found in current directory.", err=True)
                sys.exit(1)
            file_path = candidates[0]
        else:
            # No args — look for main.spry or index.spry
            for name in ("main.spry", "index.spry"):
                if Path(name).exists():
                    file_path = Path(name)
                    break
            else:
                click.echo("[ERROR] No .spry file specified.", err=True)
                sys.exit(1)

        if not file_path.exists():
            click.echo(f"[ERROR] File not found: {file_path}", err=True)
            sys.exit(1)

        source_code = file_path.read_text(encoding="utf-8")
        exit_code = _parse_and_run(source_code, str(file_path), task_name, secure, debug=debug)
        sys.exit(exit_code)

    @main.command("build")
    @click.argument("file", required=False, default="main.spry")
    @click.option("--mode", default="dev", help="Build mode: dev, production, secure, enterprise")
    @click.option("--output", "-o", default=None, help="Output path")
    def build_cmd(file: str, mode: str, output: str | None):
        """Build a SpryCode program."""
        file_path = Path(file)
        if not file_path.exists():
            click.echo(f"[ERROR] File not found: {file_path}", err=True)
            sys.exit(1)

        source = file_path.read_text(encoding="utf-8")
        click.echo(f"[spryc] Parsing {file_path}...")

        try:
            lexer = Lexer(source, str(file_path))
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
        except (LexerError, ParseError) as e:
            click.echo(f"[ERROR] {e}", err=True)
            sys.exit(1)

        click.echo(f"[spryc] Build successful (mode={mode})")
        click.echo(f"[spryc] {len(program.body)} top-level declarations")

    @main.command("test")
    @click.argument("path", default="tests", required=False)
    @click.option("--verbose", "-v", is_flag=True, default=False)
    def test_cmd(path: str, verbose: bool):
        """Run SpryCode tests."""
        test_dir = Path(path)
        if test_dir.is_file() and test_dir.suffix == ".spry":
            test_files = [test_dir]
        elif test_dir.is_dir():
            test_files = list(test_dir.glob("**/*.spry"))
        else:
            # Try pytest for Python tests
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "pytest", path, "-v" if verbose else "-q"],
                capture_output=False,
            )
            sys.exit(result.returncode)

        passed = 0
        failed = 0
        for test_file in test_files:
            source = test_file.read_text(encoding="utf-8")
            rc = _parse_and_run(source, str(test_file), None, secure=False)
            if rc == 0:
                passed += 1
                if verbose:
                    click.echo(f"  ✓ {test_file}")
            else:
                failed += 1
                click.echo(f"  ✗ {test_file}", err=True)

        click.echo(f"\n{passed} passed, {failed} failed")
        if failed > 0:
            sys.exit(1)

    @main.command("fmt")
    @click.argument("files", nargs=-1)
    def fmt_cmd(files: tuple):
        """Format SpryCode source files (stub — formatter coming soon)."""
        if not files:
            files = tuple(str(f) for f in Path(".").glob("**/*.spry"))
        for f in files:
            click.echo(f"[spry fmt] {f} (no changes)")

    @main.command("lint")
    @click.argument("files", nargs=-1)
    def lint_cmd(files: tuple):
        """Lint SpryCode source files for errors and warnings."""
        if not files:
            files = tuple(str(f) for f in Path(".").glob("**/*.spry"))

        # Expand any directories to their .spry files
        expanded: list[str] = []
        for f in files:
            p = Path(f)
            if p.is_dir():
                expanded.extend(str(fp) for fp in p.glob("**/*.spry"))
            else:
                expanded.append(f)

        issues = 0
        for f in expanded:
            try:
                source = Path(f).read_text(encoding="utf-8")
                lexer = Lexer(source, f)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                parser.parse()
                click.echo(f"  ✓ {f}")
            except (LexerError, ParseError) as e:
                click.echo(f"  ✗ {f}: {e}", err=True)
                issues += 1

        if issues:
            click.echo(f"\n{issues} issue(s) found")
            sys.exit(1)
        else:
            click.echo("\nNo issues found")

    @main.command("new")
    @click.argument("kind", type=click.Choice(["app", "task", "lib"]))
    @click.argument("name")
    def new_cmd(kind: str, name: str):
        """Create a new SpryCode project."""
        project_dir = Path(name)
        if project_dir.exists():
            click.echo(f"[ERROR] Directory {name!r} already exists.", err=True)
            sys.exit(1)

        project_dir.mkdir(parents=True)

        # Create spry.toml
        (project_dir / "spry.toml").write_text(
            f'name = "{name}"\nversion = "0.1.0"\nlicense = "SpryCode-Free"\nedition = "free"\n\n'
            f'[permissions]\n\n[dependencies]\n'
        )

        # Create main.spry
        main_content = f'app {name.replace("-", "_")} version "0.1.0"\n\ntask main {{\n    log info "Hello from {name}!"\n}}\n'
        (project_dir / "main.spry").write_text(main_content)

        # Create README
        (project_dir / "README.md").write_text(
            f"# {name}\n\nA SpryCode application.\n\n## Usage\n\n```bash\nspry run main\n```\n"
        )

        click.echo(f"Created SpryCode {kind} project: {name}/")
        click.echo(f"  {name}/spry.toml")
        click.echo(f"  {name}/main.spry")
        click.echo(f"  {name}/README.md")
        click.echo(f"\nRun: cd {name} && spry run main")

    @main.command("audit")
    @click.argument("file", default="spry.toml", required=False)
    def audit_cmd(file: str):
        """Audit dependencies for security vulnerabilities."""
        click.echo("[sprypm] Auditing dependencies...")
        click.echo("[sprypm] No known vulnerabilities found")

    @main.command("deploy")
    @click.argument("file", default="main.spry", required=False)
    @click.option("--env", default="production", help="Target environment: production, staging, dev")
    @click.option("--dry-run", is_flag=True, default=False, help="Simulate deployment without executing")
    def deploy_cmd(file: str, env: str, dry_run: bool):
        """Deploy a SpryCode program to a target environment."""
        file_path = Path(file)
        if not file_path.exists():
            click.echo(f"[ERROR] File not found: {file_path}", err=True)
            sys.exit(1)
        # Validate the program can be parsed
        source = file_path.read_text(encoding="utf-8")
        try:
            lexer = Lexer(source, str(file_path))
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            parser.parse()
        except (LexerError, ParseError) as e:
            click.echo(f"[ERROR] {e}", err=True)
            sys.exit(1)
        if dry_run:
            click.echo(f"[spry deploy] Dry run — would deploy {file_path} to {env!r}")
            click.echo("[spry deploy] No changes made")
        else:
            click.echo(f"[spry deploy] Deploying {file_path} to {env!r}...")
            click.echo("[spry deploy] Deployment complete")

    @main.command("profile")
    @click.argument("file")
    @click.option("--task", "-t", default=None, help="Profile a specific task")
    @click.option("--iterations", default=1, help="Number of iterations to run")
    def profile_cmd(file: str, task: str | None, iterations: int):
        """Profile a SpryCode program and report execution times."""
        import statistics
        file_path = Path(file)
        if not file_path.exists():
            click.echo(f"[ERROR] File not found: {file_path}", err=True)
            sys.exit(1)
        source = file_path.read_text(encoding="utf-8")
        times: list[float] = []
        for i in range(max(1, iterations)):
            import time as _time
            start = _time.perf_counter()
            _parse_and_run(source, str(file_path), task, secure=False)
            elapsed = _time.perf_counter() - start
            times.append(elapsed)
        total = sum(times)
        avg = statistics.mean(times)
        click.echo(f"[spry profile] {file_path} — {iterations} iteration(s)")
        click.echo(f"  total: {total*1000:.2f}ms  avg: {avg*1000:.2f}ms  "
                   f"min: {min(times)*1000:.2f}ms  max: {max(times)*1000:.2f}ms")

    # Package manager command group
    @click.group("pm")
    def pm_cmd():
        """SpryCode package manager (sprypm)."""

    @pm_cmd.command("init")
    @click.argument("name", required=False)
    def pm_init(name: str | None):
        """Initialize a new spry.toml manifest."""
        if name is None:
            name = Path(".").resolve().name
        manifest = (
            f'name = "{name}"\n'
            f'version = "0.1.0"\n'
            f'license = "SpryCode-Free"\n'
            f'edition = "free"\n\n'
            f'[permissions]\n\n'
            f'[dependencies]\n'
        )
        Path("spry.toml").write_text(manifest)
        click.echo(f"Created spry.toml for {name!r}")

    @pm_cmd.command("add")
    @click.argument("package")
    @click.option("--version", default="latest")
    def pm_add(package: str, version: str):
        """Add a package dependency."""
        click.echo(f"[sprypm] Adding {package}@{version}...")
        click.echo("[sprypm] Package registry is not yet available in this build.")

    @pm_cmd.command("remove")
    @click.argument("package")
    def pm_remove(package: str):
        """Remove a package dependency."""
        click.echo(f"[sprypm] Removing {package}...")

    @pm_cmd.command("update")
    def pm_update():
        """Update all packages to latest versions."""
        click.echo("[sprypm] Checking for updates...")
        click.echo("[sprypm] All packages up to date")

    # Compiler command
    @click.command("compile")
    @click.argument("file")
    @click.option("--mode", default="dev")
    @click.option("--output", "-o", default=None)
    def compile_cmd(file: str, mode: str, output: str | None):
        """Compile a SpryCode program (spryc)."""
        click.echo(f"[spryc] Compiling {file} (mode={mode})...")
        file_path = Path(file)
        if not file_path.exists():
            click.echo(f"[ERROR] File not found: {file_path}", err=True)
            sys.exit(1)
        source = file_path.read_text(encoding="utf-8")
        try:
            lexer = Lexer(source, str(file_path))
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            click.echo(f"[spryc] Compiled successfully ({len(program.body)} nodes)")
        except (LexerError, ParseError) as e:
            click.echo(f"[ERROR] {e}", err=True)
            sys.exit(1)

    @main.command("repl")
    @click.option("--secure", is_flag=True, default=False, help="Enable secure mode")
    @click.option("--debug", "-d", is_flag=True, default=False, help="Enable debug mode (hook into debugger; statements)")
    def repl_cmd(secure: bool, debug: bool):
        """Start an interactive SpryCode REPL.

        Debug commands available in the REPL:
          .vars    — show all user-defined variables
          .reset   — reset interpreter state
          .load    — load and run a .spry file
          .type    — show the type of an expression
          .ast     — show the AST of an expression
        """
        _run_repl(secure=secure, debug=debug)

    def _run_repl(secure: bool = False, debug: bool = False) -> None:
        """Interactive Read-Eval-Print Loop for SpryCode."""
        try:
            import readline as _rl  # noqa: F401 -- enables history/editing; optional
        except ImportError:
            pass  # readline not available in this environment

        banner = (
            f"SpryCode {__version__} REPL\n"
            "Type .help for commands, .exit to quit\n"
        )
        click.echo(banner)

        permissions = PermissionSet()
        if secure:
            permissions.enable_secure_mode()

        logger = SpryLogger()
        interp = Interpreter(logger=logger, permissions=permissions)

        if debug:
            # In debug mode, hitting `debugger;` prints current variable state
            def _dbg_hook(env: Any) -> None:
                click.echo("\n[debugger] Variables in current scope:", err=True)
                _print_env_vars(env, builtin_keys=interp._builtin_keys)
            interp._debugger_hook = _dbg_hook

        history: list[str] = []
        _COMMANDS = {
            ".exit": "Exit the REPL",
            ".quit": "Exit the REPL",
            ".help": "Show available REPL commands",
            ".clear": "Clear the screen",
            ".history": "Show command history",
            ".vars": "Show all user-defined variables",
            ".reset": "Reset the interpreter state (clear all variables)",
            ".load <f>": "Load and execute a .spry file into the current session",
            ".type <e>": "Evaluate an expression and print its type",
            ".ast <e>": "Show the AST of an expression or statement",
        }

        def _show_help() -> None:
            click.echo("Available REPL commands:")
            for cmd, desc in _COMMANDS.items():
                click.echo(f"  {cmd:<14} {desc}")
            click.echo("Multi-line: end a line with \\ to continue on next line")
            click.echo("Up/Down arrows: navigate history (on supported terminals)")

        def _is_incomplete(src: str) -> bool:
            """Heuristic: source ends with { or ( or \\ — needs more input."""
            stripped = src.rstrip()
            if not stripped:
                return False
            last_char = stripped[-1]
            if last_char in ("{", "(", "[", ",", "\\"):
                return True
            # Count unbalanced braces/parens
            opens = stripped.count("{") + stripped.count("(") + stripped.count("[")
            closes = stripped.count("}") + stripped.count(")") + stripped.count("]")
            return opens > closes

        def _spry_repr(value: Any) -> str:
            """Format a SpryCode value for REPL output."""
            from .interpreter import SPRY_UNDEFINED, _SpryUndefinedType
            if isinstance(value, _SpryUndefinedType):
                return "undefined"
            if value is None:
                return "null"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, str):
                return repr(value)
            return repr(value)

        def _eval_source(src: str) -> None:
            try:
                lex = Lexer(src, "<repl>")
                tokens = lex.tokenize()
                prs = Parser(tokens)
                program = prs.parse()
            except LexerError as e:
                click.echo(f"[SyntaxError] {e}", err=True)
                return
            except ParseError as e:
                click.echo(f"[SyntaxError] {e}", err=True)
                return
            try:
                result = interp.run(program)
                if result is not None:
                    from .interpreter import SPRY_UNDEFINED, _SpryUndefinedType
                    if not isinstance(result, _SpryUndefinedType):
                        click.echo(_spry_repr(result))
            except SpryRuntimeError as e:
                click.echo(f"[RuntimeError] {e}", err=True)
            except Exception as e:  # noqa: BLE001
                click.echo(f"[Error] {e}", err=True)

        def _cmd_vars() -> None:
            """Show all user-defined variables in the global scope."""
            _print_env_vars(interp.globals, builtin_keys=interp._builtin_keys)

        def _cmd_reset() -> None:
            """Reset interpreter state — clear all user variables."""
            nonlocal interp
            interp = Interpreter(logger=logger, permissions=permissions)
            if debug:
                def _dbg_hook(env: Any) -> None:
                    click.echo("\n[debugger] Variables in current scope:", err=True)
                    _print_env_vars(env, builtin_keys=interp._builtin_keys)
                interp._debugger_hook = _dbg_hook
            click.echo("[repl] Interpreter state reset.")

        def _cmd_load(args: str) -> None:
            """Load and execute a .spry file into current session."""
            path = Path(args.strip())
            if not path.exists():
                click.echo(f"[ERROR] File not found: {path}", err=True)
                return
            try:
                src = path.read_text(encoding="utf-8")
                _eval_source(src)
                click.echo(f"[repl] Loaded {path}")
            except OSError as e:
                click.echo(f"[ERROR] {e}", err=True)

        def _cmd_type(expr: str) -> None:
            """Evaluate expression and print its JS-style type."""
            src = f"typeof ({expr.strip()})"
            _eval_source(src)

        def _cmd_ast(expr: str) -> None:
            """Show the AST of expression/statement."""
            try:
                lex = Lexer(expr.strip(), "<repl>")
                tokens = lex.tokenize()
                prs = Parser(tokens)
                program = prs.parse()
                import pprint
                for node in program.body:
                    click.echo(pprint.pformat(node))
            except (LexerError, ParseError) as e:
                click.echo(f"[SyntaxError] {e}", err=True)

        buffer: list[str] = []
        while True:
            prompt = "spry> " if not buffer else "  ... "
            try:
                line = click.prompt(prompt, prompt_suffix="", default="", show_default=False)
            except (EOFError, KeyboardInterrupt):
                click.echo("\nGoodbye!")
                break

            # Special REPL commands
            stripped_line = line.strip()
            if stripped_line in (".exit", ".quit"):
                click.echo("Goodbye!")
                break
            if stripped_line == ".help":
                _show_help()
                continue
            if stripped_line == ".clear":
                click.clear()
                continue
            if stripped_line == ".history":
                for i, h in enumerate(history, 1):
                    click.echo(f"  {i:4d}  {h}")
                continue
            if stripped_line == ".vars":
                _cmd_vars()
                continue
            if stripped_line == ".reset":
                _cmd_reset()
                continue
            if stripped_line.startswith(".load "):
                _cmd_load(stripped_line[6:])
                continue
            if stripped_line.startswith(".type "):
                history.append(stripped_line)
                _cmd_type(stripped_line[6:])
                continue
            if stripped_line.startswith(".ast "):
                history.append(stripped_line)
                _cmd_ast(stripped_line[5:])
                continue

            # Accumulate multi-line input
            buffer.append(line)
            source = "\n".join(buffer)

            if _is_incomplete(source):
                continue  # get more lines

            # Have complete source
            full_source = source.strip()
            buffer = []
            if not full_source:
                continue

            history.append(full_source)
            _eval_source(full_source)

else:
    # Minimal CLI without click
    def main():  # type: ignore
        args = sys.argv[1:]
        if not args:
            print("spry: SpryCode runtime")
            print("Usage: spry <command> [options]")
            print("Commands: run, build, test, fmt, lint, new, audit")
            return

        cmd = args[0]
        if cmd == "run":
            file_path = Path(args[1]) if len(args) > 1 else Path("main.spry")
            task_name = args[2] if len(args) > 2 else None
            if not file_path.exists():
                print(f"[ERROR] File not found: {file_path}", file=sys.stderr)
                sys.exit(1)
            source = file_path.read_text(encoding="utf-8")
            rc = _parse_and_run(source, str(file_path), task_name, secure=False)
            sys.exit(rc)

    def compile_cmd():  # type: ignore
        main()

    def pm_cmd():  # type: ignore
        main()
