from __future__ import annotations

import re
from dataclasses import dataclass

try:
    import streamlit as st
except Exception:  # pragma: no cover
    class _NoStreamlit:
        @staticmethod
        def cache_data(ttl: int | None = None):
            def _decorator(fn):
                return fn

            return _decorator

    st = _NoStreamlit()  # type: ignore

from core.net import disable_proxies_for_process


@dataclass(frozen=True)
class StockCandidate:
    market: str  # CN/HK/US
    symbol: str  # normalized symbol (e.g. 600519.SH / 00700 / AAPL)
    name: str | None = None


_A_CN_SUFFIX_RE = re.compile(r"^(\d{6})\.(SH|SZ|BJ)$", re.IGNORECASE)


def _normalize_market(market: str) -> str:
    m = (market or "").strip().upper()
    if m in {"A股", "CN", "A"}:
        return "CN"
    if m in {"港股", "HK"}:
        return "HK"
    if m in {"美股", "US"}:
        return "US"
    return m or "CN"


def normalize_symbol(market: str, raw: str) -> str:
    market = _normalize_market(market)
    s = (raw or "").strip().upper()

    if market == "CN":
        m = _A_CN_SUFFIX_RE.match(s)
        if m:
            return f"{m.group(1)}.{m.group(2).upper()}"
        if re.fullmatch(r"\d{6}", s):
            if s.startswith("6"):
                return f"{s}.SH"
            if s.startswith(("0", "3")):
                return f"{s}.SZ"
            if s.startswith(("8", "4")):
                return f"{s}.BJ"
            return f"{s}.SZ"
        return s

    if market == "HK":
        if re.fullmatch(r"\d{1,5}(\.HK)?", s):
            code = s.replace(".HK", "")
            return f"{code.zfill(5)}.HK"
        return s

    return s


def is_explicit_symbol(market: str, raw: str) -> bool:
    market = _normalize_market(market)
    s = (raw or "").strip().upper()
    if not s:
        return False

    if market == "CN":
        return bool(_A_CN_SUFFIX_RE.match(s) or re.fullmatch(r"\d{6}", s))
    if market == "HK":
        return bool(re.fullmatch(r"\d{1,5}(\.HK)?", s))
    # US
    return bool(re.fullmatch(r"[A-Z.\-]{1,10}", s))


def infer_market(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not s:
        return ""
    if _A_CN_SUFFIX_RE.match(s) or re.fullmatch(r"\d{6}", s):
        return "CN"
    if re.fullmatch(r"\d{1,5}(\.HK)?", s):
        return "HK"
    if re.fullmatch(r"[A-Z.\-]{1,10}", s):
        return "US"
    return ""


def normalize_symbol_auto(raw: str) -> tuple[str, str] | tuple[None, None]:
    market = infer_market(raw)
    if not market:
        return None, None
    if not is_explicit_symbol(market, raw):
        return None, None
    return market, normalize_symbol(market, raw)


@st.cache_data(ttl=24 * 3600)
def _load_cn_universe() -> list[tuple[str, str]]:
    disable_proxies_for_process()
    import akshare as ak

    df = ak.stock_zh_a_spot_em()
    code_col = "代码" if "代码" in df.columns else df.columns[0]
    name_col = "名称" if "名称" in df.columns else df.columns[1]
    return [(str(c).strip(), str(n).strip()) for c, n in zip(df[code_col], df[name_col])]


@st.cache_data(ttl=24 * 3600)
def _load_hk_universe() -> list[tuple[str, str]]:
    disable_proxies_for_process()
    import akshare as ak

    df = ak.stock_hk_spot_em()
    code_col = "代码" if "代码" in df.columns else df.columns[0]
    name_col = "名称" if "名称" in df.columns else df.columns[1]
    return [(str(c).strip(), str(n).strip()) for c, n in zip(df[code_col], df[name_col])]


@st.cache_data(ttl=24 * 3600)
def _load_us_universe() -> list[tuple[str, str]]:
    disable_proxies_for_process()
    import akshare as ak

    df = ak.stock_us_spot_em()
    code_col = "代码" if "代码" in df.columns else df.columns[0]
    name_col = "名称" if "名称" in df.columns else df.columns[1]
    return [(str(c).strip(), str(n).strip()) for c, n in zip(df[code_col], df[name_col])]


def fuzzy_search(market: str, query: str, limit: int = 20) -> list[StockCandidate]:
    market = _normalize_market(market)
    q = (query or "").strip()
    if not q:
        return []

    q_upper = q.upper()

    if market == "CN":
        universe = _load_cn_universe()
        matches = []
        for code, name in universe:
            if q in code or q in name:
                matches.append(StockCandidate(market="CN", symbol=normalize_symbol("CN", code), name=name))
        return matches[:limit]

    if market == "HK":
        universe = _load_hk_universe()
        matches = []
        for code, name in universe:
            if q in code or q in name:
                matches.append(StockCandidate(market="HK", symbol=normalize_symbol("HK", code), name=name))
        return matches[:limit]

    universe = _load_us_universe()
    matches = []
    for code, name in universe:
        if q_upper in code.upper() or q in name:
            matches.append(StockCandidate(market="US", symbol=normalize_symbol("US", code), name=name))
    return matches[:limit]
