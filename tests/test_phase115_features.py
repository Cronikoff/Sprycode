"""Phase 115: Managed registry loading for orchestrator pathways."""

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


class TestOrchestratorManagedRegistryLoading:
    def test_load_registry_managed_returns_loaded_count(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("a", fn(state) => state + 1)
            reg.register("b", fn(state) => state + 1)
            let orch = Orchestrator.new()
            let loaded = orch.loadRegistryManaged(reg, fn(state, cycle, name, attempt) => true, 2)
            let count = orch.stepCount
        """)
        assert val(i, "loaded") == 2
        assert val(i, "count") == 2

    def test_load_registry_managed_loops_each_service_until_solved(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("inc1", fn(state) => state + 1)
            reg.register("inc2", fn(state) => state + 2)

            let orch = Orchestrator.new()
            orch.loadRegistryManaged(reg, fn(state, cycle, name, attempt) => attempt >= 2, 3)
            let out = orch.runCycle(0, 1)
        """)
        assert val(i, "out") == 6

    def test_load_registry_managed_with_run_managed_pathway(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("x", fn(state) => state + 1)
            reg.register("y", fn(state) => state + 2)

            let orch = Orchestrator.new()
            orch.loadRegistryManaged(reg, fn(state, cycle, name, attempt) => attempt >= 2, 3)
            let out = orch.runManaged(fn(state, cycle) => state >= 12, 0, 3)
        """)
        assert val(i, "out") == 12

    def test_load_registry_managed_invalid_registry_raises(self):
        with pytest.raises(SpryRuntimeError, match="loadRegistryManaged expects ServiceRegistry"):
            run("""
                let orch = Orchestrator.new()
                orch.loadRegistryManaged({}, fn(state) => true, 3)
            """)

    def test_load_registry_managed_invalid_max_loops_raises(self):
        with pytest.raises(SpryRuntimeError, match="max_loops"):
            run("""
                let reg = ServiceRegistry.new()
                reg.register("x", fn(state) => state)
                let orch = Orchestrator.new()
                orch.loadRegistryManaged(reg, fn(state) => true, "bad")
            """)

