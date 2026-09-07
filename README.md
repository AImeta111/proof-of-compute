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
- On-chain anchoring of receipt hashes (BSC) ships next; the receipt
  schema already carries the `anchor` field.

## License

MIT — permissionless integration, like everything AIMETA ships.

---

*AIMETA — Make every agent action provable.*
[aimeta.network](https://aimeta.network) · [@AImetalabs](https://x.com/AImetalabs)
