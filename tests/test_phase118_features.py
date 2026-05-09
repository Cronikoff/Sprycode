"""Phase 118: Orchestrator step enable/disable control and introspection."""

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


class TestOrchestratorStepEnableDisable:
    def test_disable_step_skips_it_in_run_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 10)
            orch.addStep("b", fn(state) => state + 1)
            orch.disableStep("a")
            let out = orch.runCycle(0, 1)
        """)
        assert val(i, "out") == 1

    def test_enable_step_re_runs_previously_disabled_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 10)
            orch.addStep("b", fn(state) => state + 1)
            orch.disableStep("a")
            orch.enableStep("a")
            let out = orch.runCycle(0, 1)
        """)
        assert val(i, "out") == 11

    def test_disable_step_returns_true_when_found(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            let disableResult = orch.disableStep("svc")
        """)
        assert val(i, "disableResult") is True

    def test_disable_step_returns_false_when_missing(self):
        i = run("""
            let orch = Orchestrator.new()
            let disableResult = orch.disableStep("missing")
        """)
        assert val(i, "disableResult") is False

    def test_enable_step_returns_true_for_disabled_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            orch.disableStep("svc")
            let enableResult = orch.enableStep("svc")
        """)
        assert val(i, "enableResult") is True

    def test_enable_step_returns_true_for_already_enabled_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            let enableResult = orch.enableStep("svc")
        """)
        assert val(i, "enableResult") is True

    def test_enable_step_returns_false_when_missing(self):
        i = run("""
            let orch = Orchestrator.new()
            let enableResult = orch.enableStep("missing")
        """)
        assert val(i, "enableResult") is False

    def test_is_step_enabled_true_by_default(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            let enabled = orch.isStepEnabled("svc")
        """)
        assert val(i, "enabled") is True

    def test_is_step_enabled_false_after_disable(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            orch.disableStep("svc")
            let enabled = orch.isStepEnabled("svc")
        """)
        assert val(i, "enabled") is False

    def test_is_step_enabled_false_for_missing_step(self):
        i = run("""
            let orch = Orchestrator.new()
            let enabled = orch.isStepEnabled("ghost")
        """)
        assert val(i, "enabled") is False

    def test_enabled_step_names_excludes_disabled_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            orch.addStep("c", fn(state) => state)
            orch.disableStep("b")
            let names = orch.enabledStepNames
        """)
        assert val(i, "names") == ["a", "c"]

    def test_enabled_step_count_reflects_disabled_count(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            orch.disableStep("a")
            let count = orch.enabledStepCount
        """)
        assert val(i, "count") == 1

    def test_remove_step_clears_disabled_state(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            orch.disableStep("svc")
            orch.removeStep("svc")
            orch.addStep("svc", fn(state) => state + 7)
            let enabled = orch.isStepEnabled("svc")
            let out = orch.runCycle(0, 1)
        """)
        assert val(i, "enabled") is True
        assert val(i, "out") == 7

    def test_clear_steps_clears_disabled_state(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            orch.disableStep("svc")
            orch.clearSteps()
            orch.addStep("svc", fn(state) => state + 3)
            let enabled = orch.isStepEnabled("svc")
        """)
        assert val(i, "enabled") is True

    def test_get_step_config_unmanaged_enabled(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            let cfg = orch.getStepConfig("svc")
        """)
        cfg = val(i, "cfg")
        assert cfg["name"] == "svc"
        assert cfg["managed"] is False
        assert cfg["maxLoops"] is None
        assert cfg["enabled"] is True

    def test_get_step_config_managed_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep("svc", fn(state) => state, fn(state) => true, 7)
            let cfg = orch.getStepConfig("svc")
        """)
        cfg = val(i, "cfg")
        assert cfg["name"] == "svc"
        assert cfg["managed"] is True
        assert cfg["maxLoops"] == 7
        assert cfg["enabled"] is True

    def test_get_step_config_disabled_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            orch.disableStep("svc")
            let cfg = orch.getStepConfig("svc")
        """)
        cfg = val(i, "cfg")
        assert cfg["enabled"] is False

    def test_get_step_config_missing_returns_undefined(self):
        i = run("""
            let orch = Orchestrator.new()
            let cfg = orch.getStepConfig("ghost")
        """)
        from sprycode.interpreter import SPRY_UNDEFINED
        assert val(i, "cfg") is SPRY_UNDEFINED

    def test_disabled_managed_step_skipped_in_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "managed",
                fn(state) => state + 100,
                fn(state, cycle, name, attempt) => attempt >= 1,
                3
            )
            orch.addStep("plain", fn(state) => state + 1)
            orch.disableStep("managed")
            let out = orch.runCycle(0, 1)
        """)
        assert val(i, "out") == 1

    def test_run_managed_convergence_with_disabled_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("big", fn(state) => state + 100)
            orch.addStep("inc", fn(state) => state + 1)
            orch.disableStep("big")
            let out = orch.runManaged(fn(state) => state >= 3, 0, 10)
        """)
        assert val(i, "out") == 3
