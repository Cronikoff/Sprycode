"""Phase 131: Orchestrator pathway report microservice loop accounting."""

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


class TestOrchestratorPathwayReportServiceLoops:
    def test_report_tracks_service_loops_for_all_active_managed_services(self):
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
            let loops = rep["serviceLoops"]
        """)
        loops = val(i, "loops")
        assert [item["name"] for item in loops] == ["svcA", "svcB"]
        assert [item["attempts"] for item in loops] == [26, 47]
        assert [item["cycles"] for item in loops] == [12, 12]
        assert [item["peakAttempts"] for item in loops] == [5, 8]
        assert [item["mature"] for item in loops] == [True, True]

    def test_report_service_loops_excludes_disabled_managed_services(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "enabledSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            orch.addManagedStep(
                "disabledSvc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (8 - cycle),
                10
            )
            orch.disableStep("disabledSvc")
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let loops = rep["serviceLoops"]
        """)
        loops = val(i, "loops")
        assert [item["name"] for item in loops] == ["enabledSvc"]
        assert loops[0]["attempts"] == 19
        assert loops[0]["cycles"] == 5
        assert loops[0]["peakAttempts"] == 5
        assert loops[0]["mature"] is True

    def test_report_service_loops_empty_without_managed_services(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(42, 10)
            let loops = rep["serviceLoops"]
        """)
        assert val(i, "loops") == []
