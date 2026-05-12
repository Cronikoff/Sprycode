"""Phase 269: Report-level stateGainAttributionResidual metric."""

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


class TestPhase269:
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

        rg = rep["reportStateGain"]
        tg = rep["targetStateGainSum"]
        pg = rep["preTargetStateGain"]
        if rg is None or tg is None or pg is None:
            assert rep["stateGainAttributionResidual"] is None
        else:
            expected = rg - (tg + pg)
            assert abs(rep["stateGainAttributionResidual"] - expected) < 1e-9

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

        rg = rep["reportStateGain"]
        tg = rep["targetStateGainSum"]
        pg = rep["preTargetStateGain"]
        if rg is None or tg is None or pg is None:
            assert rep["stateGainAttributionResidual"] is None
        else:
            expected = rg - (tg + pg)
            assert abs(rep["stateGainAttributionResidual"] - expected) < 1e-9

    def test_zero_cycle_report_behavior(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")

        rg = rep["reportStateGain"]
        tg = rep["targetStateGainSum"]
        pg = rep["preTargetStateGain"]
        if rg is None or tg is None or pg is None:
            assert rep["stateGainAttributionResidual"] is None
        else:
            expected = rg - (tg + pg)
            assert abs(rep["stateGainAttributionResidual"] - expected) < 1e-9

