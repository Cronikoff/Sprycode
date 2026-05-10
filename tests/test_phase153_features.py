"""Phase 153: Report-level absolute attribution coverage residual metric.

stateGainAttributionCoverageAbsoluteResidual =
    abs(stateGainAttributionCoverageResidual) (when residual is defined)
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


class TestPathwayReportStateGainAttributionCoverageAbsoluteResidual:
    def test_single_target_has_zero_absolute_coverage_residual(self):
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
        assert abs(rep["stateGainAttributionCoverageAbsoluteResidual"]) < 1e-9

    def test_two_target_has_zero_absolute_coverage_residual(self):
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
        assert abs(rep["stateGainAttributionCoverageAbsoluteResidual"]) < 1e-9

    def test_absolute_coverage_residual_matches_formula(self):
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
        expected = abs(rep["stateGainAttributionCoverageResidual"])
        assert abs(rep["stateGainAttributionCoverageAbsoluteResidual"] - expected) < 1e-9

    def test_no_managed_steps_has_none_absolute_coverage_residual(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        assert rep["stateGainAttributionCoverageAbsoluteResidual"] is None

    def test_zero_report_gain_with_managed_target_has_none_absolute_coverage_residual(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
        """)
        rep = val(i, "rep")
        assert rep["reportStateGain"] == 0
        assert rep["stateGainAttributionCoverageAbsoluteResidual"] is None

    def test_non_numeric_report_gain_has_none_absolute_coverage_residual(self):
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
        assert rep["stateGainAttributionCoverageAbsoluteResidual"] is None
