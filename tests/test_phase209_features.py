"""Phase 209: Report-level stateGainAttributionResidualCoverageAbsoluteCoverage metric.

stateGainAttributionResidualCoverageAbsoluteCoverage =
    stateGainAttributionResidualCoverageAbsolute / reportStateGain
(when reportStateGain != 0 and absolute metric is numeric)
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


class TestPathwayStateGainAttributionResidualCoverageAbsoluteCoverage:
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
        absolute = rep["stateGainAttributionResidualCoverageAbsolute"]
        report_state_gain = rep["reportStateGain"]
        if absolute is None or report_state_gain == 0:
            assert rep["stateGainAttributionResidualCoverageAbsoluteCoverage"] is None
        else:
            expected = absolute / report_state_gain
            assert abs(rep["stateGainAttributionResidualCoverageAbsoluteCoverage"] - expected) < 1e-9

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
        absolute = rep["stateGainAttributionResidualCoverageAbsolute"]
        report_state_gain = rep["reportStateGain"]
        if absolute is None or report_state_gain == 0:
            assert rep["stateGainAttributionResidualCoverageAbsoluteCoverage"] is None
        else:
            expected = absolute / report_state_gain
            assert abs(rep["stateGainAttributionResidualCoverageAbsoluteCoverage"] - expected) < 1e-9

    def test_zero_cycle_report_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert rep["reportStateGain"] == 0
        assert rep["stateGainAttributionResidualCoverageAbsoluteCoverage"] is None
