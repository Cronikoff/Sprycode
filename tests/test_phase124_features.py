"""Phase 124: Orchestrator loop-pressure utilization and headroom analytics."""

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


class TestOrchestratorLoopPressureAnalytics:
    def test_utilization_and_headroom_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let util = orch.stepLoopUtilization
            let room = orch.stepLoopHeadroom
        """)
        assert val(i, "util") == {}
        assert val(i, "room") == {}

    def test_utilization_and_headroom_single_managed_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "m",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                6
            )
            orch.runCycle(0, 1)
            let util = orch.stepLoopUtilization
            let room = orch.stepLoopHeadroom
        """)
        assert val(i, "util") == {"m": 0.5}
        assert val(i, "room") == {"m": 3.0}

    def test_utilization_and_headroom_multiple_cycles(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "x",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= cycle,
                4
            )
            orch.runCycle(0, 1)
            orch.runCycle(0, 2)
            orch.runCycle(0, 3)
            let util = orch.stepLoopUtilization
            let room = orch.stepLoopHeadroom
        """)
        # avg attempts = (1+2+3)/3 = 2.0
        assert val(i, "util") == {"x": 0.5}
        assert val(i, "room") == {"x": 2.0}

    def test_utilization_and_headroom_skip_unmanaged_and_disabled(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addManagedStep(
                "b",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            orch.disableStep("b")
            orch.runCycle(0, 1)
            let util = orch.stepLoopUtilization
            let room = orch.stepLoopHeadroom
        """)
        assert val(i, "util") == {}
        assert val(i, "room") == {}

    def test_utilization_and_headroom_reset_with_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "m",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            orch.runCycle(0, 1)
            orch.resetHistory()
            let util = orch.stepLoopUtilization
            let room = orch.stepLoopHeadroom
        """)
        assert val(i, "util") == {}
        assert val(i, "room") == {}


class TestOrchestratorLoopPressureInSummary:
    def test_get_step_summary_contains_loop_pressure_fields(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 4,
                8
            )
            orch.runCycle(0, 1)
            let s = orch.getStepSummary("svc")
        """)
        s = val(i, "s")
        assert s["loopUtilization"] == 0.5
        assert s["loopHeadroom"] == 4.0

    def test_summary_unmanaged_step_has_none_loop_pressure_fields(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            let s = orch.summary
        """)
        s = val(i, "s")
        assert s[0]["loopUtilization"] is None
        assert s[0]["loopHeadroom"] is None

    def test_summary_managed_no_history_has_none_loop_pressure_fields(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "m",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            let s = orch.summary
        """)
        s = val(i, "s")
        assert s[0]["loopUtilization"] is None
        assert s[0]["loopHeadroom"] is None
