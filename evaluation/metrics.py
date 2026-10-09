"""Aggregate metrics for hallucination and safety evaluation."""
from statistics import mean
from typing import Iterable

from backend.app.schemas import SafetyReport


def _mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    return round(mean(xs), 4) if xs else float("nan")


def aggregate(reports: list[SafetyReport]) -> dict:
    """Metrics over a list of safety reports (one per generated output)."""
    n = len(reports)
    if not n:
        return {}
    g = lambda k: [r.metrics[k] for r in reports if k in r.metrics]
    return {
        "outputs": n,
        "pass_rate": _mean(1.0 if r.passed else 0.0 for r in reports),
        "numerical_accuracy": _mean(g("numerical_accuracy")),
        "unit_preservation": _mean(g("unit_preservation")),
        "range_accuracy": _mean(g("range_accuracy")),
        "entity_preservation": _mean(g("entity_preservation")),
        "abstention_correctness": _mean(g("abstention")),
        "unsupported_claim_rate": _mean(1.0 if r.metrics.get("unsupported_claim_count", 0) > 0 else 0.0 for r in reports),
        "unsafe_recommendation_rate": _mean(1.0 if r.metrics.get("unsafe_recommendation_count", 0) > 0 else 0.0 for r in reports),
        "translation_meaning_preserved": _mean(g("meaning_preserved")),
        "judge_fluency_mean_1_to_5": _mean(g("judge_fluency")),
    }


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"precision": round(p, 4), "recall": round(r, 4), "tp": tp, "fp": fp, "fn": fn}
