"""Phase 136: Per-target aggregate attempt metrics in managed pathway report."""

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


class TestPathwayReportTargetAggregateAttempts:
    def test_single_target_total_attempts(self):
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
        assert t["totalAttempts"] == 14
        assert t["peakCycleAttempts"] == 5
        assert abs(t["avgAttemptsPerCycle"] - 3.5) < 1e-9

    def test_total_attempts_equals_sum_of_service_loop_attempts(self):
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
        service_loop_total = sum(sl["attempts"] for sl in t["serviceLoops"])
        assert t["totalAttempts"] == service_loop_total

    def test_two_service_target_aggregate_attempts(self):
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
        """)
        t = val(i, "t")
        assert t["name"] == "svcB"
        assert t["totalAttempts"] == 60
        assert t["peakCycleAttempts"] == 13
        assert abs(t["avgAttemptsPerCycle"] - 60 / 11) < 1e-9

    def test_avg_attempts_per_cycle_matches_total_over_cycles(self):
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
        """)
        t = val(i, "t")
        expected_avg = t["totalAttempts"] / t["cycles"]
        assert abs(t["avgAttemptsPerCycle"] - expected_avg) < 1e-9

    def test_peak_cycle_attempts_geq_any_service_loop_peak(self):
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
        """)
        t = val(i, "t")
        max_individual_peak = max(sl["peakAttempts"] for sl in t["serviceLoops"])
        assert t["peakCycleAttempts"] >= max_individual_peak

    def test_no_managed_steps_has_no_targets(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []
