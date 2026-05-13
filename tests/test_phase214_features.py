"""Phase 214: Report-level stateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle metric."""

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


class TestPathwayStateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle:
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
        absolute = rep["stateGainAttributionResidualAbsoluteCoverageAbsolute"]
        cycles = rep["cycles"]
        if absolute is None or cycles == 0:
            assert rep["stateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle"] is None
        else:
            expected = absolute / cycles
            assert abs(rep["stateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle"] - expected) < 1e-9

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
        absolute = rep["stateGainAttributionResidualAbsoluteCoverageAbsolute"]
        cycles = rep["cycles"]
        if absolute is None or cycles == 0:
            assert rep["stateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle"] is None
        else:
            expected = absolute / cycles
            assert abs(rep["stateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle"] - expected) < 1e-9

    def test_zero_cycle_report_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert rep["cycles"] == 0
        assert rep["stateGainAttributionResidualAbsoluteCoverageAbsolutePerCycle"] is None
