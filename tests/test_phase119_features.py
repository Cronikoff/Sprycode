"""Phase 119: Orchestrator step priority / ordering APIs."""

import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
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


class TestOrchestratorGetStepIndex:
    def test_get_step_index_first_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let idx = orch.getStepIndex("a")
        """)
        assert val(i, "idx") == 0

    def test_get_step_index_second_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let idx = orch.getStepIndex("b")
        """)
        assert val(i, "idx") == 1

    def test_get_step_index_missing_returns_minus_one(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            let idx = orch.getStepIndex("ghost")
        """)
        assert val(i, "idx") == -1

    def test_get_step_index_empty_returns_minus_one(self):
        i = run("""
            let orch = Orchestrator.new()
            let idx = orch.getStepIndex("a")
        """)
        assert val(i, "idx") == -1


class TestOrchestratorMoveStepFirst:
    def test_move_step_first_from_end(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.moveStepFirst("b")
            let names = orch.stepNames
        """)
        assert val(i, "names") == ["b", "a"]

    def test_move_step_first_affects_execution_order(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.moveStepFirst("b")
            let out = orch.runCycle(1, 1)
        """)
        # b first: 1*10=10, then a: 10+1=11
        assert val(i, "out") == 11

    def test_move_step_first_already_first(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let result = orch.moveStepFirst("a")
            let names = orch.stepNames
        """)
        assert val(i, "result") is True
        assert val(i, "names") == ["a", "b"]

    def test_move_step_first_returns_false_when_missing(self):
        i = run("""
            let orch = Orchestrator.new()
            let result = orch.moveStepFirst("ghost")
        """)
        assert val(i, "result") is False


class TestOrchestratorMoveStepLast:
    def test_move_step_last_from_start(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.moveStepLast("a")
            let names = orch.stepNames
        """)
        assert val(i, "names") == ["b", "a"]

    def test_move_step_last_affects_execution_order(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.moveStepLast("a")
            let out = orch.runCycle(1, 1)
        """)
        # b first: 1*10=10, then a: 10+1=11
        assert val(i, "out") == 11

    def test_move_step_last_returns_false_when_missing(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            let result = orch.moveStepLast("ghost")
        """)
        assert val(i, "result") is False


class TestOrchestratorMoveStepBefore:
    def test_move_step_before_target(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            orch.addStep("c", fn(state) => state)
            orch.moveStepBefore("c", "a")
            let names = orch.stepNames
        """)
        assert val(i, "names") == ["c", "a", "b"]

    def test_move_step_before_execution_order(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.addStep("c", fn(state) => state - 1)
            // move c before a → order: c, a, b
            orch.moveStepBefore("c", "a")
            let out = orch.runCycle(2, 1)
        """)
        # c: 2-1=1, a: 1+1=2, b: 2*10=20
        assert val(i, "out") == 20

    def test_move_step_before_returns_true(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let result = orch.moveStepBefore("b", "a")
        """)
        assert val(i, "result") is True

    def test_move_step_before_missing_name_returns_false(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            let result = orch.moveStepBefore("ghost", "a")
        """)
        assert val(i, "result") is False

    def test_move_step_before_missing_target_returns_false(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            let result = orch.moveStepBefore("a", "ghost")
        """)
        assert val(i, "result") is False

    def test_move_step_before_same_name_target_is_noop(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let result = orch.moveStepBefore("a", "a")
            let names = orch.stepNames
        """)
        assert val(i, "result") is True
        assert val(i, "names") == ["a", "b"]


class TestOrchestratorMoveStepAfter:
    def test_move_step_after_target(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            orch.addStep("c", fn(state) => state)
            orch.moveStepAfter("a", "c")
            let names = orch.stepNames
        """)
        assert val(i, "names") == ["b", "c", "a"]

    def test_move_step_after_execution_order(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.addStep("c", fn(state) => state - 1)
            // move a after c → order: b, c, a
            orch.moveStepAfter("a", "c")
            let out = orch.runCycle(2, 1)
        """)
        # b: 2*10=20, c: 20-1=19, a: 19+1=20
        assert val(i, "out") == 20

    def test_move_step_after_returns_true(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let result = orch.moveStepAfter("a", "b")
        """)
        assert val(i, "result") is True

    def test_move_step_after_missing_name_returns_false(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            let result = orch.moveStepAfter("ghost", "a")
        """)
        assert val(i, "result") is False

    def test_move_step_after_missing_target_returns_false(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            let result = orch.moveStepAfter("a", "ghost")
        """)
        assert val(i, "result") is False

    def test_move_step_after_same_name_target_is_noop(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let result = orch.moveStepAfter("a", "a")
            let names = orch.stepNames
        """)
        assert val(i, "result") is True
        assert val(i, "names") == ["a", "b"]


class TestOrchestratorOrderingIntegration:
    def test_reordering_preserves_enabled_disabled_state(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state * 10)
            orch.disableStep("a")
            orch.moveStepFirst("b")
            let out = orch.runCycle(3, 1)
        """)
        # b runs first (only enabled): 3*10=30, a is disabled
        assert val(i, "out") == 30

    def test_get_step_index_after_move(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            orch.addStep("c", fn(state) => state)
            orch.moveStepLast("a")
            let idxA = orch.getStepIndex("a")
            let idxC = orch.getStepIndex("c")
        """)
        assert val(i, "idxA") == 2
        assert val(i, "idxC") == 1

    def test_convergence_unchanged_after_reorder(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 1)
            orch.addStep("noop", fn(state) => state)
            orch.moveStepLast("inc")
            let out = orch.runManaged(fn(state) => state >= 3, 0, 10)
        """)
        assert val(i, "out") == 3
