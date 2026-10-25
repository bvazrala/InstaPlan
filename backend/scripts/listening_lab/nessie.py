"""Capital One Nessie sandbox, proxied through the lab server so the key never reaches the browser.

Once the group confirms a plan, the person who started it enters the cost and everyone who voted yes pays
their share. Nessie's current transfers have no payee, so a payment is a withdrawal from the payer's account
plus a deposit into the payee's, both in whole dollars (the sandbox stores integer amounts). Each simulator user gets one Nessie customer and checking account,
created on first use and remembered in .cache/nessie.json so reruns reuse them.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from threading import Lock

from .settings import env

NAME = "NESSIE_API_KEY"
CACHE = Path(__file__).parent / ".cache" / "nessie.json"
STARTING_BALANCE = 1500
_lock = Lock()


def configured() -> bool:
    return bool(env(NAME))


def _base() -> str:
    return (env("NESSIE_BASE_URL") or "https://prod-api.nessieisreal.com").rstrip("/")


def _call(method: str, path: str, body: dict | None = None) -> dict | list:
    key = env(NAME)
    if not key:
        raise RuntimeError(f"{NAME} is missing; payments are unavailable")
    url = f"{_base()}{path}?{urllib.parse.urlencode({'key': key})}"
    request = urllib.request.Request(url, method=method, headers={"Content-Type": "application/json"},
                                     data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:600]
        raise RuntimeError(f"Nessie returned {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Can't reach Nessie: {getattr(exc, 'reason', exc)}") from None


def _created(payload: dict | list) -> dict:
    """Nessie wraps new objects as {"objectCreated": {...}}."""
    return payload.get("objectCreated", payload) if isinstance(payload, dict) else {}


def accounts(users: list[dict]) -> dict[str, str]:
    """Simulator user id → Nessie account id, creating customers and accounts the first time."""
    with _lock:
        known = json.loads(CACHE.read_text()) if CACHE.is_file() else {}
        changed = False
        for person in users:
            if person["id"] in known:
                continue
            customer = _created(_call("POST", "/customers", {
                "first_name": "Jordan" if person["name"] == "You" else person["name"], "last_name": "InstaPlan",
                "address": {"street_number": "2317", "street_name": "Speedway", "city": "Austin", "state": "TX", "zip": "78712"},
            }))
            account = _created(_call("POST", f"/customers/{customer['_id']}/accounts", {
                "type": "Checking", "nickname": "InstaPlan demo", "rewards": 0, "balance": STARTING_BALANCE,
            }))
            known[person["id"]] = account["_id"]
            changed = True
        if changed:
            CACHE.parent.mkdir(exist_ok=True)
            CACHE.write_text(json.dumps(known))
        return {uid: known[uid] for uid in (p["id"] for p in users) if uid in known}


def balance(account_id: str) -> float:
    payload = _call("GET", f"/accounts/{account_id}")
    return float(payload.get("balance", 0)) if isinstance(payload, dict) else 0.0


def _post_money(path: str, body: dict) -> dict:
    """Creates a withdrawal or deposit. The sandbox's schema has shifted over time, so adapt once to what it rejects."""
    body = dict(body)
    for _ in range(3):
        try:
            return _created(_call("POST", path, body))
        except RuntimeError as exc:
            text = str(exc)
            if "medium" in text and "medium" in body and ("not permitted" in text or "extra" in text):
                body.pop("medium")
            elif "status" in text and body.get("status") == "completed":
                body["status"] = "pending"
            else:
                raise
    return _created(_call("POST", path, body))


def transfer(from_account: str, to_account: str, amount: float, description: str) -> dict:
    """Moves whole dollars: a withdrawal from the payer and a deposit to the payee. Returns both Nessie ids."""
    body = {"medium": "balance", "transaction_date": date.today().isoformat(), "status": "completed",
            "amount": int(round(amount)), "description": description[:120]}
    withdrawal = _post_money(f"/accounts/{from_account}/withdrawals", body)
    deposit = _post_money(f"/accounts/{to_account}/deposits", body)
    return {"id": withdrawal.get("_id", ""), "deposit_id": deposit.get("_id", ""),
            "status": withdrawal.get("status", body["status"])}
