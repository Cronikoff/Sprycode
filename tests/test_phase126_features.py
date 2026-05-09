"""Phase 126: Orchestrator capability maturity analytics for managed loop pathways."""

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


class TestOrchestratorCapabilityMaturityAnalytics:
    def test_capability_properties_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let stages = orch.stepCapabilityStages
            let maturity = orch.pathwayCapabilityMaturity
        """)
        assert val(i, "stages") == {}
        assert val(i, "maturity") == {
            "managedSteps": 0,
            "critical": 0,
            "stretched": 0,
            "stabilizing": 0,
            "mature": 0,
            "avgUtilization": None,
            "maturity": None,
        }

    def test_capability_stages_and_maturity_distribution(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "criticalSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 9,
                10
            ) // util = 0.9 => critical
            orch.addManagedStep(
                "stretchSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 7,
                10
            ) // util = 0.7 => stretched
            orch.addManagedStep(
                "stabilizeSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 4,
                10
            ) // util = 0.4 => stabilizing
            orch.addManagedStep(
                "matureSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                10
            ) // util = 0.2 => mature
            orch.runCycle(0, 1)
            let stages = orch.stepCapabilityStages
            let maturity = orch.pathwayCapabilityMaturity
        """)
        assert val(i, "stages") == {
            "criticalSvc": "critical",
            "stretchSvc": "stretched",
            "stabilizeSvc": "stabilizing",
            "matureSvc": "mature",
        }
        maturity = val(i, "maturity")
        assert maturity["managedSteps"] == 4
        assert maturity["critical"] == 1
        assert maturity["stretched"] == 1
        assert maturity["stabilizing"] == 1
        assert maturity["mature"] == 1
        assert maturity["avgUtilization"] == 0.55
        assert maturity["maturity"] == 0.44999999999999996

    def test_capability_fields_in_summary_and_get_step_summary(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 5,
                10
            ) // util = 0.5 => stabilizing, progress = 0.5
            orch.runCycle(0, 1)
            let one = orch.getStepSummary("svc")
            let full = orch.summary
        """)
        one = val(i, "one")
        assert one["loopCapabilityStage"] == "stabilizing"
        assert one["capabilityProgress"] == 0.5

        full = val(i, "full")
        by_name = {item["name"]: item for item in full}
        assert by_name["plain"]["loopCapabilityStage"] is None
        assert by_name["plain"]["capabilityProgress"] is None
        assert by_name["svc"]["loopCapabilityStage"] == "stabilizing"
        assert by_name["svc"]["capabilityProgress"] == 0.5

    def test_capability_properties_reset_with_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 6,
                10
            )
            orch.runCycle(0, 1)
            orch.resetHistory()
            let stages = orch.stepCapabilityStages
            let maturity = orch.pathwayCapabilityMaturity
            let s = orch.getStepSummary("svc")
        """)
        assert val(i, "stages") == {}
        assert val(i, "maturity")["managedSteps"] == 0
        assert val(i, "maturity")["maturity"] is None
        assert val(i, "s")["loopCapabilityStage"] is None
        assert val(i, "s")["capabilityProgress"] is None
