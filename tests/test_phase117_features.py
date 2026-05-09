"""Phase 117: Orchestrator step-level loop micromanagement."""

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


class TestOrchestratorStepReconfiguration:
    def test_set_managed_step_converts_plain_step_to_managed(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state + 1)
            let ok = orch.setManagedStep("svc", fn(state, cycle, name, attempt) => attempt >= 2, 5)
            let out = orch.runCycle(0, 1)
            let attempts = orch.lastCycleAttempts
        """)
        assert val(i, "ok") is True
        assert val(i, "out") == 2
        assert val(i, "attempts")["svc"] == 2

    def test_set_managed_step_updates_existing_managed_config(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 4,
                5
            )
            orch.setManagedStep("svc", fn(state, cycle, name, attempt) => attempt >= 2, 5)
            orch.runCycle(0, 1)
            let attempts = orch.lastCycleAttempts
        """)
        assert val(i, "attempts")["svc"] == 2

    def test_set_managed_step_returns_false_when_missing(self):
        i = run("""
            let orch = Orchestrator.new()
            let ok = orch.setManagedStep("missing", fn(state) => true, 3)
        """)
        assert val(i, "ok") is False

    def test_set_unmanaged_step_reverts_managed_loop_to_single_run(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                5
            )
            let ok = orch.setUnmanagedStep("svc")
            let out = orch.runCycle(0, 1)
            let attempts = orch.lastCycleAttempts
        """)
        assert val(i, "ok") is True
        assert val(i, "out") == 1
        assert val(i, "attempts")["svc"] == 1

    def test_set_unmanaged_step_returns_false_when_missing(self):
        i = run("""
            let orch = Orchestrator.new()
            let ok = orch.setUnmanagedStep("missing")
        """)
        assert val(i, "ok") is False

    def test_set_managed_step_invalid_max_loops_raises(self):
        with pytest.raises(SpryRuntimeError, match="max_loops"):
            run("""
                let orch = Orchestrator.new()
                orch.addStep("svc", fn(state) => state)
                orch.setManagedStep("svc", fn(state) => true, "bad")
            """)

    def test_set_managed_step_can_configure_registry_loaded_service(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("ingest", fn(state) => state + 1)
            let orch = Orchestrator.new()
            orch.loadRegistry(reg)
            let ok = orch.setManagedStep("ingest", fn(state, cycle, name, attempt) => attempt >= 2, 5)
            let out = orch.runCycle(0, 1)
            let attempts = orch.lastCycleAttempts
        """)
        assert val(i, "ok") is True
        assert val(i, "out") == 2
        assert val(i, "attempts")["ingest"] == 2
