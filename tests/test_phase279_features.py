"""Phase 279: Os module — operating-system interface.

Covers path helpers, file I/O, directory operations, environment variables,
process information, and temp-file utilities exposed via the Os global.
"""

import os
import tempfile
import platform

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals._vars.get(name)


class TestOsConstants:
    def test_sep_is_string(self):
        i = run("let s = Os.sep")
        assert isinstance(val(i, "s"), str)
        assert val(i, "s") == os.sep

    def test_pathsep_is_string(self):
        i = run("let s = Os.pathsep")
        assert val(i, "s") == os.pathsep

    def test_platform_is_lowercase_string(self):
        i = run("let p = Os.platform")
        assert isinstance(val(i, "p"), str)
        assert val(i, "p") == platform.system().lower()

    def test_arch_is_string(self):
        i = run("let a = Os.arch")
        assert isinstance(val(i, "a"), str)

    def test_hostname_is_string(self):
        i = run("let h = Os.hostname")
        assert isinstance(val(i, "h"), str)
        assert len(val(i, "h")) > 0

    def test_pid_is_positive_int(self):
        i = run("let p = Os.pid")
        assert isinstance(val(i, "p"), int)
        assert val(i, "p") > 0

    def test_environ_is_dict(self):
        i = run("let e = Os.environ")
        assert isinstance(val(i, "e"), dict)


class TestOsWorkingDirectory:
    def test_cwd_returns_string(self):
        i = run("let c = Os.cwd()")
        assert isinstance(val(i, "c"), str)
        assert val(i, "c") == os.getcwd()

    def test_getcwd_alias(self):
        i = run("let c = Os.getcwd()")
        assert val(i, "c") == os.getcwd()

    def test_chdir_and_cwd(self):
        original = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpd:
                i = run(f"""
                    Os.chdir("{tmpd}")
                    let c = Os.cwd()
                """)
                result = val(i, "c")
                assert os.path.realpath(result) == os.path.realpath(tmpd)
        finally:
            os.chdir(original)


class TestOsEnvironment:
    def test_getenv_existing(self):
        os.environ["SPRY_TEST_VAR"] = "hello_spry"
        i = run('let v = Os.getenv("SPRY_TEST_VAR")')
        assert val(i, "v") == "hello_spry"

    def test_getenv_missing_returns_none(self):
        os.environ.pop("SPRY_NONEXISTENT_SPRY", None)
        i = run('let v = Os.getenv("SPRY_NONEXISTENT_SPRY")')
        assert val(i, "v") is None

    def test_getenv_default(self):
        os.environ.pop("SPRY_NONEXISTENT_SPRY2", None)
        i = run('let v = Os.getenv("SPRY_NONEXISTENT_SPRY2", "fallback")')
        assert val(i, "v") == "fallback"

    def test_setenv_then_getenv(self):
        os.environ.pop("SPRY_SET_TEST", None)
        i = run("""
            Os.setenv("SPRY_SET_TEST", "world")
            let v = Os.getenv("SPRY_SET_TEST")
        """)
        assert val(i, "v") == "world"

    def test_unsetenv_removes_key(self):
        os.environ["SPRY_UNSET_TEST"] = "temp"
        i = run("""
            Os.unsetenv("SPRY_UNSET_TEST")
            let v = Os.getenv("SPRY_UNSET_TEST")
        """)
        assert val(i, "v") is None


class TestOsPathHelpers:
    def test_join_two_parts(self):
        i = run('let p = Os.join("/tmp", "foo")')
        assert val(i, "p") == os.path.join("/tmp", "foo")

    def test_join_three_parts(self):
        i = run('let p = Os.join("/tmp", "foo", "bar.txt")')
        assert val(i, "p") == "/tmp/foo/bar.txt"

    def test_basename(self):
        i = run('let b = Os.basename("/tmp/foo/bar.txt")')
        assert val(i, "b") == "bar.txt"

    def test_dirname(self):
        i = run('let d = Os.dirname("/tmp/foo/bar.txt")')
        assert val(i, "d") == "/tmp/foo"

    def test_extname_with_dot(self):
        i = run('let e = Os.extname("report.pdf")')
        assert val(i, "e") == ".pdf"

    def test_extname_no_extension(self):
        i = run('let e = Os.extname("Makefile")')
        assert val(i, "e") == ""

    def test_stem(self):
        i = run('let s = Os.stem("report.pdf")')
        assert val(i, "s") == "report"

    def test_abspath_returns_absolute(self):
        i = run('let a = Os.abspath(".")')
        assert os.path.isabs(val(i, "a"))

    def test_normalize(self):
        i = run('let n = Os.normalize("/tmp//foo/../bar")')
        assert val(i, "n") == os.path.normpath("/tmp//foo/../bar")

    def test_split_returns_list(self):
        i = run('let s = Os.split("/tmp/foo/bar.txt")')
        v = val(i, "s")
        assert isinstance(v, list)
        assert v == ["/tmp/foo", "bar.txt"]

    def test_splitext_returns_list(self):
        i = run('let s = Os.splitext("report.pdf")')
        v = val(i, "s")
        assert v == ["report", ".pdf"]

    def test_isAbsolute_true(self):
        i = run('let r = Os.isAbsolute("/tmp/foo")')
        assert val(i, "r") is True

    def test_isAbsolute_false(self):
        i = run('let r = Os.isAbsolute("relative/path")')
        assert val(i, "r") is False


class TestOsExistenceChecks:
    def test_exists_tmp(self):
        i = run('let r = Os.exists("/tmp")')
        assert val(i, "r") is True

    def test_exists_nonexistent(self):
        i = run('let r = Os.exists("/tmp/spry_nonexistent_xyzzy")')
        assert val(i, "r") is False

    def test_isDir_tmp(self):
        i = run('let r = Os.isDir("/tmp")')
        assert val(i, "r") is True

    def test_isFile_tmp(self):
        i = run('let r = Os.isFile("/tmp")')
        assert val(i, "r") is False

    def test_isFile_on_actual_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            i = run(f'let r = Os.isFile("{path}")')
            assert val(i, "r") is True
        finally:
            os.unlink(path)

    def test_stat_returns_dict(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            i = run(f'let s = Os.stat("{path}")')
            s = val(i, "s")
            assert isinstance(s, dict)
            assert "size" in s
            assert "mtime" in s
            assert isinstance(s["isFile"], bool)
        finally:
            os.unlink(path)

    def test_size_returns_int(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write("hello")
            path = f.name
        try:
            i = run(f'let sz = Os.size("{path}")')
            assert val(i, "sz") == 5
        finally:
            os.unlink(path)


class TestOsDirectoryOperations:
    def test_listdir_returns_list(self):
        i = run('let d = Os.listdir("/tmp")')
        v = val(i, "d")
        assert isinstance(v, list)

    def test_readdir_alias(self):
        i = run('let d = Os.readdir("/tmp")')
        assert isinstance(val(i, "d"), list)

    def test_mkdir_and_rmdir(self):
        with tempfile.TemporaryDirectory() as base:
            new_dir = os.path.join(base, "newdir")
            i = run(f"""
                Os.mkdir("{new_dir}")
                let ex = Os.exists("{new_dir}")
                Os.rmdir("{new_dir}")
                let gone = Os.exists("{new_dir}")
            """)
            assert val(i, "ex") is True
            assert val(i, "gone") is False

    def test_mkdirs_recursive(self):
        with tempfile.TemporaryDirectory() as base:
            deep = os.path.join(base, "a", "b", "c")
            i = run(f"""
                Os.mkdirs("{deep}")
                let ex = Os.isDir("{deep}")
            """)
            assert val(i, "ex") is True

    def test_rmdirs_removes_tree(self):
        with tempfile.TemporaryDirectory() as base:
            tree = os.path.join(base, "tree")
            os.makedirs(os.path.join(tree, "sub"))
            i = run(f"""
                Os.rmdirs("{tree}")
                let gone = Os.exists("{tree}")
            """)
            assert val(i, "gone") is False

    def test_walk_returns_list(self):
        with tempfile.TemporaryDirectory() as base:
            os.mkdir(os.path.join(base, "sub"))
            i = run(f'let w = Os.walk("{base}")')
            w = val(i, "w")
            assert isinstance(w, list)
            assert len(w) >= 1
            assert "root" in w[0]
            assert "dirs" in w[0]
            assert "files" in w[0]


class TestOsFileOperations:
    def test_write_and_read_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            i = run(f"""
                Os.writeFile("{path}", "hello world")
                let c = Os.readFile("{path}")
            """)
            assert val(i, "c") == "hello world"
        finally:
            os.unlink(path)

    def test_append_file(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as f:
            f.write("hello")
            path = f.name
        try:
            i = run(f"""
                Os.appendFile("{path}", " world")
                let c = Os.readFile("{path}")
            """)
            assert val(i, "c") == "hello world"
        finally:
            os.unlink(path)

    def test_copy_file(self):
        with tempfile.TemporaryDirectory() as base:
            src = os.path.join(base, "src.txt")
            dst = os.path.join(base, "dst.txt")
            with open(src, "w") as f:
                f.write("copy_me")
            i = run(f"""
                Os.copyFile("{src}", "{dst}")
                let c = Os.readFile("{dst}")
            """)
            assert val(i, "c") == "copy_me"

    def test_rename_file(self):
        with tempfile.TemporaryDirectory() as base:
            src = os.path.join(base, "orig.txt")
            dst = os.path.join(base, "renamed.txt")
            with open(src, "w") as f:
                f.write("data")
            i = run(f"""
                Os.rename("{src}", "{dst}")
                let ex = Os.isFile("{dst}")
                let gone = Os.exists("{src}")
            """)
            assert val(i, "ex") is True
            assert val(i, "gone") is False

    def test_remove_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        i = run(f"""
            Os.remove("{path}")
            let gone = Os.exists("{path}")
        """)
        assert val(i, "gone") is False

    def test_unlink_alias(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        i = run(f"""
            Os.unlink("{path}")
            let gone = Os.exists("{path}")
        """)
        assert val(i, "gone") is False


class TestOsTempHelpers:
    def test_tmpdir_returns_string(self):
        import tempfile as _tf
        i = run("let t = Os.tmpdir()")
        assert val(i, "t") == _tf.gettempdir()

    def test_mktempdir_creates_dir(self):
        i = run('let d = Os.mktempdir()')
        d = val(i, "d")
        assert isinstance(d, str)
        assert os.path.isdir(d)
        os.rmdir(d)

    def test_mktempfile_creates_file(self):
        i = run('let f = Os.mktempfile()')
        f = val(i, "f")
        assert isinstance(f, str)
        assert os.path.isfile(f)
        os.unlink(f)

    def test_homedir_returns_string(self):
        i = run("let h = Os.homedir()")
        assert val(i, "h") == os.path.expanduser("~")

    def test_expanduser_tilde(self):
        i = run('let e = Os.expanduser("~")')
        assert val(i, "e") == os.path.expanduser("~")


class TestOsProcessExec:
    def test_exec_echo_ok(self):
        i = run('let r = Os.exec("echo hello")')
        r = val(i, "r")
        assert isinstance(r, dict)
        assert r["ok"] is True
        assert r["code"] == 0
        assert "hello" in r["stdout"]

    def test_exec_returns_stderr(self):
        i = run('let r = Os.exec("echo err 1>&2")')
        r = val(i, "r")
        assert isinstance(r, dict)
        assert "ok" in r

    def test_exec_bad_command_ok_false(self):
        i = run('let r = Os.exec("false")')
        r = val(i, "r")
        assert r["ok"] is False

    def test_cpuCount_positive(self):
        i = run("let n = Os.cpuCount()")
        assert isinstance(val(i, "n"), int)
        assert val(i, "n") >= 1
