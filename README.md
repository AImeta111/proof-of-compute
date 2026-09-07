# AIMETA · Proof of Compute (v0)

**Signed, independently verifiable receipts for compute jobs.**
Part of the [AIMETA](https://aimeta.network) verifiable AI-agent network — this is the smallest real slice of our Proof-of-Compute layer, running today on decentralized compute.

> Cheap decentralized compute all faces the same diligence question:
> *how do I know the job really ran — and ran honestly?*
> A receipt you can re-verify is the answer a hash alone can't give.

## What it does

`pocr.py` wraps **any command** and emits a receipt containing:

- **job identity** — the command + SHA-256 of code and input files
- **environment** — machine fingerprint (host, arch, CPUs, OS, Python)
- **execution** — UTC start, wall time, exit code
- **output identity** — SHA-256 of declared output files and stdout
- **ed25519 signature** over the canonical receipt body

`pocv.py` verifies a receipt anywhere:

1. **signature** — the receipt wasn't tampered with
2. **integrity** — the receipt hash matches the signed content
3. **replay** (`--replay`) — re-run the job locally and compare output
   hashes; deterministic jobs verify **bit-for-bit**

## Verified in production

The example receipt in [`examples/`](examples/) was produced on a
**Fluence** cloudless VM (x86-64, Frankfurt) and independently verified
on an Apple-silicon laptop (arm64):

```
✔ signature valid  (ed25519)
✔ receipt_hash consistent
  job     : python3 agent_backtest_bench.py --bars 500000 --grid 96 …
  ran on  : fluence (fluence:cpu-shared-2c-2g:FRA)
replaying job locally …
  ✔ grid_results.json: match
✔ replay verified — outputs are bit-identical to the receipt
```

Same job, different silicon, identical bits. That is the property the
AIMETA proof stack anchors.

## Quick start

```bash
pip install cryptography

# run a job under receipt
python3 pocr.py --key runner.key \
    --input my_job.py --output result.json \
    --provider fluence:cpu-shared-2c-2g:FRA \
    -- python3 my_job.py

# verify it anywhere
python3 pocv.py receipt-*.json --replay
```

`agent_backtest_bench.py` is the deterministic demo workload used in the
example (synthetic OHLCV, 96-cell strategy grid — pure stdlib).

## Honest boundaries (v0)

- The signature proves the **runner** attested the job — it does not yet
  prove the runner itself was untampered. Hardware attestation (TEE) is
  the next layer of the AIMETA proof stack, not this repo.
- `--replay` proves output identity for **deterministic** jobs only.
- Receipt hashes anchor on BSC testnet — the example receipt's hash is
  anchored at [`0xfb5a…4108`](https://testnet.bscscan.com/tx/0xfb5a919b991a5fe7dd96a60c73ebeb9d8e618e7e1c2326863db81abf56044108)
  (block 129637842): compare the tx `data` field with `receipt_hash`.


## v0.2 — shipped

- **Merkle batch anchoring** (`pocbatch.py`) — thousands of receipts, one
  on-chain tx; every receipt carries its inclusion proof. Live root:
  [`0x4c7c…d097`](https://testnet.bscscan.com/tx/0x4c7ccb0c5122540bb07cad37ca35c8d2357db7cd02deba332699a7efe7bed097)
- **Corroboration** (`pocarb.py`) — the same job executed by independent
  parties, receipts cross-checked. Example verdict in `examples/`:
  Fluence x86-64 and Apple arm64, independent keys, identical outputs →
  **CORROBORATED**. Trusting the result no longer requires trusting any
  single runner.
- **Environment pinning** — jobs run against an exact image digest
  (`python@sha256:…` inside the signed command), so "what code, in what
  environment" is part of the receipt (`examples/receipt-vm-docker.json`).
- **Storage on Crust** (`poccrust.py`) — receipts persisted to IPFS via
  Crust W3Auth gateways, CID recorded in the receipt (network pinning
  marked `pending` until confirmed — status is honest, like everything here).
- **Receipt Explorer** — verify any receipt in the browser at
  [aimeta.network/verify](https://aimeta.network/verify): signature,
  integrity, anchor and CID, checked entirely client-side.
- **Envelope fix** — `anchor` moved outside the signed body: post-hoc
  anchoring metadata can never invalidate a signature (schema `v0.2`).


## v0.3 — shipped

- **Hermetic execution** — jobs run in a network-disabled pinned container
  (`docker run --network=none … python@sha256:…`, inside the signed command):
  the output is provably a function of the committed inputs alone.
- **Receipt lineage** (`--parent`) — a job declares the receipts whose outputs
  feed its inputs; hashes must match, verifiers can walk the chain
  (`pocv --chain`). Compute pipelines become provenance DAGs
  (`examples/receipt-stage2.json`).
- **Automated cross-cloud corroboration** — a GitHub Actions executor re-runs
  the benchmark every 6 h and arbitrates against the Fluence receipt; the
  standing verdict lives in [`live/`](live/): **CORROBORATED**, independent
  keys, identical bits.
- **Continuous audit** — a scheduled workflow re-verifies every live receipt
  (signature, integrity, replay where runnable) and publishes
  `live/audit-latest.json`. The system spot-checks itself in public.

## License

MIT — permissionless integration, like everything AIMETA ships.

---

*AIMETA — Make every agent action provable.*
[aimeta.network](https://aimeta.network) · [@AImetalabs](https://x.com/AImetalabs)
