"""Phase 132: Per-target service loop breakdown in pathway managed report."""

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


class TestPathwayReportPerTargetServiceLoops:
    def test_each_target_carries_service_loop_breakdown(self):
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
            let targets = rep["targets"]
        """)
        targets = val(i, "targets")
        assert len(targets) == 1
        t = targets[0]
        assert t["name"] == "svcB"
        assert t["cycles"] == 11
        sloops = t["serviceLoops"]
        assert [s["name"] for s in sloops] == ["svcA", "svcB"]
        assert [s["attempts"] for s in sloops] == [21, 39]
        assert [s["cycles"] for s in sloops] == [11, 11]
        assert [s["peakAttempts"] for s in sloops] == [5, 8]

    def test_single_target_service_loop_breakdown(self):
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
        """)
        targets = val(i, "targets")
        assert len(targets) == 1
        t = targets[0]
        sloops = t["serviceLoops"]
        assert len(sloops) == 1
        assert sloops[0]["name"] == "svc"
        assert sloops[0]["attempts"] == 14
        assert sloops[0]["cycles"] == 4
        assert sloops[0]["peakAttempts"] == 5

    def test_no_managed_steps_produces_no_targets(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(42, 10)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []

    def test_target_service_loops_have_avg_attempts(self):
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
        """)
        targets = val(i, "targets")
        sloops = targets[0]["serviceLoops"]
        avg = sloops[0]["avgAttempts"]
        assert avg is not None
        assert abs(avg - 14 / 4) < 1e-9
