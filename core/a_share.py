from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from core.net import disable_proxies_for_process


@dataclass(frozen=True)
class AShareFinancials:
    profit: pd.DataFrame
    balance: pd.DataFrame
    cash: pd.DataFrame


def to_akshare_symbol(symbol_cn: str) -> str:
    """Convert normalized CN symbol like 600519.SH into AkShare symbol like SH600519."""
    s = (symbol_cn or "").strip().upper()
    if "." not in s:
        raise ValueError(f"CN symbol must include suffix, got: {symbol_cn}")
    code, suffix = s.split(".", 1)
    suffix = suffix.upper()
    if suffix not in {"SH", "SZ", "BJ"}:
        raise ValueError(f"Unsupported CN suffix: {suffix}")
    return f"{suffix}{code}"


def fetch_a_share_financials(symbol_cn: str) -> AShareFinancials:
    disable_proxies_for_process()
    import akshare as ak

    ak_symbol = to_akshare_symbol(symbol_cn)
    profit = ak.stock_profit_sheet_by_report_em(ak_symbol)
    balance = ak.stock_balance_sheet_by_report_em(ak_symbol)
    cash = ak.stock_cash_flow_sheet_by_report_em(ak_symbol)
    return AShareFinancials(profit=profit, balance=balance, cash=cash)


def row_payload(row: pd.Series, keep_cols: list[str]) -> str:
    payload = {k: (None if pd.isna(row.get(k)) else row.get(k)) for k in keep_cols if k in row.index}
    return json.dumps(payload, ensure_ascii=False, default=str)
