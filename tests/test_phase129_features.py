"""Phase 129: Orchestrator target-level capability pathway micromanagement loops."""

import pytest
from sprycode.interpreter import Interpreter, SPRY_UNDEFINED, SpryRuntimeError
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


class TestOrchestratorTargetCapabilityMicromanagement:
    def test_run_target_until_mature_converges(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let out = orch.runTargetUntilMature("svc", 0, 10)
            let total = orch.totalCycles
            let fully = orch.capabilityFullyDeveloped
        """)
        assert val(i, "out") == 14
        assert val(i, "total") == 4
        assert val(i, "fully") is True

    def test_run_target_until_mature_rejects_unmanaged_target(self):
        with pytest.raises(SpryRuntimeError, match="is not managed"):
            run("""
                let orch = Orchestrator.new()
                orch.addStep("plain", fn(state) => state + 1)
                orch.runTargetUntilMature("plain", 0, 2)
            """)

    def test_run_next_capability_target_bootstraps_from_empty_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "criticalSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            orch.addManagedStep(
                "matureSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 1,
                10
            )
            let out = orch.runNextCapabilityTarget(0, 10)
            let next = orch.nextCapabilityTarget
            let remain = orch.capabilityRemainingTargets
            let total = orch.totalCycles
        """)
        assert val(i, "out") == 24
        assert val(i, "next") is SPRY_UNDEFINED
        assert val(i, "remain") == []
        assert val(i, "total") == 5

    def test_run_capability_pathway_managed_drives_fully_developed(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svcA",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            orch.addManagedStep(
                "svcB",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (5 - cycle),
                10
            )
            let out = orch.runCapabilityPathwayManaged(0, 10)
            let done = orch.capabilityFullyDeveloped
            let remain = orch.capabilityRemainingTargets
            let total = orch.totalCycles
        """)
        assert val(i, "out") == 33
        assert val(i, "done") is True
        assert val(i, "remain") == []
        assert val(i, "total") == 5

    def test_run_capability_pathway_managed_returns_initial_when_no_managed_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let out = orch.runCapabilityPathwayManaged(42, 3)
            let done = orch.capabilityFullyDeveloped
        """)
        assert val(i, "out") == 42
        assert val(i, "done") is SPRY_UNDEFINED
