"""Phase 130: Orchestrator capability-pathway micromanagement reporting."""

from sprycode.interpreter import Interpreter, SPRY_UNDEFINED
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


class TestOrchestratorCapabilityPathwayManagedReport:
    def test_report_tracks_structural_pathway_targets_until_fully_developed(self):
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
                fn(state, cycle, name, attempt) => attempt >= (9 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 20)
            let out = rep["state"]
            let cycles = rep["cycles"]
            let targets = rep["targets"]
            let fully = rep["fullyDeveloped"]
            let remain = rep["remainingTargets"]
            let total = orch.totalCycles
        """)
        assert val(i, "out") == 73
        assert val(i, "cycles") == 12
        assert val(i, "total") == 12
        assert val(i, "fully") is True
        assert val(i, "remain") == []
        targets = val(i, "targets")
        assert [t["name"] for t in targets] == ["svcB"]
        assert [t["endStage"] for t in targets] == ["mature"]
        assert [t["cycles"] for t in targets] == [11]

    def test_report_handles_single_target_pathway(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let targets = rep["targets"]
            let cycles = rep["cycles"]
            let out = rep["state"]
        """)
        assert [t["name"] for t in val(i, "targets")] == ["svc"]
        assert val(i, "cycles") == 5
        assert val(i, "out") == 19

    def test_report_returns_initial_when_no_managed_services(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(42, 10)
            let out = rep["state"]
            let cycles = rep["cycles"]
            let targets = rep["targets"]
            let fully = rep["fullyDeveloped"]
        """)
        assert val(i, "out") == 42
        assert val(i, "cycles") == 0
        assert val(i, "targets") == []
        assert val(i, "fully") is SPRY_UNDEFINED
