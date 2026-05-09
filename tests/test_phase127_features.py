"""Phase 127: Orchestrator capability pathway targeting for managed looped services."""

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


class TestOrchestratorCapabilityPathway:
    def test_capability_pathway_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let path = orch.capabilityPathway
            let next = orch.nextCapabilityTarget
            let done = orch.capabilityFullyDeveloped
        """)
        assert val(i, "path") == []
        assert val(i, "next") is SPRY_UNDEFINED
        assert val(i, "done") is SPRY_UNDEFINED

    def test_capability_pathway_orders_by_stage_then_utilization(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "crit",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 9,
                10
            ) // critical
            orch.addManagedStep(
                "stretch",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 7,
                10
            ) // stretched
            orch.addManagedStep(
                "stab",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 4,
                10
            ) // stabilizing
            orch.addManagedStep(
                "mature",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                10
            ) // mature
            orch.runCycle(0, 1)
            let path = orch.capabilityPathway
            let next = orch.nextCapabilityTarget
            let done = orch.capabilityFullyDeveloped
            let s = orch.summary
        """)
        assert val(i, "path") == ["crit", "stretch", "stab", "mature"]
        assert val(i, "next") == "crit"
        assert val(i, "done") is False
        by_name = {item["name"]: item for item in val(i, "s")}
        assert by_name["crit"]["capabilityPathRank"] == 1
        assert by_name["stretch"]["capabilityPathRank"] == 2
        assert by_name["stab"]["capabilityPathRank"] == 3
        assert by_name["mature"]["capabilityPathRank"] == 4

    def test_capability_target_undefined_when_all_mature(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "a",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 1,
                10
            )
            orch.addManagedStep(
                "b",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                10
            )
            orch.runCycle(0, 1)
            let next = orch.nextCapabilityTarget
            let done = orch.capabilityFullyDeveloped
        """)
        assert val(i, "next") is SPRY_UNDEFINED
        assert val(i, "done") is True

    def test_capability_pathway_resets_with_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 8,
                10
            )
            orch.runCycle(0, 1)
            orch.resetHistory()
            let path = orch.capabilityPathway
            let next = orch.nextCapabilityTarget
            let done = orch.capabilityFullyDeveloped
            let s = orch.getStepSummary("svc")
        """)
        assert val(i, "path") == []
        assert val(i, "next") is SPRY_UNDEFINED
        assert val(i, "done") is SPRY_UNDEFINED
        assert val(i, "s")["capabilityPathRank"] is None
