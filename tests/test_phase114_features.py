"""Phase 114: Managed orchestrator step loops for structural pathways."""

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


class TestOrchestratorManagedSteps:
    def test_add_managed_step_returns_count(self):
        i = run("""
            let orch = Orchestrator.new()
            let n1 = orch.addStep("base", fn(state) => state)
            let n2 = orch.addManagedStep("managed", fn(state) => state, fn(state) => true, 3)
        """)
        assert val(i, "n1") == 1
        assert val(i, "n2") == 2

    def test_managed_step_loops_until_step_solved(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "refine",
                fn(state, cycle, name, attempt) {
                    if state == undefined { return attempt }
                    return state + attempt
                },
                fn(state, cycle, name, attempt) => state >= 6,
                5
            )
            let out = orch.runCycle(undefined, 1)
        """)
        assert val(i, "out") == 6

    def test_managed_step_not_solved_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let orch = Orchestrator.new()
                orch.addManagedStep(
                    "never",
                    fn(state) => 1,
                    fn(state) => false,
                    2
                )
                orch.runCycle(0, 1)
            """)

    def test_managed_step_invalid_max_loops_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let orch = Orchestrator.new()
                orch.addManagedStep("x", fn(state) => state, fn(state) => true, "bad")
            """)

    def test_run_managed_with_mixed_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "stabilize",
                fn(state, cycle, name, attempt) {
                    if state == undefined { return attempt }
                    return state + 1
                },
                fn(state) => state >= 2,
                4
            )
            orch.addStep("boost", fn(state) => state + 1)
            let out = orch.runManaged(fn(state) => state >= 5, undefined, 5)
        """)
        assert val(i, "out") == 5

    def test_registry_loop_inside_managed_step(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("micro", fn(state) {
                if state == undefined { return 1 }
                return state + 1
            })

            let orch = Orchestrator.new()
            orch.addManagedStep(
                "innerServiceLoop",
                fn(state, cycle, name, attempt) {
                    return reg.runUntilSolved("micro", fn(inner) => inner >= 2, state, 5)
                },
                fn(state) => state >= 2,
                2
            )
            orch.addStep("finalize", fn(state) => state + 1)

            let out = orch.runManaged(fn(state) => state >= 4, undefined, 5)
        """)
        assert val(i, "out") == 4

