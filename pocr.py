#!/usr/bin/env python3
"""
AIMETA Proof-of-Compute Runner (pocr) — v0

Wraps any command and produces a signed, independently verifiable
compute receipt:

  * job identity   : command + hashes of the code and input files
  * environment    : machine fingerprint (host, arch, cpu, os, python)
  * execution      : wall time, exit code, started_at (UTC)
  * output identity: hashes of declared output files + stdout
  * signature      : ed25519 over the canonical receipt body

Verification (see pocv.py): re-run the job anywhere → compare output
hashes → check the signature. Deterministic jobs verify bit-for-bit.

Usage:
  python3 pocr.py --key runner.key \
      --input agent_backtest_bench.py \
      --output bench_report.json \
      --provider fluence:cpu-shared-2c-2g:FRA \
      -- python3 agent_backtest_bench.py --bars 500000 --grid 96 --hourly-usd 0.0064

First run generates runner.key (ed25519) if missing.
"""
import argparse, hashlib, json, os, platform, subprocess, sys, time
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives import serialization


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_bytes(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def load_or_create_key(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with open(path, "wb") as f:
        os.chmod(path, 0o600) if os.path.exists(path) else None
        f.write(pem)
    os.chmod(path, 0o600)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="runner.key")
    ap.add_argument("--input", action="append", default=[],
                    help="input file whose hash is committed (repeatable)")
    ap.add_argument("--output", action="append", default=[],
                    help="output file to fingerprint after the run (repeatable)")
    ap.add_argument("--parent", action="append", default=[],
                    help="parent receipt whose output feeds this job's input")
    ap.add_argument("--provider", default="unknown",
                    help="network:instance:region label")
    ap.add_argument("--receipt", default=None, help="receipt path (default auto)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- command to execute")
    args = ap.parse_args()
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        sys.exit("no command given (put it after --)")

    key = load_or_create_key(args.key)
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()

    inputs = {p: sha256_file(p) for p in args.input}

    # lineage: each declared parent must have produced one of our inputs
    parents = []
    for pp in args.parent:
        pr = json.load(open(pp))
        pouts = set(pr.get("output", {}).get("files", {}).values())
        links = [{"file": f, "hash": h} for f, h in inputs.items() if h in pouts]
        if not links:
            sys.exit(f"--parent {pp}: no input of this job matches any output of that receipt")
        parents.append({"parent_receipt_hash": pr["receipt_hash"], "links": links})

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True)
    wall = round(time.time() - t0, 3)

    outputs = {p: sha256_file(p) for p in args.output if os.path.exists(p)}

    body = {
        "schema": "aimeta.poc.v0.3",
        "job": {"cmd": cmd, "inputs": inputs},
        "env": {
            "host": platform.node(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
        },
        "run": {
            "started_at": started,
            "wall_seconds": wall,
            "exit_code": proc.returncode,
        },
        "output": {
            "files": outputs,
            "stdout": sha256_bytes(proc.stdout),
        },
        "provider": args.provider,
        "signer_pubkey": "ed25519:" + pub,
    }
    if parents:
        body["lineage"] = {"parents": parents}
    # signature and receipt_hash cover the body only — the anchor field is
    # post-hoc metadata and must never invalidate the signature
    sig = key.sign(canonical(body)).hex()
    receipt = {**body, "signature": "ed25519:" + sig}
    receipt["receipt_hash"] = sha256_bytes(canonical(receipt))
    receipt["anchor"] = {"chain": "bsc-testnet", "status": "pending"}

    out = args.receipt or f"receipt-{int(t0)}.json"
    with open(out, "w") as f:
        json.dump(receipt, f, indent=2)

    sys.stdout.buffer.write(proc.stdout)
    sys.stderr.buffer.write(proc.stderr)
    print(f"\n[pocr] receipt → {out}")
    print(f"[pocr] receipt_hash: {receipt['receipt_hash']}")
    print(f"[pocr] signer: ed25519:{pub[:16]}…")


if __name__ == "__main__":
    main()
