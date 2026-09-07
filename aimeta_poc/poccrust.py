#!/usr/bin/env python3
"""
AIMETA Proof-of-Compute × Crust Storage (poccrust) — v0.2

Stores a receipt on Crust Network via the W3Auth IPFS gateway:
identity = an Ethereum key signing its own address (Crust's Web3-auth
scheme — no account, no API key). Then requests pinning via Crust's
IPFS Pinning Service API so the network persists it.

The receipt's `anchor` gains a `storage` section: {network, cid, url}.
Compute proof anchored on BSC + receipt body persisted on Crust —
both AIMETA storage partners carrying the compute story.

Usage:  poccrust.py receipt.json [more.json …]
"""
import base64, json, os, sys
import urllib.request


GATEWAYS = [
    "https://gw.crustfiles.app",
    "https://crustipfs.xyz",
    "https://gw.w3ipfs.org.cn",
]
PIN_ENDPOINT = "https://pin.crustcode.com/psa/pins"


def auth_header():
    acct = Account.from_key(
        open(os.path.expanduser("~/.aimeta/bsc-testnet.key")).read().strip())
    sig = Account.sign_message(
        encode_defunct(text=acct.address), acct.key).signature.hex()
    token = f"eth-{acct.address}:0x{sig.removeprefix('0x')}"
    return "Basic " + base64.b64encode(token.encode()).decode()


def upload(path, auth):
    data = open(path, "rb").read()
    boundary = "----aimetapoc"
    body = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
            f"Content-Type: application/json\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    last_err = None
    for gw in GATEWAYS:
        try:
            req = urllib.request.Request(
                gw + "/api/v0/add?pin=true", data=body, method="POST",
                headers={"Authorization": auth,
                         "Content-Type": f"multipart/form-data; boundary={boundary}"})
            resp = json.loads(urllib.request.urlopen(req, timeout=45).read())
            return resp["Hash"], gw
        except Exception as e:
            last_err = f"{gw}: {e}"
            print(f"  · gateway failed — {last_err}", file=sys.stderr)
    raise RuntimeError(f"all gateways failed; last: {last_err}")


def pin(cid, name, auth):
    req = urllib.request.Request(
        PIN_ENDPOINT, data=json.dumps({"cid": cid, "name": name}).encode(),
        method="POST",
        headers={"Authorization": auth, "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=45)
        return True
    except Exception as e:
        print(f"  · pinning service: {e} (file still on gateway IPFS)", file=sys.stderr)
        return False


def main():
    from eth_account import Account
    from eth_account.messages import encode_defunct
    auth = auth_header()
    for path in sys.argv[1:]:
        receipt = json.load(open(path))
        cid, gw = upload(path, auth)
        pinned = pin(cid, os.path.basename(path), auth)
        receipt.setdefault("anchor", {})["storage"] = {
            "network": "crust", "cid": cid,
            "pinned": pinned,
            "url": f"{gw}/ipfs/{cid}",
        }
        json.dump(receipt, open(path, "w"), indent=2)
        print(f"✔ {path} → ipfs://{cid}  (crust pin {'requested' if pinned else 'pending'})")


if __name__ == "__main__":
    main()
