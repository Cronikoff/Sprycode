"""Phase 232: Report-level stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget metric."""

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


class TestPathwayStateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget:
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
        coverage = rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverage"]
        targets = rep["targets"]
        count = len(targets)
        if coverage is None or count == 0:
            assert rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget"] is None
        else:
            expected = coverage / count
            assert abs(rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget"] - expected) < 1e-9

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
        coverage = rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoverage"]
        targets = rep["targets"]
        count = len(targets)
        if coverage is None or count == 0:
            assert rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget"] is None
        else:
            expected = coverage / count
            assert abs(rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget"] - expected) < 1e-9

    def test_zero_target_report_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert len(rep["targets"]) == 0
        assert rep["stateGainAttributionCoverageAbsoluteResidualCoverageAbsoluteCoveragePerTarget"] is None
