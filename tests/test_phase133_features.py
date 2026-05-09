"""Phase 133: Per-target pathway progress checkpoints in managed report."""

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


class TestPathwayReportPerTargetProgress:
    def test_target_includes_remaining_and_fully_developed_checkpoints(self):
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
            let fully = rep["fullyDeveloped"]
            let remain = rep["remainingTargets"]
        """)
        targets = val(i, "targets")
        assert len(targets) == 1
        t = targets[0]
        assert t["name"] == "svcB"
        assert t["remainingTargetsAfter"] == []
        assert t["fullyDevelopedAfter"] is True
        assert val(i, "remain") == []
        assert val(i, "fully") is True

    def test_single_target_checkpoint_values(self):
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
        assert t["remainingTargetsAfter"] == []
        assert t["fullyDevelopedAfter"] is True

    def test_no_managed_services_still_has_no_targets(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(42, 10)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []
