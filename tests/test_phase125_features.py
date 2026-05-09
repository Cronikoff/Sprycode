"""Phase 125: Orchestrator loop-pressure pathway and bottleneck ranking."""

from sprycode.interpreter import Interpreter, SPRY_UNDEFINED
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


class TestOrchestratorLoopPressurePathway:
    def test_pathway_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let path = orch.stepPressurePath
            let lead = orch.primaryBottleneck
        """)
        assert val(i, "path") == []
        assert val(i, "lead") is SPRY_UNDEFINED

    def test_pathway_orders_by_loop_utilization_desc(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "a",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                4
            ) // util: 3/4 = 0.75
            orch.addManagedStep(
                "b",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                6
            ) // util: 3/6 = 0.5
            orch.addManagedStep(
                "c",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 4,
                5
            ) // util: 4/5 = 0.8
            orch.runCycle(0, 1)
            let path = orch.stepPressurePath
            let lead = orch.primaryBottleneck
            let full = orch.summary
        """)
        assert val(i, "path") == ["c", "a", "b"]
        assert val(i, "lead") == "c"
        full = val(i, "full")
        by_name = {item["name"]: item for item in full}
        assert by_name["c"]["loopPressureRank"] == 1
        assert by_name["a"]["loopPressureRank"] == 2
        assert by_name["b"]["loopPressureRank"] == 3

    def test_pathway_tie_breaks_by_step_order(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "x",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                4
            ) // util: 2/4 = 0.5
            orch.addManagedStep(
                "y",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                6
            ) // util: 3/6 = 0.5
            orch.runCycle(0, 1)
            let path = orch.stepPressurePath
        """)
        assert val(i, "path") == ["x", "y"]

    def test_pathway_skips_unmanaged_or_disabled_or_no_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("u", fn(state) => state + 1)
            orch.addManagedStep(
                "m1",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            orch.addManagedStep(
                "m2",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            orch.disableStep("m2")
            orch.runCycle(0, 1)
            let path = orch.stepPressurePath
            let full = orch.summary
        """)
        assert val(i, "path") == ["m1"]
        full = val(i, "full")
        by_name = {item["name"]: item for item in full}
        assert by_name["u"]["loopPressureRank"] is None
        assert by_name["m1"]["loopPressureRank"] == 1
        assert by_name["m2"]["loopPressureRank"] is None

    def test_pathway_reset_clears_ranking(self):
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
            let path = orch.stepPressurePath
            let lead = orch.primaryBottleneck
            let s = orch.getStepSummary("m")
        """)
        assert val(i, "path") == []
        assert val(i, "lead") is SPRY_UNDEFINED
        assert val(i, "s")["loopPressureRank"] is None
