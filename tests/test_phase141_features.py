"""Phase 141: Report-level spry distribution ratios in managed pathway report."""

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


class TestPathwayReportSpryDistributionRatios:
    def test_single_target_ratios_match_distribution(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let ratios = rep["spryDistributionRatios"]
        """)
        ratios = val(i, "ratios")
        assert abs(ratios["brisk"] - 1.0) < 1e-9
        assert ratios["lively"] == 0.0
        assert ratios["active"] == 0.0
        assert ratios["vigorous"] == 0.0

    def test_two_service_pathway_has_vigorous_ratio_one(self):
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
            let ratios = rep["spryDistributionRatios"]
        """)
        ratios = val(i, "ratios")
        assert ratios["lively"] == 0.0
        assert ratios["active"] == 0.0
        assert ratios["brisk"] == 0.0
        assert abs(ratios["vigorous"] - 1.0) < 1e-9

    def test_ratios_sum_to_one_when_targets_present(self):
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
            let ratios = rep["spryDistributionRatios"]
        """)
        ratios = val(i, "ratios")
        total = (
            ratios["lively"]
            + ratios["active"]
            + ratios["brisk"]
            + ratios["vigorous"]
        )
        assert abs(total - 1.0) < 1e-9

    def test_no_managed_steps_has_zero_ratios(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let ratios = rep["spryDistributionRatios"]
        """)
        ratios = val(i, "ratios")
        assert ratios["lively"] == 0.0
        assert ratios["active"] == 0.0
        assert ratios["brisk"] == 0.0
        assert ratios["vigorous"] == 0.0
