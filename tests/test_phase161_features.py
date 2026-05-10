"""Phase 161: Report-level state-gain-attribution-residual-per-target metric.

stateGainAttributionResidualPerTarget = stateGainAttributionResidual / len(targets)
(when target count > 0 and report state gain is numeric)
"""

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


class TestPathwayReportStateGainAttributionResidualPerTarget:
    def test_single_target_matches_formula(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
        """)
        rep = val(i, "rep")
        expected = rep["stateGainAttributionResidual"] / len(rep["targets"])
        assert abs(rep["stateGainAttributionResidualPerTarget"] - expected) < 1e-9

    def test_two_targets_matches_formula(self):
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
        """)
        rep = val(i, "rep")
        expected = rep["stateGainAttributionResidual"] / len(rep["targets"])
        assert abs(rep["stateGainAttributionResidualPerTarget"] - expected) < 1e-9

    def test_no_managed_steps_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        assert rep["targets"] == []
        assert rep["stateGainAttributionResidualPerTarget"] is None

    def test_zero_cycle_report_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert rep["cycles"] == 0
        assert rep["targets"] == []
        assert rep["stateGainAttributionResidualPerTarget"] is None

    def test_non_numeric_state_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => "steady",
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport("start", 10)
        """)
        rep = val(i, "rep")
        assert rep["reportStateGain"] is None
        assert rep["stateGainAttributionResidualPerTarget"] is None
