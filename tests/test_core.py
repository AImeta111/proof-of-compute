"""Core invariants of the Proof-of-Compute receipt system."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aimeta_poc.pocbatch import build_tree, h  # noqa: E402


def run(args, cwd, ok=True):
    p = subprocess.run([sys.executable] + args, cwd=cwd,
                       capture_output=True, text=True)
    if ok:
        assert p.returncode == 0, p.stderr + p.stdout
    return p


@pytest.fixture()
def workdir(tmp_path):
    # deterministic toy job: read in.txt, write out.txt
    (tmp_path / "job.py").write_text(
        "data=open('in.txt').read()\n"
        "open('out.txt','w').write(str(sum(ord(c) for c in data)))\n")
    (tmp_path / "in.txt").write_text("aimeta proof of compute")
    return tmp_path


def make_receipt(workdir, name="r.json", key="k1.key"):
    run([os.path.join(ROOT, "pocr.py"),
         "--key", key, "--input", "job.py", "--input", "in.txt",
         "--output", "out.txt", "--provider", "test:unit:local",
         "--receipt", name, "--", sys.executable, "job.py"], cwd=workdir)
    return json.load(open(workdir / name))


def test_receipt_verifies(workdir):
    make_receipt(workdir)
    run([os.path.join(ROOT, "pocv.py"), "r.json", "--replay"], cwd=workdir)


def test_tamper_breaks_signature(workdir):
    r = make_receipt(workdir)
    r["run"]["wall_seconds"] = 0.001          # forge a faster run
    json.dump(r, open(workdir / "r.json", "w"))
    p = run([os.path.join(ROOT, "pocv.py"), "r.json"], cwd=workdir, ok=False)
    assert p.returncode != 0
    assert "INVALID" in (p.stdout + p.stderr)


def test_anchor_metadata_does_not_break_signature(workdir):
    r = make_receipt(workdir)
    r["anchor"] = {"chain": "bsc", "status": "anchored", "tx": "0x" + "ab" * 32}
    json.dump(r, open(workdir / "r.json", "w"))
    run([os.path.join(ROOT, "pocv.py"), "r.json"], cwd=workdir)  # must still pass


def test_determinism_across_runs(workdir):
    r1 = make_receipt(workdir, "r1.json", "k1.key")
    r2 = make_receipt(workdir, "r2.json", "k2.key")
    assert r1["output"]["files"] == r2["output"]["files"]
    assert r1["signer_pubkey"] != r2["signer_pubkey"]


def test_arbitration_corroborates(workdir):
    make_receipt(workdir, "r1.json", "k1.key")
    make_receipt(workdir, "r2.json", "k2.key")
    p = run([os.path.join(ROOT, "pocarb.py"), "r1.json", "r2.json",
             "-o", "v.json"], cwd=workdir)
    v = json.load(open(workdir / "v.json"))
    assert v["verdict"] == "CORROBORATED"
    assert v["independent_signers"] is True


def test_arbitration_detects_divergence(workdir):
    make_receipt(workdir, "r1.json", "k1.key")
    r2 = make_receipt(workdir, "r2.json", "k2.key")
    # forge a diverging output — but signature then breaks, so re-sign is
    # impossible without the key; simulate a dishonest runner with its own key
    (workdir / "in.txt").write_text("tampered input, different output")
    make_receipt(workdir, "r3.json", "k3.key")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "pocarb.py"),
                        "r1.json", "r3.json", "-o", "v.json"],
                       cwd=workdir, capture_output=True, text=True)
    # different input hash ⇒ different job ⇒ refuses to arbitrate
    assert p.returncode != 0


def test_lineage_links_and_breaks(workdir):
    make_receipt(workdir, "parent.json", "k1.key")
    (workdir / "job2.py").write_text(
        "v=open('out.txt').read()\nopen('final.txt','w').write(v[::-1])\n")
    run([os.path.join(ROOT, "pocr.py"), "--key", "k1.key",
         "--input", "job2.py", "--input", "out.txt",
         "--parent", "parent.json", "--output", "final.txt",
         "--provider", "test:unit:local", "--receipt", "child.json",
         "--", sys.executable, "job2.py"], cwd=workdir)
    run([os.path.join(ROOT, "pocv.py"), "child.json",
         "--chain", "parent.json"], cwd=workdir)
    # a parent that produced none of our inputs must be rejected
    p = subprocess.run([sys.executable, os.path.join(ROOT, "pocr.py"),
                        "--key", "k1.key", "--input", "job.py",
                        "--parent", "child.json", "--output", "out.txt",
                        "--provider", "t", "--receipt", "bad.json",
                        "--", sys.executable, "job.py"],
                       cwd=workdir, capture_output=True, text=True)
    assert p.returncode != 0


def test_merkle_tree_proofs():
    leaves = [hashlib.sha256(bytes([i])).digest() for i in range(5)]
    root, proofs = build_tree(leaves)
    for i, leaf in enumerate(leaves):
        node = leaf
        for step in proofs[i]:
            sib = bytes.fromhex(step[0])
            node = h(node + sib) if step[1] else h(sib + node)
        assert node == root, f"leaf {i} proof does not fold to root"
