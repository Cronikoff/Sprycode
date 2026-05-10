"""Phase 179: Report-level stateGainAttributionResidualAbsolutePerAttempt metric.

stateGainAttributionResidualAbsolutePerAttempt =
    stateGainAttributionResidualAbsolute / totalAttempts
(when total attempts > 0 and the absolute residual is numeric)
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


class TestPathwayStateGainAttributionResidualAbsolutePerAttempt:
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
        absolute = rep["stateGainAttributionResidualAbsolute"]
        attempts = rep["totalAttempts"]
        if absolute is None or attempts == 0:
            assert rep["stateGainAttributionResidualAbsolutePerAttempt"] is None
        else:
            expected = absolute / attempts
            assert abs(rep["stateGainAttributionResidualAbsolutePerAttempt"] - expected) < 1e-9

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
        absolute = rep["stateGainAttributionResidualAbsolute"]
        attempts = rep["totalAttempts"]
        if absolute is None or attempts == 0:
            assert rep["stateGainAttributionResidualAbsolutePerAttempt"] is None
        else:
            expected = absolute / attempts
            assert abs(rep["stateGainAttributionResidualAbsolutePerAttempt"] - expected) < 1e-9

    def test_zero_cycle_report_has_none(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert rep["totalAttempts"] == 0
        assert rep["stateGainAttributionResidualAbsolutePerAttempt"] is None

    def test_no_managed_steps_matches_formula(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        absolute = rep["stateGainAttributionResidualAbsolute"]
        attempts = rep["totalAttempts"]
        if absolute is None or attempts == 0:
            assert rep["stateGainAttributionResidualAbsolutePerAttempt"] is None
        else:
            expected = absolute / attempts
            assert abs(rep["stateGainAttributionResidualAbsolutePerAttempt"] - expected) < 1e-9

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
        assert rep["stateGainAttributionResidualAbsolute"] is None
        assert rep["stateGainAttributionResidualAbsolutePerAttempt"] is None
