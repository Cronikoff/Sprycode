"""Phase 237: Report-level stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage metric.

stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage =
    stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsolute / stateGainAttributionCoverageSum
(when both operands are numeric and denominator is non-zero)
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


class TestPathwayStateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage:
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
        absolute = rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsolute"]
        total = rep["stateGainAttributionCoverageSum"]
        if absolute is None or total in (None, 0):
            assert rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage"] is None
        else:
            expected = absolute / total
            assert abs(rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage"] - expected) < 1e-9

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
        absolute = rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsolute"]
        total = rep["stateGainAttributionCoverageSum"]
        if absolute is None or total in (None, 0):
            assert rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage"] is None
        else:
            expected = absolute / total
            assert abs(rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage"] - expected) < 1e-9

    def test_zero_cycle_report_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert rep["cycles"] == 0
        assert rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverageAbsoluteCoverage"] is None
