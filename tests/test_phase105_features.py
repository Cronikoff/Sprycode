"""Tests for Phase 105: additional performance API compatibility."""
from __future__ import annotations

from typing import Any

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


class TestPerformanceGetEntries:
    def test_get_entries_lists_all_entries(self):
        i = run("""
performance.mark("a");
performance.measure("m1");
let v = performance.getEntries().length;
""")
        assert val(i) == 2


class TestPerformanceTimeOrigin:
    def test_time_origin_is_number(self):
        i = run("let v = typeof performance.timeOrigin;")
        assert val(i) == "number"


class TestPerformanceMeasureNumbers:
    def test_measure_accepts_numeric_start_and_end(self):
        i = run("""
let m = performance.measure("delta", 10, 15.5);
let v = m.duration === 5.5;
""")
        assert val(i) is True


class TestPerformanceResourceTiming:
    def test_clear_resource_timings_removes_resource_entries(self):
        i = run("""
performance.clearResourceTimings();
let v = true;
""")
        assert val(i) is True
        perf = i.globals.get("performance")
        perf._entries.extend([
            {"name": "r1", "entryType": "resource", "startTime": 1.0, "duration": 1.0},
            {"name": "m1", "entryType": "measure", "startTime": 1.0, "duration": 1.0},
        ])
        perf.clearResourceTimings()
        assert len([e for e in perf._entries if e.get("entryType") == "resource"]) == 0
        assert len([e for e in perf._entries if e.get("entryType") == "measure"]) == 1

    def test_set_resource_timing_buffer_size_sets_non_negative_int(self):
        i = run("""
performance.setResourceTimingBufferSize(500);
let v = true;
""")
        assert val(i) is True
        perf = i.globals.get("performance")
        assert perf._resource_timing_buffer_size == 500

    def test_set_resource_timing_buffer_size_clamps_invalid_values(self):
        i = run("""
performance.setResourceTimingBufferSize(-10);
performance.setResourceTimingBufferSize("bad");
let v = true;
""")
        assert val(i) is True
        perf = i.globals.get("performance")
        assert perf._resource_timing_buffer_size == 0
