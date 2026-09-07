#!/usr/bin/env python3
"""
AIMETA Proof-of-Compute Batch Anchor (pocbatch) — v0.2

Anchors MANY receipts in ONE on-chain transaction:
  * builds a SHA-256 Merkle tree over receipt hashes
  * anchors only the Merkle root on BSC testnet
  * writes each receipt's inclusion proof (path + index) back into it

Verification: recompute receipt_hash → fold up the Merkle path → compare
with the root in the anchored tx's data field. Cost per receipt → ~zero.

Usage:  pocbatch.py receipt1.json receipt2.json …
"""
import hashlib, json, os, sys, time
from web3 import Web3
from eth_account import Account

import os as _os
_MAINNET = _os.environ.get("AIMETA_CHAIN", "testnet") == "mainnet"
RPC = "https://bsc-rpc.publicnode.com" if _MAINNET else "https://bsc-testnet-rpc.publicnode.com"
CHAIN_ID = 56 if _MAINNET else 97
CHAIN_NAME = "bsc" if _MAINNET else "bsc-testnet"
EXPLORER = "https://bscscan.com" if _MAINNET else "https://testnet.bscscan.com"


def h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def build_tree(leaves):
    """Returns (root, proofs) — proofs[i] = list of (sibling_hex, is_right)."""
    level = leaves[:]
    proofs = [[] for _ in leaves]
    idx = list(range(len(leaves)))
    while len(level) > 1:
        if len(level) % 2:                       # duplicate last on odd levels
            level.append(level[-1])
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(h(level[i] + level[i + 1]))
        for j, leaf_pos in enumerate(idx):
            pos = leaf_pos
            sib = pos ^ 1
            proofs[j].append((level[sib].hex(), pos % 2 == 0))
            idx[j] = pos // 2
        level = nxt
    return level[0], proofs


def main():
    paths = sys.argv[1:]
    if len(paths) < 2:
        sys.exit("give ≥2 receipts")
    receipts = [json.load(open(p)) for p in paths]
    leaves = [bytes.fromhex(r["receipt_hash"].split(":")[1]) for r in receipts]
    root, proofs = build_tree(leaves)
    print(f"merkle root over {len(leaves)} receipts: {root.hex()}")

    w3 = Web3(Web3.HTTPProvider(RPC))
    acct = Account.from_key(open(os.path.expanduser("~/.aimeta/bsc-testnet.key")).read().strip())
    tx = {"to": acct.address, "value": 0, "data": root,
          "nonce": w3.eth.get_transaction_count(acct.address),
          "chainId": CHAIN_ID, "gasPrice": w3.eth.gas_price}
    tx["gas"] = w3.eth.estimate_gas(tx)
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
    rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=120)
    assert rcpt.status == 1
    txh = "0x" + txh.removeprefix("0x")
    print("root anchored:", f"{EXPLORER}/tx/{txh}")

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for p, r, proof, i in zip(paths, receipts, proofs, range(len(receipts))):
        r["anchor"] = {
            "chain": CHAIN_NAME, "status": "anchored-batch",
            "merkle_root": root.hex(), "leaf_index": i,
            "merkle_path": [{"sibling": s, "leaf_was_left": l} for s, l in proof],
            "tx": txh, "block": rcpt.blockNumber,
            "explorer": f"{EXPLORER}/tx/{txh}",
            "anchored_at": stamp,
        }
        json.dump(r, open(p, "w"), indent=2)
        print(f"  ✔ {p} ← inclusion proof (leaf {i})")


if __name__ == "__main__":
    main()
