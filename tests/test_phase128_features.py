"""Phase 128: Orchestrator capability-pathway loop execution until fully developed."""

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


class TestOrchestratorCapabilityDevelopmentExecution:
    def test_run_capability_until_developed_converges(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let out = orch.runCapabilityUntilDeveloped(0, 10)
            let total = orch.totalCycles
            let fully = orch.capabilityFullyDeveloped
            let next = orch.nextCapabilityTarget
            let remain = orch.capabilityRemainingTargets
        """)
        assert val(i, "out") == 14
        assert val(i, "total") == 4
        assert val(i, "fully") is True
        assert val(i, "next") is SPRY_UNDEFINED
        assert val(i, "remain") == []

    def test_run_capability_until_developed_raises_when_not_converged(self):
        with pytest.raises(
            SpryRuntimeError,
            match="without fully developing capability pathway",
        ):
            run("""
                let orch = Orchestrator.new()
                orch.addManagedStep(
                    "svc",
                    fn(state, cycle, name, attempt) => state + 1,
                    fn(state, cycle, name, attempt) => attempt >= 8,
                    10
                )
                orch.runCapabilityUntilDeveloped(0, 2)
            """)

    def test_capability_remaining_targets_ordered_by_pathway(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "criticalSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 9,
                10
            )
            orch.addManagedStep(
                "matureSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                10
            )
            orch.runCycle(0, 1)
            let path = orch.capabilityPathway
            let remain = orch.capabilityRemainingTargets
        """)
        assert val(i, "path") == ["criticalSvc", "matureSvc"]
        assert val(i, "remain") == ["criticalSvc"]

    def test_capability_remaining_targets_reset_with_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 6,
                10
            )
            orch.runCycle(0, 1)
            orch.resetHistory()
            let remain = orch.capabilityRemainingTargets
        """)
        assert val(i, "remain") == []
