"""Phase 134: Per-target state evolution checkpoints (stateBefore/stateAfter) in managed pathway report."""

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


class TestPathwayReportStateEvolution:
    def test_single_target_state_before_and_after(self):
        # The bootstrap cycle transforms state=0 → 5 before the target loop starts.
        # The target loop then runs 4 cycles (svc matures), leaving state=19.
        # stateBefore captures state at entry to runTargetUntilMature; stateAfter at exit.
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let targets = rep["targets"]
        """)
        targets = val(i, "targets")
        assert len(targets) == 1
        t = targets[0]
        assert t["stateBefore"] == 5   # state after bootstrap cycle
        assert t["stateAfter"] == 19   # state after svc reaches maturity
        assert t["stateAfter"] >= t["stateBefore"]  # invariant: state grows forward

    def test_two_targets_state_evolution(self):
        # svcA matures inside the bootstrap cycle (lower loop demand), so only svcB
        # is returned as a capability target by nextCapabilityTarget. Only the step
        # that requires an explicit micromanagement run to reach maturity appears.
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
            let targets = rep["targets"]
            let finalState = rep["state"]
        """)
        targets = val(i, "targets")
        # Only svcB appears: svcA reaches maturity during the bootstrap cycle so it
        # is never the nextCapabilityTarget when the target loop begins.
        assert len(targets) == 1
        t = targets[0]
        assert t["name"] == "svcB"
        assert t["stateBefore"] == 13
        assert t["stateAfter"] == 73
        # Invariant: state should grow throughout the pathway.
        assert t["stateAfter"] >= t["stateBefore"]
        # stateAfter of last target matches final report state
        assert val(i, "finalState") == t["stateAfter"]

    def test_state_after_is_greater_than_state_before(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (5 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 8)
            let t = rep["targets"][0]
            let before = t["stateBefore"]
            let after = t["stateAfter"]
        """)
        before = val(i, "before")
        after = val(i, "after")
        assert isinstance(before, (int, float))
        assert isinstance(after, (int, float))
        assert after > before

    def test_no_managed_steps_yields_empty_targets(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []

    def test_state_before_reflects_bootstrap_state(self):
        """stateBefore should be greater than initial_state when bootstrap cycle runs."""
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let stateBefore = rep["targets"][0]["stateBefore"]
        """)
        # Bootstrap cycle runs one managed loop before target loop starts,
        # so stateBefore > 0 (the initial state).
        assert val(i, "stateBefore") > 0
