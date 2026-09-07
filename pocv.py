#!/usr/bin/env python3
"""
AIMETA Proof-of-Compute Verifier (pocv) — v0

Independently verifies a pocr receipt:

  1. signature  — ed25519 over the canonical body matches signer_pubkey
  2. integrity  — receipt_hash matches the signed content
  3. (optional) replay — re-run the job locally and compare output hashes;
     for deterministic jobs this proves the recorded output is exactly
     what that command produces.

Usage:
  python3 pocv.py receipt.json            # signature + integrity
  python3 pocv.py receipt.json --replay   # plus deterministic re-run
"""
import argparse, hashlib, json, subprocess, sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt")
    ap.add_argument("--replay", action="store_true")
    args = ap.parse_args()

    receipt = json.load(open(args.receipt))
    body = {k: v for k, v in receipt.items()
            if k not in ("signature", "receipt_hash", "anchor")}

    # 1. signature
    pub = bytes.fromhex(receipt["signer_pubkey"].split(":", 1)[1])
    sig = bytes.fromhex(receipt["signature"].split(":", 1)[1])
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, canonical(body))
        print("✔ signature valid  (ed25519)")
    except InvalidSignature:
        sys.exit("✘ SIGNATURE INVALID — receipt was tampered with")

    # 2. integrity
    check = {**body, "signature": receipt["signature"]}  # anchor excluded
    if sha256_bytes(canonical(check)) == receipt["receipt_hash"]:
        print("✔ receipt_hash consistent")
    else:
        sys.exit("✘ receipt_hash mismatch")

    print(f"  job     : {' '.join(body['job']['cmd'])}")
    print(f"  ran on  : {body['env']['host']} ({body['provider']})")
    print(f"  wall    : {body['run']['wall_seconds']}s · exit {body['run']['exit_code']}")

    # 3. replay
    if args.replay:
        print("replaying job locally …")
        proc = subprocess.run(body["job"]["cmd"], capture_output=True)
        ok = True
        for path, want in body["output"]["files"].items():
            got = sha256_file(path)
            mark = "✔" if got == want else "✘"
            if got != want:
                ok = False
            print(f"  {mark} {path}: {'match' if got == want else 'MISMATCH'}")
        if ok:
            print("✔ replay verified — outputs are bit-identical to the receipt")
        else:
            sys.exit("✘ replay diverged — output does not match the receipt")

    print("\nreceipt verified.")


if __name__ == "__main__":
    main()
