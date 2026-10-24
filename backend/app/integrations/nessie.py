"""Capital One Nessie sandbox: accounts and bills for budget ceilings (R11), transfers for settle up (R17).
The API key goes in the `key` query parameter; it stays on this server."""

from datetime import date
from typing import Any

import httpx

from app.config import get_settings


def _client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(base_url=s.nessie_base_url, params={"key": s.nessie_api_key}, timeout=10)


def _get(path: str) -> Any:
    with _client() as c:
        res = c.get(path)
        res.raise_for_status()
        return res.json()


def _post(path: str, body: dict[str, Any]) -> Any:
    with _client() as c:
        res = c.post(path, json=body)
        res.raise_for_status()
        return res.json()


def accounts(customer_id: str) -> list[dict[str, Any]]:
    return _get(f"/customers/{customer_id}/accounts")


def bills(account_id: str) -> list[dict[str, Any]]:
    return _get(f"/accounts/{account_id}/bills")


def transfer(from_account_id: str, to_account_id: str, amount: float, description: str) -> dict[str, Any]:
    return _post(f"/accounts/{from_account_id}/transfers", {
        "medium": "balance", "payee_id": to_account_id, "amount": round(amount, 2),
        "transaction_date": date.today().isoformat(), "description": description,
    })


# Used by scripts/seed_demo.py
def create_customer(first: str, last: str) -> dict[str, Any]:
    return _post("/customers", {
        "first_name": first, "last_name": last,
        "address": {"street_number": "1", "street_name": "Speedway", "city": "Austin", "state": "TX", "zip": "78712"},
    })


def create_account(customer_id: str, balance: int, nickname: str = "Checking") -> dict[str, Any]:
    return _post(f"/customers/{customer_id}/accounts", {
        "type": "Checking", "nickname": nickname, "rewards": 0, "balance": balance,
    })


def create_bill(account_id: str, payee: str, amount: float, payment_date: str) -> dict[str, Any]:
    return _post(f"/accounts/{account_id}/bills", {
        "status": "pending", "payee": payee, "nickname": payee, "payment_date": payment_date, "payment_amount": amount,
    })
