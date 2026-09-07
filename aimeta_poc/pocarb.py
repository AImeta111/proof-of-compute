#!/usr/bin/env python3
"""
AIMETA Proof-of-Compute Arbitration (pocarb) — v0.2

Trust through redundancy: the same job executed by INDEPENDENT parties,
receipts cross-checked. If N independent executors produce identical
output hashes, trusting the result no longer requires trusting any
single runner — the receipts corroborate each other.

Takes ≥2 receipts for the same job, verifies each signature, compares
output hashes, and emits a signed arbitration verdict (which can itself
be anchored on-chain like any receipt).

Usage:  pocarb.py receipt_a.json receipt_b.json [-o verdict.json]
"""
import argparse, hashlib, json, sys, time

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey, Ed25519PrivateKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def check_sig(r):
    body = {k: v for k, v in r.items() if k not in ("signature", "receipt_hash", "anchor")}
    pub = bytes.fromhex(r["signer_pubkey"].split(":", 1)[1])
    sig = bytes.fromhex(r["signature"].split(":", 1)[1])
    Ed25519PublicKey.from_public_bytes(pub).verify(sig, canonical(body))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("receipts", nargs="+")
    ap.add_argument("-o", "--out", default="verdict.json")
    ap.add_argument("--key", default="arbiter.key")
    args = ap.parse_args()
    if len(args.receipts) < 2:
        sys.exit("need ≥2 receipts")

    rs = [json.load(open(p)) for p in args.receipts]

    # 1. each receipt must be validly signed
    for p, r in zip(args.receipts, rs):
        try:
            check_sig(r)
            print(f"✔ {p}: signature valid ({r['provider']})")
        except InvalidSignature:
            sys.exit(f"✘ {p}: INVALID SIGNATURE")

    # 2. same job?
    jobs = {canonical(r["job"]).decode() for r in rs}
    if len(jobs) != 1:
        sys.exit("✘ receipts are for different jobs — nothing to arbitrate")

    # 3. independent signers?
    signers = [r["signer_pubkey"] for r in rs]
    independent = len(set(signers)) == len(signers)

    # 4. compare deterministic outputs
    outs = [canonical(r["output"]["files"]).decode() for r in rs]
    agree = len(set(outs)) == 1

    verdict_body = {
        "schema": "aimeta.poc.arbitration.v0",
        "job": rs[0]["job"],
        "executors": [
            {"provider": r["provider"], "signer": r["signer_pubkey"],
             "receipt_hash": r["receipt_hash"], "env": r["env"]["machine"]}
            for r in rs
        ],
        "independent_signers": independent,
        "outputs_identical": agree,
        "verdict": "CORROBORATED" if (agree and independent) else
                   ("MATCH_SAME_SIGNER" if agree else "DIVERGENT"),
        "arbitrated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # sign the verdict
    import os
    if os.path.exists(args.key):
        key = serialization.load_pem_private_key(open(args.key, "rb").read(), password=None)
    else:
        key = Ed25519PrivateKey.generate()
        open(args.key, "wb").write(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        os.chmod(args.key, 0o600)
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    verdict_body["arbiter_pubkey"] = "ed25519:" + pub
    sig = key.sign(canonical(verdict_body)).hex()
    verdict = {**verdict_body, "signature": "ed25519:" + sig}
    verdict["receipt_hash"] = sha256_bytes(canonical(verdict))

    json.dump(verdict, open(args.out, "w"), indent=2)
    print(f"\nverdict: {verdict['verdict']}")
    print(f"  executors: {', '.join(r['provider'] for r in rs)}")
    print(f"  saved → {args.out}  (hash {verdict['receipt_hash'][:23]}…)")


if __name__ == "__main__":
    main()
