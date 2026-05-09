"""Phase 135: Per-target cycle window checkpoints in managed pathway report."""

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
    return i.globals.get(name)


class TestPathwayReportTargetCycleWindows:
    def test_single_target_cycle_window(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let t = rep["targets"][0]
        """)
        t = val(i, "t")
        assert t["cycleStart"] == 2
        assert t["cycleEnd"] == 5
        assert t["cycles"] == 4
        assert t["cycleEnd"] - t["cycleStart"] + 1 == t["cycles"]

    def test_two_service_pathway_cycle_window(self):
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
            let t = rep["targets"][0]
            let total = rep["cycles"]
        """)
        t = val(i, "t")
        assert t["name"] == "svcB"
        assert t["cycleStart"] == 2
        assert t["cycleEnd"] == 12
        assert t["cycles"] == 11
        assert t["cycleEnd"] - t["cycleStart"] + 1 == t["cycles"]
        assert val(i, "total") == 12

    def test_cycle_window_is_monotonic(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (5 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 8)
            let t = rep["targets"][0]
            let start = t["cycleStart"]
            let end = t["cycleEnd"]
        """)
        assert val(i, "start") <= val(i, "end")

    def test_no_managed_steps_has_no_target_windows(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []
