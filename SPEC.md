# AIMETA Proof-of-Compute Receipt Specification

**Schema:** `aimeta.poc.v0.3` · **Status:** draft-for-implementation · **License:** MIT

This document specifies the receipt format so that independent
implementations can produce and verify compatible receipts. Everything
here is implemented by the reference tools in this repository.

## 1 · Envelope

A receipt is a single JSON object with three zones:

| Zone | Fields | Covered by signature? |
|---|---|---|
| **Body** | `schema, job, env, run, output, provider, signer_pubkey, lineage?` | ✔ signed |
| **Seal** | `signature`, `receipt_hash` | derived from body |
| **Metadata** | `anchor` | ✘ post-hoc, never signed |

The `anchor` zone is deliberately outside the signed body: anchoring,
re-anchoring or storage placement MUST NOT invalidate a signature.

## 2 · Canonicalization

All hashing and signing operates on **canonical JSON**: keys sorted
lexicographically at every level, separators `,` and `:` with no
whitespace, UTF-8 encoded. (Equivalent to Python
`json.dumps(obj, sort_keys=True, separators=(",", ":"))`.)

## 3 · Body fields

| Field | Type | Meaning |
|---|---|---|
| `schema` | string | `aimeta.poc.v0.3` |
| `job.cmd` | string[] | argv of the executed command, verbatim. Environment pinning (e.g. a container image digest) belongs **inside** the command so it is part of job identity |
| `job.inputs` | {path → `sha256:<hex>`} | SHA-256 of each committed input file |
| `env` | object | executor fingerprint: `host, machine, cpu_count, os, python` |
| `run` | object | `started_at` (UTC ISO-8601), `wall_seconds`, `exit_code` |
| `output.files` | {path → `sha256:<hex>`} | SHA-256 of each declared output file |
| `output.stdout` | `sha256:<hex>` | hash of captured stdout |
| `provider` | string | `network:instance:region` label, e.g. `fluence:cpu-shared-2c-2g:FRA` |
| `signer_pubkey` | `ed25519:<hex>` | runner's public key (32 bytes, hex) |
| `lineage.parents[]` | object[] | optional; see §5 |

## 4 · Seal

- `signature` = `ed25519:` + hex( Ed25519-sign( canonical(body) ) )
- `receipt_hash` = `sha256:` + hex( SHA-256( canonical(body ∪ {signature}) ) )

Verification order: signature over body → receipt_hash over
body+signature. Any mutation of body or signature breaks verification;
mutation of `anchor` does not.

## 5 · Lineage

A job MAY declare parents. For each parent receipt:

```json
{ "parent_receipt_hash": "sha256:…",
  "links": [ { "file": "<input path>", "hash": "sha256:…" } ] }
```

**Rule:** every `links[].hash` MUST appear among the parent's
`output.files` values, and MUST equal the child's `job.inputs` hash for
that path. A runner MUST refuse to emit a lineage claim that does not
hash-match (reference: `pocr --parent`). Verifiers walk chains with
`pocv --chain`.

## 6 · Corroboration

Independent executors running the identical job (`canonical(job)` equal)
whose `output.files` are identical corroborate each other. An
arbitration verdict (`aimeta.poc.arbitration.v0`) records executors,
signer independence and the boolean outcome, and is itself signed and
hashable — it can be anchored and audited like any receipt. Verdicts:
`CORROBORATED` · `MATCH_SAME_SIGNER` · `DIVERGENT`.

## 7 · Anchoring

Two modes, recorded in `anchor`:

- **single**: a 0-value transaction whose `data` is the 32-byte
  `receipt_hash`.
- **batch (preferred)**: leaves = receipt hashes; parent =
  SHA-256(left‖right); odd levels duplicate the last node. The Merkle
  **root** is anchored; each receipt stores `merkle_root`, `leaf_index`
  and `merkle_path` (sibling + side per level). Cost per receipt is
  O(1/N).

Chains: BSC mainnet (`chain: "bsc"`) and testnet. Example live root:
[`0xf6613c…6d66`](https://bscscan.com/tx/0xf6613c7381183916065fdb5374175c3bac137fde2e78cb144617cca13f5e6d66)
anchoring five receipts on BSC mainnet, block 120507301.

## 8 · Storage

Receipts MAY be persisted to content-addressed storage; `anchor.storage`
records `{network, cid, url, pinned}`. The reference implementation
uses Crust W3Auth IPFS gateways (identity = an Ethereum key signing its
own address).

## 9 · Trust model (honest boundaries)

The signature proves *the runner attested this*; it does not prove the
runner was untampered. Mitigations, in increasing strength:
hermetic execution (network-disabled pinned containers, §3 `job.cmd`) →
cross-executor corroboration (§6) → hardware attestation (TEE; outside
this spec version) → zk proofs (roadmap). Replay verification applies
to deterministic jobs only.

---
*AIMETA — Make every agent action provable. · aimeta.network*
