"""Phase 113: Managed microservice loop pathways."""

import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals.get(name)


class TestServiceRegistryManagedLoops:
    def test_registry_run_until_solved_loops_service(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("step", fn(state, attempt, name) {
                if state == undefined { return 1 }
                return state + 2
            })
            let out = reg.runUntilSolved("step", fn(state, attempt, name) => state >= 7, undefined, 10)
        """)
        assert val(i, "out") == 7

    def test_registry_run_until_solved_uses_name_and_attempt(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("svc", fn(state, attempt, name) => attempt + len(name))
            let out = reg.runUntilSolved("svc", fn(state, attempt, name) => attempt >= 1, 0, 3)
        """)
        assert val(i, "out") == 4

    def test_registry_run_until_solved_invalid_max_loops_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let reg = ServiceRegistry.new()
                reg.register("svc", fn(state) => state)
                reg.runUntilSolved("svc", fn(state) => true, 0, "bad")
            """)

    def test_registry_run_until_solved_missing_service_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let reg = ServiceRegistry.new()
                reg.runUntilSolved("missing", fn(state) => true, 0, 3)
            """)

    def test_registry_run_until_solved_raises_when_not_solved(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let reg = ServiceRegistry.new()
                reg.register("svc", fn(state) => 1)
                reg.runUntilSolved("svc", fn(state) => false, 0, 2)
            """)


class TestOrchestratorManagedPathways:
    def test_run_managed_aliases_run_until_solved(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 1)
            let out = orch.runManaged(fn(state) => state >= 4, 0, 10)
        """)
        assert val(i, "out") == 4

    def test_run_managed_with_loaded_registry(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("fetch", fn(state) {
                if state == undefined { return 2 }
                return state + 2
            })
            reg.register("shape", fn(state) => state - 1)
            let orch = Orchestrator.new()
            orch.loadRegistry(reg)
            let out = orch.runManaged(fn(state, cycle) => state >= 7, undefined, 10)
        """)
        assert val(i, "out") == 8

    def test_registry_and_orchestrator_nested_loop_management(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("refine", fn(state) {
                if state == undefined { return 1 }
                return state + 1
            })

            let orch = Orchestrator.new()
            orch.addStep("innerLoop", fn(state, cycle) {
                return reg.runUntilSolved("refine", fn(inner) => inner >= 2, state, 5)
            })
            orch.addStep("finalize", fn(state) => state + 1)

            let out = orch.runManaged(fn(state) => state >= 5, undefined, 5)
        """)
        assert val(i, "out") == 5

