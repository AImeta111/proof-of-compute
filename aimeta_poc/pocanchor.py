#!/usr/bin/env python3
"""
AIMETA Proof-of-Compute Anchor (pocanchor) — v0

Anchors a receipt hash on BSC TESTNET as a zero-value self-transaction
whose data field is the receipt hash. Updates the receipt's `anchor`
field with the tx hash and a BscScan link.

Usage:  ./.venv/bin/python pocanchor.py receipt-002.json
Key:    ~/.aimeta/bsc-testnet.key  (testnet only — no real value)
"""
import json, os, sys, time
from web3 import Web3
from eth_account import Account

import os as _os
_MAINNET = _os.environ.get("AIMETA_CHAIN", "testnet") == "mainnet"
RPC = "https://bsc-rpc.publicnode.com" if _MAINNET else "https://bsc-testnet-rpc.publicnode.com"
CHAIN_ID = 56 if _MAINNET else 97
CHAIN_NAME = "bsc" if _MAINNET else "bsc-testnet"
EXPLORER = "https://bscscan.com" if _MAINNET else "https://testnet.bscscan.com"

def main():
    path = sys.argv[1]
    receipt = json.load(open(path))
    rhash = receipt["receipt_hash"].split(":", 1)[1]

    w3 = Web3(Web3.HTTPProvider(RPC))
    assert w3.is_connected(), "RPC unreachable"
    acct = Account.from_key(open(os.path.expanduser("~/.aimeta/bsc-testnet.key")).read().strip())
    bal = w3.eth.get_balance(acct.address)
    print(f"anchor wallet {acct.address} · balance {w3.from_wei(bal,'ether')} tBNB")
    if bal == 0:
        sys.exit("wallet unfunded — get free tBNB from the faucet first")

    tx = {
        "to": acct.address,
        "value": 0,
        "data": bytes.fromhex(rhash),
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": CHAIN_ID,
        "gasPrice": w3.eth.gas_price,
    }
    tx["gas"] = w3.eth.estimate_gas(tx)
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
    print("tx sent:", txh, "— waiting for confirmation …")
    rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=120)
    assert rcpt.status == 1, "tx failed"

    receipt["anchor"] = {
        "chain": CHAIN_NAME,
        "status": "anchored",
        "tx": "0x" + txh if not txh.startswith("0x") else txh,
        "block": rcpt.blockNumber,
        "explorer": f"{EXPLORER}/tx/0x{txh.removeprefix('0x')}",
        "anchored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(receipt, open(path, "w"), indent=2)
    print("✔ anchored:", receipt["anchor"]["explorer"])


if __name__ == "__main__":
    main()
