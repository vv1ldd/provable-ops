#!/usr/bin/env python3
"""
Проверочные запросы к Точка.API, Яндекс Маркет Partner API и EZ PIN (только stdlib).

Из корня репозитория (с заполненным .env):

  set -a && source .env && set +a
  python3 scripts/ingestion/smoke_fetch.py all

Отдельно: tochka | yandex | ezpaypin

Переменные см. scripts/ingestion/.env.example
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

CTX = ssl.create_default_context()

TOCHKA_TOKEN_URL = "https://enter.tochka.com/connect/token"
TOCHKA_ACCOUNTS_URL = "https://enter.tochka.com/uapi/open-banking/v1.0/accounts"

YANDEX_API_ROOT = "https://api.partner.market.yandex.ru"

EZPAYPIN_BASE = "https://api.ezpaypin.com/vendors/v2"


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=60) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return e.code, raw


def _print_json(label: str, text: str, max_chars: int = 12000) -> None:
    print(f"\n=== {label} ===")
    try:
        data = json.loads(text)
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pretty = text
    if len(pretty) > max_chars:
        pretty = pretty[:max_chars] + f"\n… [{len(pretty) - max_chars} символов обрезано]"
    print(pretty)


def tochka_fetch() -> int:
    token = os.environ.get("TOCHKA_ACCESS_TOKEN", "").strip()
    if not token:
        cid = os.environ.get("TOCHKA_CLIENT_ID", "").strip()
        secret = os.environ.get("TOCHKA_CLIENT_SECRET", "").strip()
        if not cid or not secret:
            print("Tochka: задайте TOCHKA_ACCESS_TOKEN или TOCHKA_CLIENT_ID + TOCHKA_CLIENT_SECRET")
            return 1
        scope = os.environ.get(
            "TOCHKA_SCOPE",
            "ReadAccountsBasic ReadAccountsDetail ReadStatements ReadBalances",
        ).strip()
        form = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": cid,
                "client_secret": secret,
                "scope": scope,
            }
        ).encode("utf-8")
        code, text = _request(
            "POST",
            TOCHKA_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=form,
        )
        if code != 200:
            print(f"Tochka token HTTP {code}:", text[:2000])
            return 1
        try:
            token = json.loads(text)["access_token"]
        except (KeyError, json.JSONDecodeError) as e:
            print("Tochka: неожиданный ответ token:", text[:2000], e)
            return 1
        print("Tochka: OAuth OK (access_token получен).")

    headers = {"Authorization": f"Bearer {token}"}
    cc = os.environ.get("TOCHKA_CUSTOMER_CODE", "").strip()
    if cc:
        headers["Customer-Code"] = cc

    code, text = _request("GET", TOCHKA_ACCOUNTS_URL, headers=headers)
    if code != 200:
        print(f"Tochka accounts HTTP {code}:", text[:4000])
        return 1
    _print_json("Tochka GET /uapi/open-banking/v1.0/accounts", text)
    return 0


def yandex_fetch() -> int:
    key = os.environ.get("YANDEX_MARKET_API_KEY", "").strip()
    bid = os.environ.get("YANDEX_BUSINESS_ID", "").strip()
    if not key or not bid:
        print("Yandex: нужны YANDEX_MARKET_API_KEY и YANDEX_BUSINESS_ID")
        return 1
    end = date.today()
    start = end - timedelta(days=7)
    payload: dict[str, Any] = {
        "dates": {
            "creationDateFrom": start.isoformat(),
            "creationDateTo": end.isoformat(),
        }
    }
    url = f"{YANDEX_API_ROOT}/v1/businesses/{bid}/orders?limit=20"
    body = json.dumps(payload).encode("utf-8")
    code, text = _request(
        "POST",
        url,
        headers={
            "Content-Type": "application/json",
            "Api-Key": key,
        },
        body=body,
    )
    if code != 200:
        print(f"Yandex orders HTTP {code}:", text[:4000])
        return 1
    _print_json("Yandex POST .../businesses/{id}/orders", text)
    return 0


def ezpaypin_token() -> tuple[int, str | None]:
    cid = os.environ.get("EZPAYPIN_CLIENT_ID", "").strip()
    secret = os.environ.get("EZPAYPIN_SECRET_KEY", "").strip()
    if not cid or not secret:
        print("EZ PIN: нужны EZPAYPIN_CLIENT_ID и EZPAYPIN_SECRET_KEY")
        return 1, None
    body = json.dumps({"client_id": cid, "secret_key": secret}).encode("utf-8")
    code, text = _request(
        "POST",
        f"{EZPAYPIN_BASE}/auth/token/",
        headers={"Content-Type": "application/json"},
        body=body,
    )
    if code != 200:
        print(f"EZ PIN token HTTP {code}:", text[:2000])
        return 1, None
    try:
        access = json.loads(text)["access"]
    except (KeyError, json.JSONDecodeError):
        print("EZ PIN: в ответе нет поля access:", text[:2000])
        return 1, None
    print("EZ PIN: токен получен.")
    return 0, access


def ezpaypin_fetch() -> int:
    rc, access = ezpaypin_token()
    if rc != 0 or not access:
        return 1
    auth = {"Authorization": f"Bearer {access}"}

    code, text = _request("GET", f"{EZPAYPIN_BASE}/balance/", headers={**auth})
    if code != 200:
        print(f"EZ PIN balance HTTP {code}:", text[:2000])
        return 1
    _print_json("EZ PIN GET /balance/", text, max_chars=8000)

    code, text = _request("GET", f"{EZPAYPIN_BASE}/orders/?limit=10", headers={**auth})
    if code != 200:
        print(f"EZ PIN orders HTTP {code}:", text[:4000])
        return 1
    _print_json("EZ PIN GET /orders/?limit=10", text, max_chars=12000)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke-запросы к Точка / Яндекс Маркет / EZ PIN")
    p.add_argument(
        "target",
        choices=("tochka", "yandex", "ezpaypin", "all"),
        nargs="?",
        default="all",
    )
    args = p.parse_args()
    targets = ("tochka", "yandex", "ezpaypin") if args.target == "all" else (args.target,)
    exit_code = 0
    for t in targets:
        print(f"\n--- {t} ---")
        if t == "tochka":
            exit_code |= tochka_fetch()
        elif t == "yandex":
            exit_code |= yandex_fetch()
        else:
            exit_code |= ezpaypin_fetch()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
