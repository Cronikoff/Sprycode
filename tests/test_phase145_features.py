"""Phase 145: Report-level per-attribution state-gain per-cycle metrics.

targetStateGainPerCycle  = targetStateGainSum  / report_cycles (when report_cycles > 0)
preTargetStateGainPerCycle = preTargetStateGain / report_cycles (when report_cycles > 0)
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


class TestPathwayReportGainPerCycleAttribution:
    def test_single_target_gain_per_cycle_values(self):
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
        cycles = rep["cycles"]
        assert cycles > 0
        assert abs(rep["targetStateGainPerCycle"] - rep["targetStateGainSum"] / cycles) < 1e-9
        assert abs(rep["preTargetStateGainPerCycle"] - rep["preTargetStateGain"] / cycles) < 1e-9

    def test_two_target_gain_per_cycle_values(self):
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
        cycles = rep["cycles"]
        assert abs(rep["targetStateGainPerCycle"] - 60 / cycles) < 1e-9
        assert abs(rep["preTargetStateGainPerCycle"] - 13 / cycles) < 1e-9

    def test_attribution_per_cycle_sums_to_report_per_cycle(self):
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
        total = rep["targetStateGainPerCycle"] + rep["preTargetStateGainPerCycle"]
        assert abs(total - rep["reportStateGainPerCycle"]) < 1e-9

    def test_formula_consistency_for_target_gain_per_cycle(self):
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
        expected = rep["targetStateGainSum"] / rep["cycles"]
        assert abs(rep["targetStateGainPerCycle"] - expected) < 1e-9

    def test_formula_consistency_for_pre_target_gain_per_cycle(self):
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
        expected = rep["preTargetStateGain"] / rep["cycles"]
        assert abs(rep["preTargetStateGainPerCycle"] - expected) < 1e-9

    def test_no_managed_steps_has_none_per_cycle_attributions(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        assert rep["targetStateGainPerCycle"] is None
        assert rep["preTargetStateGainPerCycle"] is None

    def test_zero_report_gain_has_zero_per_cycle_attributions(self):
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
        assert rep["targetStateGainPerCycle"] == 0.0
        assert rep["preTargetStateGainPerCycle"] == 0.0
