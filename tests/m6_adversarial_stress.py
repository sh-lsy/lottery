"""
tests/m6_adversarial_stress.py

Adversarial Stress Test Suite & Latency Benchmarks for Milestone 6 FastAPI Endpoints.
Covers:
1. Malformed inputs: non-integer balls, out-of-range balls, duplicate red balls, invalid counts.
2. Boundary pagination queries: page <= 0, page > total, page_size <= 0, page_size boundaries.
3. Non-existent entities: batches, issues, metrics (HTTP 404).
4. Missing required payload fields (HTTP 422).
5. Clean error handling: zero unhandled HTTP 500 crashes.
6. Empirical latency benchmarking (<100ms prediction, <50ms sandbox collision).
"""

import os
import sys
import time
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


class StressTestReporter:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def record(self, category: str, test_name: str, endpoint: str, expected_status: int, actual_status: int, passed: bool, detail: str = ""):
        self.results.append({
            "category": category,
            "test_name": test_name,
            "endpoint": endpoint,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "passed": passed,
            "detail": detail,
        })

    def print_summary(self):
        print("\n" + "=" * 90)
        print(f"{'CATEGORY':<20} | {'TEST NAME':<32} | {'EXPECT':<6} | {'ACTUAL':<6} | {'PASS/FAIL'}")
        print("=" * 90)
        passed_count = sum(1 for r in self.results if r["passed"])
        failed_count = sum(1 for r in self.results if not r["passed"])
        for r in self.results:
            status_str = "PASS" if r["passed"] else "FAIL"
            print(f"{r['category']:<20} | {r['test_name'][:32]:<32} | {r['expected_status']:<6} | {r['actual_status']:<6} | {status_str}")
        print("-" * 90)
        print(f"Total stress tests: {len(self.results)}, Passed: {passed_count}, Failed: {failed_count}")
        print("=" * 90 + "\n")


reporter = StressTestReporter()


def run_malformed_input_tests():
    print(">>> Running Malformed Input Stress Tests...")

    # Sandbox: Non-integer red ball
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": ["invalid", 2, 3, 4, 5, 6], "blue": 1})
    reporter.record("Malformed Input", "Non-integer red ball (string)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Float red ball
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1.5, 2, 3, 4, 5, 6], "blue": 1})
    reporter.record("Malformed Input", "Non-integer red ball (float)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Non-integer blue ball
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6], "blue": "xyz"})
    reporter.record("Malformed Input", "Non-integer blue ball", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Red ball < 1
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [0, 2, 3, 4, 5, 6], "blue": 1})
    reporter.record("Malformed Input", "Red ball below range (0)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Red ball < 0 (negative)
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [-5, 2, 3, 4, 5, 6], "blue": 1})
    reporter.record("Malformed Input", "Negative red ball (-5)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Red ball > 33
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 34], "blue": 1})
    reporter.record("Malformed Input", "Red ball above range (34)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Red ball > 100
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 999], "blue": 1})
    reporter.record("Malformed Input", "Extreme red ball (999)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Blue ball < 1
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6], "blue": 0})
    reporter.record("Malformed Input", "Blue ball below range (0)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Blue ball negative
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6], "blue": -8})
    reporter.record("Malformed Input", "Negative blue ball (-8)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Blue ball > 16
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6], "blue": 17})
    reporter.record("Malformed Input", "Blue ball above range (17)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Blue ball extreme
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6], "blue": 9999})
    reporter.record("Malformed Input", "Extreme blue ball (9999)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Duplicate red balls (pair)
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 1, 3, 4, 5, 6], "blue": 1})
    reporter.record("Malformed Input", "Duplicate red balls (pair)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: All identical red balls
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [10, 10, 10, 10, 10, 10], "blue": 1})
    reporter.record("Malformed Input", "All identical red balls", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Red ball count < 6 (5 balls)
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5], "blue": 1})
    reporter.record("Malformed Input", "Too few red balls (5)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox: Red ball count > 6 (7 balls)
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6, 7], "blue": 1})
    reporter.record("Malformed Input", "Too many red balls (7)", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict save: wrong note counts (0 notes)
    r = client.post("/api/v1/predict/save", json={"target_issue": "2026999", "notes": []})
    reporter.record("Malformed Input", "Save notes: 0 notes", "/api/v1/predict/save", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict save: wrong note counts (4 notes)
    r = client.post("/api/v1/predict/save", json={
        "target_issue": "2026999",
        "notes": [{"note_index": i, "reds": [1, 2, 3, 4, 5, 6], "blue": 1} for i in range(1, 5)]
    })
    reporter.record("Malformed Input", "Save notes: 4 notes", "/api/v1/predict/save", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict save: wrong note counts (6 notes)
    r = client.post("/api/v1/predict/save", json={
        "target_issue": "2026999",
        "notes": [{"note_index": i, "reds": [1, 2, 3, 4, 5, 6], "blue": 1} for i in range(1, 7)]
    })
    reporter.record("Malformed Input", "Save notes: 6 notes", "/api/v1/predict/save", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict generate: sum_min > sum_max
    r = client.post("/api/v1/predict/generate", json={"sum_min": 140, "sum_max": 70})
    reporter.record("Malformed Input", "Generate: sum_min > sum_max", "/api/v1/predict/generate", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict generate: span_min > span_max
    r = client.post("/api/v1/predict/generate", json={"span_min": 30, "span_max": 10})
    reporter.record("Malformed Input", "Generate: span_min > span_max", "/api/v1/predict/generate", 422, r.status_code, r.status_code == 422, str(r.json()))


def run_boundary_pagination_tests():
    print(">>> Running Boundary Pagination Stress Tests...")

    # History draws: page=0
    r = client.get("/api/v1/history/draws?page=0")
    reporter.record("Boundary Pagination", "History draws: page=0", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: page=-1
    r = client.get("/api/v1/history/draws?page=-1")
    reporter.record("Boundary Pagination", "History draws: page=-1", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: page=999999 (should succeed and return empty items)
    r = client.get("/api/v1/history/draws?page=999999")
    passed = r.status_code == 200 and len(r.json().get("items", [1])) == 0
    reporter.record("Boundary Pagination", "History draws: page=999999", "/api/v1/history/draws", 200, r.status_code, passed, f"Items: {len(r.json().get('items', []))}")

    # History draws: page_size=0
    r = client.get("/api/v1/history/draws?page_size=0")
    reporter.record("Boundary Pagination", "History draws: page_size=0", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: page_size=-10
    r = client.get("/api/v1/history/draws?page_size=-10")
    reporter.record("Boundary Pagination", "History draws: page_size=-10", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: page_size=500 (upper bound)
    r = client.get("/api/v1/history/draws?page_size=500")
    passed = r.status_code == 200 and len(r.json().get("items", [])) == 500
    reporter.record("Boundary Pagination", "History draws: page_size=500", "/api/v1/history/draws", 200, r.status_code, passed, f"Items: {len(r.json().get('items', []))}")

    # History draws: page_size=501 (exceeds le=500)
    r = client.get("/api/v1/history/draws?page_size=501")
    reporter.record("Boundary Pagination", "History draws: page_size=501", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: invalid sort_order
    r = client.get("/api/v1/history/draws?sort_order=invalid_sort")
    reporter.record("Boundary Pagination", "History draws: invalid sort", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: start_issue > end_issue (should return 400 Bad Request)
    r = client.get("/api/v1/history/draws?start_issue=2026120&end_issue=2026100")
    reporter.record("Boundary Pagination", "History draws: start > end issue", "/api/v1/history/draws", 400, r.status_code, r.status_code == 400, str(r.json()))

    # History draws: search_ball < 1
    r = client.get("/api/v1/history/draws?search_ball=0")
    reporter.record("Boundary Pagination", "History draws: search_ball=0", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History draws: search_ball > 33
    r = client.get("/api/v1/history/draws?search_ball=34")
    reporter.record("Boundary Pagination", "History draws: search_ball=34", "/api/v1/history/draws", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict batches: page=0
    r = client.get("/api/v1/predict/batches?page=0")
    reporter.record("Boundary Pagination", "Predict batches: page=0", "/api/v1/predict/batches", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict batches: page=-5
    r = client.get("/api/v1/predict/batches?page=-5")
    reporter.record("Boundary Pagination", "Predict batches: page=-5", "/api/v1/predict/batches", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict batches: page_size=0
    r = client.get("/api/v1/predict/batches?page_size=0")
    reporter.record("Boundary Pagination", "Predict batches: page_size=0", "/api/v1/predict/batches", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict batches: page_size=100 (upper bound)
    r = client.get("/api/v1/predict/batches?page_size=100")
    reporter.record("Boundary Pagination", "Predict batches: page_size=100", "/api/v1/predict/batches", 200, r.status_code, r.status_code == 200, f"Items: {len(r.json().get('items', []))}")

    # Predict batches: page_size=101 (exceeds limit 100)
    r = client.get("/api/v1/predict/batches?page_size=101")
    reporter.record("Boundary Pagination", "Predict batches: page_size=101", "/api/v1/predict/batches", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History omissions: limit < 10
    r = client.get("/api/v1/history/omissions?limit=5")
    reporter.record("Boundary Pagination", "History omissions: limit=5", "/api/v1/history/omissions", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History omissions: limit > 100
    r = client.get("/api/v1/history/omissions?limit=150")
    reporter.record("Boundary Pagination", "History omissions: limit=150", "/api/v1/history/omissions", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History metrics: limit=0
    r = client.get("/api/v1/history/metrics?limit=0")
    reporter.record("Boundary Pagination", "History metrics: limit=0", "/api/v1/history/metrics", 422, r.status_code, r.status_code == 422, str(r.json()))

    # History metrics: limit=501
    r = client.get("/api/v1/history/metrics?limit=501")
    reporter.record("Boundary Pagination", "History metrics: limit=501", "/api/v1/history/metrics", 422, r.status_code, r.status_code == 422, str(r.json()))


def run_non_existent_entity_tests():
    print(">>> Running Non-Existent Entity (404) Stress Tests...")

    # Predict batch detail: non-existent large ID
    r = client.get("/api/v1/predict/batches/9999999")
    reporter.record("Non-Existent Entity", "Batch ID 9999999", "/api/v1/predict/batches/9999999", 404, r.status_code, r.status_code == 404, str(r.json()))

    # Predict batch detail: negative ID
    r = client.get("/api/v1/predict/batches/-1")
    reporter.record("Non-Existent Entity", "Batch ID -1", "/api/v1/predict/batches/-1", 404, r.status_code, r.status_code == 404, str(r.json()))

    # Backtest verify: non-existent historical issue
    r = client.post("/api/v1/backtest/verify/1990001")
    reporter.record("Non-Existent Entity", "Verify issue 1990001", "/api/v1/backtest/verify/1990001", 404, r.status_code, r.status_code == 404, str(r.json()))

    # Backtest verify: invalid format issue string
    r = client.post("/api/v1/backtest/verify/non_existent_issue_xyz")
    reporter.record("Non-Existent Entity", "Verify invalid issue", "/api/v1/backtest/verify/non_existent_issue_xyz", 404, r.status_code, r.status_code == 404, str(r.json()))

    # History metrics by issue: non-existent issue
    r = client.get("/api/v1/history/metrics/1990001")
    reporter.record("Non-Existent Entity", "Metrics issue 1990001", "/api/v1/history/metrics/1990001", 404, r.status_code, r.status_code == 404, str(r.json()))


def run_missing_payload_fields_tests():
    print(">>> Running Missing Required Payload Fields Stress Tests...")

    # Predict generate with empty JSON: should be accepted using defaults (200 OK)
    r = client.post("/api/v1/predict/generate", json={})
    passed = r.status_code == 200 and len(r.json().get("notes", [])) == 5
    reporter.record("Payload Validation", "Generate: empty body defaults", "/api/v1/predict/generate", 200, r.status_code, passed, "Default 5 notes generated")

    # Predict save: empty JSON (missing target_issue, notes)
    r = client.post("/api/v1/predict/save", json={})
    reporter.record("Payload Validation", "Save: empty body", "/api/v1/predict/save", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict save: missing notes field
    r = client.post("/api/v1/predict/save", json={"target_issue": "2026123"})
    reporter.record("Payload Validation", "Save: missing notes", "/api/v1/predict/save", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Predict save: missing target_issue
    r = client.post("/api/v1/predict/save", json={
        "notes": [{"note_index": i, "reds": [1, 2, 3, 4, 5, 6], "blue": 1} for i in range(1, 6)]
    })
    reporter.record("Payload Validation", "Save: missing target_issue", "/api/v1/predict/save", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox collision: empty JSON
    r = client.post("/api/v1/backtest/sandbox/collision", json={})
    reporter.record("Payload Validation", "Sandbox: empty body", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox collision: missing blue ball
    r = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6]})
    reporter.record("Payload Validation", "Sandbox: missing blue", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Sandbox collision: missing reds list
    r = client.post("/api/v1/backtest/sandbox/collision", json={"blue": 7})
    reporter.record("Payload Validation", "Sandbox: missing reds", "/api/v1/backtest/sandbox/collision", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Backtest run: n_issues < 1
    r = client.post("/api/v1/backtest/run", json={"n_issues": 0})
    reporter.record("Payload Validation", "Backtest run: n_issues=0", "/api/v1/backtest/run", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Backtest run: n_issues > 500
    r = client.post("/api/v1/backtest/run", json={"n_issues": 501})
    reporter.record("Payload Validation", "Backtest run: n_issues=501", "/api/v1/backtest/run", 422, r.status_code, r.status_code == 422, str(r.json()))

    # Backtest compare: n_issues < 1
    r = client.post("/api/v1/backtest/compare", json={"n_issues": -10})
    reporter.record("Payload Validation", "Backtest compare: n_issues=-10", "/api/v1/backtest/compare", 422, r.status_code, r.status_code == 422, str(r.json()))


def run_latency_benchmarks() -> Dict[str, Any]:
    print("\n>>> Running Empirical Latency Benchmarks (Warmup + 20 trials)...")

    # Warmup
    client.post("/api/v1/predict/generate", json={"persist": False})
    client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 4, 17, 19, 30], "blue": 9})

    # Benchmark POST /api/v1/predict/generate
    predict_latencies: List[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        resp = client.post("/api/v1/predict/generate", json={"persist": False})
        t1 = time.perf_counter()
        assert resp.status_code == 200
        predict_latencies.append((t1 - t0) * 1000.0)

    # Benchmark POST /api/v1/backtest/sandbox/collision (3,519 draws)
    sandbox_latencies: List[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        resp = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 4, 17, 19, 30], "blue": 9})
        t1 = time.perf_counter()
        assert resp.status_code == 200
        sandbox_latencies.append((t1 - t0) * 1000.0)

    p_min = min(predict_latencies)
    p_max = max(predict_latencies)
    p_mean = sum(predict_latencies) / len(predict_latencies)
    p_sorted = sorted(predict_latencies)
    p_median = p_sorted[len(p_sorted) // 2]
    p_p95 = p_sorted[int(len(p_sorted) * 0.95)]
    p_pass = p_mean < 100.0

    s_min = min(sandbox_latencies)
    s_max = max(sandbox_latencies)
    s_mean = sum(sandbox_latencies) / len(sandbox_latencies)
    s_sorted = sorted(sandbox_latencies)
    s_median = s_sorted[len(s_sorted) // 2]
    s_p95 = s_sorted[int(len(s_sorted) * 0.95)]
    s_pass = s_mean < 50.0

    print("-" * 80)
    print(f"BENCHMARK: POST /api/v1/predict/generate (Target: <100ms offline)")
    print(f"  Min: {p_min:.2f}ms | Median: {p_median:.2f}ms | Mean: {p_mean:.2f}ms | P95: {p_p95:.2f}ms | Max: {p_max:.2f}ms")
    print(f"  Result: {'PASS (Mean < 100ms)' if p_pass else 'FAIL (Exceeds 100ms)'}")
    print("-" * 80)
    print(f"BENCHMARK: POST /api/v1/backtest/sandbox/collision (Target: <50ms across 3519 draws)")
    print(f"  Min: {s_min:.2f}ms | Median: {s_median:.2f}ms | Mean: {s_mean:.2f}ms | P95: {s_p95:.2f}ms | Max: {s_max:.2f}ms")
    print(f"  Result: {'PASS (Mean < 50ms)' if s_pass else 'FAIL (Exceeds 50ms)'}")
    print("-" * 80 + "\n")

    return {
        "predict": {
            "min": p_min,
            "max": p_max,
            "mean": p_mean,
            "median": p_median,
            "p95": p_p95,
            "target": "<100ms",
            "passed": p_pass,
        },
        "sandbox": {
            "min": s_min,
            "max": s_max,
            "mean": s_mean,
            "median": s_median,
            "p95": s_p95,
            "target": "<50ms",
            "passed": s_pass,
        },
    }


def main():
    print("=" * 80)
    print("STARTING MILSTONE 6 ADVERSARIAL STRESS TESTING HARNESS")
    print("=" * 80)

    run_malformed_input_tests()
    run_boundary_pagination_tests()
    run_non_existent_entity_tests()
    run_missing_payload_fields_tests()

    reporter.print_summary()

    benchmark_stats = run_latency_benchmarks()

    all_tests_passed = all(r["passed"] for r in reporter.results)
    latency_passed = benchmark_stats["predict"]["passed"] and benchmark_stats["sandbox"]["passed"]

    if all_tests_passed and latency_passed:
        print("[FINAL HARNESS VERDICT]: ALL ASSERTIONS AND LATENCY GATES MET!")
        sys.exit(0)
    elif all_tests_passed and not latency_passed:
        print("[FINAL HARNESS VERDICT]: FUNCTIONAL PASS, BUT LATENCY TARGET BREACHED!")
        sys.exit(2)
    else:
        print("[FINAL HARNESS VERDICT]: ADVERSARIAL TEST FAILURES DETECTED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
