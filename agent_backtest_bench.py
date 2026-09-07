#!/usr/bin/env python3
"""
AIMETA agent-backtest benchmark — representative compute workload.

Simulates the strategy-backtest loop of a trading agent:
  * deterministic synthetic OHLCV series (seeded — identical on any machine)
  * grid search over momentum/mean-reversion parameter combinations
  * pure-CPU, no network, no external data — results comparable across hosts

Outputs machine specs, wall time, throughput, and cost per full grid at a
given hourly price. Run identically on Fluence and on any baseline host.

Usage:  python3 agent_backtest_bench.py [--hourly-usd 0.0139] [--bars 500000] [--grid 96]
"""
import argparse, json, math, os, platform, random, time


def gen_series(n_bars: int, seed: int = 42):
    rnd = random.Random(seed)
    price = 100.0
    closes = []
    for _ in range(n_bars):
        drift = 0.00002
        shock = rnd.gauss(0, 0.004)
        # occasional regime jumps, like real crypto tape
        if rnd.random() < 0.0004:
            shock += rnd.gauss(0, 0.03)
        price *= math.exp(drift + shock)
        closes.append(price)
    return closes


def backtest(closes, fast: int, slow: int, band: float):
    """Simple dual-SMA momentum with a mean-reversion band — one grid cell."""
    cash, pos = 10_000.0, 0.0
    fsum = ssum = 0.0
    fq, sq = [], []
    trades = 0
    for i, px in enumerate(closes):
        fq.append(px); fsum += px
        if len(fq) > fast: fsum -= fq.pop(0)
        sq.append(px); ssum += px
        if len(sq) > slow: ssum -= sq.pop(0)
        if i < slow:
            continue
        fma, sma = fsum / fast, ssum / slow
        dev = (px - sma) / sma
        if pos == 0.0 and fma > sma and dev < band:
            pos = cash / px * 0.999   # fee
            cash = 0.0
            trades += 1
        elif pos > 0.0 and (fma < sma or dev > band * 3):
            cash = pos * px * 0.999
            pos = 0.0
            trades += 1
    equity = cash + pos * closes[-1]
    return equity, trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly-usd", type=float, default=0.0139,
                    help="hourly price of this machine (Fluence 2vCPU/4GB ≈ $10/mo)")
    ap.add_argument("--bars", type=int, default=500_000)
    ap.add_argument("--grid", type=int, default=96, help="number of parameter combos")
    args = ap.parse_args()

    print("generating synthetic OHLCV …")
    t0 = time.time()
    closes = gen_series(args.bars)
    gen_s = time.time() - t0

    fasts = [8, 13, 21, 34, 55, 89]
    slows = [120, 180, 240, 360]
    bands = [0.005, 0.01, 0.02, 0.04]
    grid = [(f, s, b) for f in fasts for s in slows for b in bands][: args.grid]

    print(f"running {len(grid)}-cell grid over {args.bars:,} bars …")
    t1 = time.time()
    results = [backtest(closes, f, s, b) for f, s, b in grid]
    bt_s = time.time() - t1

    best = max(results, key=lambda r: r[0])
    # deterministic artifact: pure numbers, no host/time — verifiable across machines
    det = [{"fast": f, "slow": sl, "band": b,
            "equity": round(e, 6), "trades": t}
           for (f, sl, b), (e, t) in zip(grid, results)]
    with open("grid_results.json", "w") as fh:
        json.dump(det, fh, sort_keys=True, separators=(",", ":"))
    cells_per_s = len(grid) / bt_s
    cost = (bt_s / 3600.0) * args.hourly_usd

    report = {
        "host": platform.node(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "bars": args.bars,
        "grid_cells": len(grid),
        "gen_seconds": round(gen_s, 2),
        "backtest_seconds": round(bt_s, 2),
        "cells_per_second": round(cells_per_s, 3),
        "best_equity": round(best[0], 2),
        "hourly_usd": args.hourly_usd,
        "grid_cost_usd": round(cost, 6),
        "runs_per_dollar": round(1.0 / cost, 1) if cost else None,
    }
    print(json.dumps(report, indent=2))
    with open("bench_report.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print("\nsaved → bench_report.json")


if __name__ == "__main__":
    main()
