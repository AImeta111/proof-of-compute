#!/usr/bin/env python3
"""Stage-2 demo job: consume grid_results.json, emit best_strategy.json.
Deterministic — same input bits always produce the same output bits."""
import json

grid = json.load(open("grid_results.json"))
best = max(grid, key=lambda r: r["equity"])
equities = sorted(r["equity"] for r in grid)
n = len(equities)
out = {
    "best": best,
    "cells": n,
    "median_equity": round(equities[n // 2], 6),
    "top_decile_mean": round(sum(equities[-n // 10:]) / (n // 10), 6),
    "losing_cells": sum(1 for e in equities if e < 10_000),
}
json.dump(out, open("best_strategy.json", "w"), sort_keys=True, separators=(",", ":"))
print("best:", best)
