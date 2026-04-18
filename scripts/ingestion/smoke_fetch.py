#!/usr/bin/env python3
"""
Проверочные запросы к Точка.API, Яндекс Маркет Partner API и EZ PIN (только stdlib).

Базовый режим (счета / заказы / баланс):

  set -a && source .env && set +a
  python3 scripts/ingestion/smoke_fetch.py all

Режим «данные для леджера» — выписка Точки, отчёт по платежам Маркета, опционально каталог EZ PIN:

  python3 scripts/ingestion/smoke_fetch.py ledger

Переменные см. scripts/ingestion/.env.example
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

CTX = ssl.create_default_context()

TOCHKA_TOKEN_URL = "https://enter.tochka.com/connect/token"
TOCHKA_ACCOUNTS_URL = "https://enter.tochka.com/uapi/open-banking/v1.0/accounts"
TOCHKA_INIT_STATEMENT_URL = "https://enter.tochka.com/uapi/open-banking/v1.0/statements"

YANDEX_API_ROOT = "https://api.partner.market.yandex.ru"

EZPAYPIN_BASE = "https://api.ezpaypin.com/vendors/v2"

OUT_DIR = Path(__file__).resolve().parent / "out"

# Ответ Get Statement Точки: статус выписки (см. доку «Выписки»).
_STATEMENT_READY = re.compile(r'"status"\s*:\s*"Ready"', re.IGNORECASE)


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=120) as resp:
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


def _parse_int_list(env_name: str) -> list[int]:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return []
    out: list[int] = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        out.append(int(part))
    return out


def _tochka_auth_headers() -> tuple[int, dict[str, str] | None]:
    """Возвращает (0, headers) с Authorization или (1, None)."""
    token = os.environ.get("TOCHKA_ACCESS_TOKEN", "").strip()
    if not token:
        cid = os.environ.get("TOCHKA_CLIENT_ID", "").strip()
        secret = os.environ.get("TOCHKA_CLIENT_SECRET", "").strip()
        if not cid or not secret:
            print("Tochka: задайте TOCHKA_ACCESS_TOKEN или TOCHKA_CLIENT_ID + TOCHKA_CLIENT_SECRET")
            return 1, None
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
            return 1, None
        try:
            token = json.loads(text)["access_token"]
        except (KeyError, json.JSONDecodeError) as e:
            print("Tochka: неожиданный ответ token:", text[:2000], e)
            return 1, None
        print("Tochka: OAuth OK (access_token получен).")

    headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
    cc = os.environ.get("TOCHKA_CUSTOMER_CODE", "").strip()
    if cc:
        headers["Customer-Code"] = cc
    return 0, headers


def tochka_fetch() -> int:
    rc, headers = _tochka_auth_headers()
    if rc != 0 or not headers:
        return 1

    code, text = _request("GET", TOCHKA_ACCOUNTS_URL, headers=headers)
    if code != 200:
        print(f"Tochka accounts HTTP {code}:", text[:4000])
        return 1
    _print_json("Tochka GET /uapi/open-banking/v1.0/accounts", text)
    return 0


def _find_statement_id(data: Any) -> str | None:
    if isinstance(data, dict):
        for k, v in data.items():
            lk = k.lower()
            if lk == "statementid" and isinstance(v, str):
                return v
            r = _find_statement_id(v)
            if r:
                return r
    elif isinstance(data, list):
        for item in data:
            r = _find_statement_id(item)
            if r:
                return r
    return None


def tochka_statement_ledger(headers: dict[str, str]) -> int:
    account_id = os.environ.get("TOCHKA_ACCOUNT_ID", "").strip()
    if not account_id:
        print("Tochka выписка: пропуск (задайте TOCHKA_ACCOUNT_ID из ответа списка счетов).")
        return 0

    end = date.today()
    start = end - timedelta(days=14)
    ds = os.environ.get("TOCHKA_STATEMENT_DATE_FROM", "").strip() or start.isoformat()
    de = os.environ.get("TOCHKA_STATEMENT_DATE_TO", "").strip() or end.isoformat()
    # Точка ожидает date-time; ISO дата → полночь UTC
    start_dt = f"{ds}T00:00:00Z" if "T" not in ds else ds
    end_dt = f"{de}T23:59:59Z" if "T" not in de else de

    custom = os.environ.get("TOCHKA_INIT_STATEMENT_JSON", "").strip()
    if custom:
        body_obj: Any = json.loads(custom)
    else:
        # Типичная обёртка Tochka OpenAPI (при 400 задайте TOCHKA_INIT_STATEMENT_JSON вручную).
        body_obj = {
            "Data": {
                "Statement": {
                    "accountId": account_id,
                    "startDateTime": start_dt,
                    "endDateTime": end_dt,
                }
            }
        }

    body = json.dumps(body_obj).encode("utf-8")
    code, text = _request(
        "POST",
        TOCHKA_INIT_STATEMENT_URL,
        headers={**headers, "Content-Type": "application/json"},
        body=body,
    )
    if code != 200:
        print(f"Tochka Init Statement HTTP {code}:", text[:4000])
        print(
            "Подсказка: скопируйте тело из актуального OpenAPI Init Statement в TOCHKA_INIT_STATEMENT_JSON "
            "(плейсхолдеры accountId/dates подставьте сами)."
        )
        return 1
    _print_json("Tochka POST .../statements (Init)", text, max_chars=6000)
    try:
        sid = _find_statement_id(json.loads(text))
    except json.JSONDecodeError:
        sid = _find_statement_id(text)
    if not sid:
        print("Tochka: в ответе Init не найден statementId — проверьте JSON вручную.")
        return 1

    url = (
        f"https://enter.tochka.com/uapi/open-banking/v1.0/accounts/"
        f"{urllib.parse.quote(account_id, safe='')}/statements/{urllib.parse.quote(sid, safe='')}"
    )
    max_wait = int(os.environ.get("TOCHKA_STATEMENT_POLL_MAX", "30"))
    interval = float(os.environ.get("TOCHKA_STATEMENT_POLL_SEC", "2"))

    for attempt in range(1, max_wait + 1):
        code, st_text = _request("GET", url, headers=headers)
        if code != 200:
            print(f"Tochka Get Statement HTTP {code}:", st_text[:4000])
            return 1
        if _STATEMENT_READY.search(st_text):
            _print_json("Tochka GET statement (Ready)", st_text, max_chars=50000)
            return 0
        print(f"Tochka выписка: ожидание Ready… ({attempt}/{max_wait})")
        time.sleep(interval)

    print("Tochka: выписка не стала Ready за отведённое время — последний ответ:")
    _print_json("Tochka GET statement (последний)", st_text, max_chars=8000)
    return 1


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
    cids = _parse_int_list("YANDEX_CAMPAIGN_IDS")
    if cids:
        payload["campaignIds"] = cids

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


def _yandex_report_poll(key: str, report_id: str) -> tuple[int, str | None]:
    url = f"{YANDEX_API_ROOT}/v2/reports/info/{urllib.parse.quote(report_id, safe='')}"
    max_wait = int(os.environ.get("YANDEX_REPORT_POLL_MAX", "40"))
    interval = float(os.environ.get("YANDEX_REPORT_POLL_SEC", "3"))

    last = ""
    for attempt in range(1, max_wait + 1):
        code, text = _request("GET", url, headers={"Api-Key": key})
        last = text
        if code != 200:
            print(f"Yandex report info HTTP {code}:", text[:4000])
            return 1, None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print("Yandex: не-JSON в report info:", text[:2000])
            return 1, None
        result = data.get("result") or {}
        st = result.get("status")
        if st == "DONE":
            return 0, result.get("file")
        if st == "FAILED":
            _print_json("Yandex GET reports/info (FAILED)", text, max_chars=8000)
            return 1, None
        print(f"Yandex отчёт {report_id}: статус {st} ({attempt}/{max_wait})")
        time.sleep(interval)

    print("Yandex: отчёт не готов за отведённое время, последний ответ:")
    _print_json("Yandex GET reports/info (последний)", last, max_chars=8000)
    return 1, None


def _download_url(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=300) as resp:
            if resp.getcode() != 200:
                print(f"Скачивание HTTP {resp.getcode()}")
                return 1
            data = resp.read()
    except urllib.error.HTTPError as e:
        err = e.read()[:2000]
        print(f"Скачивание HTTP {e.code}:", err.decode("utf-8", errors="replace"))
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"Файл сохранён: {dest} ({len(data)} байт)")
    return 0


def yandex_united_netting_ledger() -> int:
    key = os.environ.get("YANDEX_MARKET_API_KEY", "").strip()
    bid = os.environ.get("YANDEX_BUSINESS_ID", "").strip()
    if not key or not bid:
        print("Yandex united-netting: пропуск (нет ключа или business id).")
        return 0

    end = date.today()
    start = end - timedelta(days=14)
    df = os.environ.get("YANDEX_NETTING_DATE_FROM", "").strip() or start.isoformat()
    dt = os.environ.get("YANDEX_NETTING_DATE_TO", "").strip() or end.isoformat()

    body: dict[str, Any] = {
        "businessId": int(bid),
        "dateFrom": df,
        "dateTo": dt,
    }
    cids = _parse_int_list("YANDEX_CAMPAIGN_IDS")
    if cids:
        body["campaignIds"] = cids

    fmt = os.environ.get("YANDEX_NETTING_FORMAT", "JSON").strip().upper()
    q = urllib.parse.urlencode({"format": fmt, "language": "RU"})
    url = f"{YANDEX_API_ROOT}/v2/reports/united-netting/generate?{q}"

    code, text = _request(
        "POST",
        url,
        headers={"Content-Type": "application/json", "Api-Key": key},
        body=json.dumps(body).encode("utf-8"),
    )
    if code != 200:
        print(f"Yandex united-netting generate HTTP {code}:", text[:4000])
        return 1
    _print_json("Yandex POST united-netting/generate", text, max_chars=4000)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return 1
    if data.get("status") != "OK":
        print("Yandex: ответ generate без status=OK")
        return 1
    report_id = (data.get("result") or {}).get("reportId")
    if not report_id:
        print("Yandex: нет result.reportId")
        return 1

    rc, file_url = _yandex_report_poll(key, str(report_id))
    if rc != 0:
        return rc
    if not file_url:
        print("Yandex: готов, но нет ссылки file — см. JSON выше.")
        return 0

    ext = ".zip" if fmt == "JSON" or fmt == "CSV" else ".xlsx"
    dest = OUT_DIR / f"yandex-united-netting-{report_id}{ext}"
    print(f"Скачивание отчёта ({fmt})…")
    return _download_url(file_url, dest)


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


def ezpaypin_fetch(include_catalog: bool = False) -> int:
    rc, access = ezpaypin_token()
    if rc != 0 or not access:
        return 1
    auth = {"Authorization": f"Bearer {access}"}

    code, text = _request("GET", f"{EZPAYPIN_BASE}/balance/", headers={**auth})
    if code != 200:
        print(f"EZ PIN balance HTTP {code}:", text[:2000])
        return 1
    _print_json("EZ PIN GET /balance/", text, max_chars=8000)

    if include_catalog:
        code, text = _request("GET", f"{EZPAYPIN_BASE}/catalogs/", headers={**auth})
        if code != 200:
            print(f"EZ PIN catalogs HTTP {code}:", text[:2000])
            return 1
        _print_json("EZ PIN GET /catalogs/", text, max_chars=15000)

    code, text = _request("GET", f"{EZPAYPIN_BASE}/orders/?limit=10", headers={**auth})
    if code != 200:
        print(f"EZ PIN orders HTTP {code}:", text[:4000])
        return 1
    _print_json("EZ PIN GET /orders/?limit=10", text, max_chars=12000)
    return 0


def ledger_fetch() -> int:
    exit_code = 0

    print("\n--- tochka (счета + выписка) ---")
    rc, headers = _tochka_auth_headers()
    exit_code |= rc
    if headers:
        code, text = _request("GET", TOCHKA_ACCOUNTS_URL, headers=headers)
        if code != 200:
            print(f"Tochka accounts HTTP {code}:", text[:4000])
            exit_code |= 1
        else:
            _print_json("Tochka GET /uapi/open-banking/v1.0/accounts", text)
        exit_code |= tochka_statement_ledger(headers)

    print("\n--- yandex (заказы + united-netting) ---")
    exit_code |= yandex_fetch()
    if os.environ.get("YANDEX_SKIP_UNITED_NETTING", "").strip() != "1":
        exit_code |= yandex_united_netting_ledger()
    else:
        print("Yandex united-netting: пропуск (YANDEX_SKIP_UNITED_NETTING=1).")

    print("\n--- ezpaypin ---")
    cat = os.environ.get("EZPAYPIN_FETCH_CATALOG", "").strip() == "1"
    exit_code |= ezpaypin_fetch(include_catalog=cat)

    return exit_code


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke / ledger: Точка, Яндекс Маркет, EZ PIN")
    p.add_argument(
        "target",
        choices=("tochka", "yandex", "ezpaypin", "all", "ledger"),
        nargs="?",
        default="all",
    )
    args = p.parse_args()

    if args.target == "ledger":
        return ledger_fetch()

    targets = ("tochka", "yandex", "ezpaypin") if args.target == "all" else (args.target,)
    exit_code = 0
    for t in targets:
        print(f"\n--- {t} ---")
        if t == "tochka":
            exit_code |= tochka_fetch()
        elif t == "yandex":
            exit_code |= yandex_fetch()
        else:
            exit_code |= ezpaypin_fetch(include_catalog=False)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
