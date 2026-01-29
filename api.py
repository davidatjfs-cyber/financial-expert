"""
FastAPI backend for the Financial Analyzer frontend.
Run with: uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import date
from typing import Optional
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select

from core.db import session_scope
from core.models import Alert, Company, ComputedMetric, Report, Statement, StatementItem
from core.repository import (
    list_reports,
    get_report,
    upsert_company,
    delete_report_children,
    upsert_report_market_fetch,
    upsert_report_file_upload,
)
from core.schema import init_db
from core.uploads import save_uploaded_file
from core.pipeline import ingest_and_analyze_a_share
from core.stock_search import normalize_symbol
from core.net import disable_proxies_for_process

# Initialize database
init_db()

app = FastAPI(title="Financial Analyzer API", version="1.0.0")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.71.102:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class StatsResponse(BaseModel):
    total: int
    done: int
    risks: int
    rate: int


class ReportResponse(BaseModel):
    id: str
    report_name: str
    source_type: str
    period_type: str
    period_end: str
    status: str
    created_at: int
    updated_at: int


class ReportDetailResponse(BaseModel):
    id: str
    report_name: str
    source_type: str
    period_type: str
    period_end: str
    status: str
    error_message: Optional[str]
    created_at: int
    updated_at: int
    company_id: Optional[str]
    market: Optional[str]


class MetricResponse(BaseModel):
    metric_code: str
    metric_name: str
    value: Optional[float]
    unit: Optional[str]
    period_end: str


class AlertResponse(BaseModel):
    id: str
    alert_code: str
    level: str
    title: str
    message: str
    period_end: str


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    market: str


class CreateReportRequest(BaseModel):
    company_name: str
    period_type: str
    period_end: str


# ============ API Endpoints ============

@app.get("/")
def root():
    return {"message": "Financial Analyzer API", "version": "1.0.0"}


@app.get("/api/stats", response_model=StatsResponse)
def get_stats():
    """Get dashboard statistics."""
    with session_scope() as s:
        total = s.execute(select(func.count(Report.id))).scalar() or 0
        done = s.execute(select(func.count(Report.id)).where(Report.status == "done")).scalar() or 0
        risks = s.execute(select(func.count(func.distinct(Alert.report_id))).where(Alert.level == "high")).scalar() or 0
        rate = int(done / total * 100) if total > 0 else 0
    return StatsResponse(total=total, done=done, risks=risks, rate=rate)


@app.get("/api/reports", response_model=list[ReportResponse])
def get_reports(limit: int = 50, status: Optional[str] = None):
    """Get list of reports."""
    def _decode_report_name(name: str) -> str:
        try:
            if name and "%" in name:
                return unquote(name)
        except Exception:
            pass
        return name

    reports = list_reports(limit=limit)
    if status:
        reports = [r for r in reports if r.status == status]
    return [
        ReportResponse(
            id=r.id,
            report_name=_decode_report_name(r.report_name),
            source_type=r.source_type,
            period_type=r.period_type,
            period_end=r.period_end,
            status=r.status,
            created_at=getattr(r, "created_at", r.updated_at),
            updated_at=r.updated_at,
        )
        for r in reports
    ]


@app.get("/api/reports/{report_id}", response_model=ReportDetailResponse)
def get_report_detail(report_id: str):
    """Get report details."""
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report_name = report.report_name
    try:
        if report_name and "%" in report_name:
            report_name = unquote(report_name)
    except Exception:
        pass

    return ReportDetailResponse(
        id=report.id,
        report_name=report_name,
        source_type=report.source_type,
        period_type=report.period_type,
        period_end=report.period_end,
        status=report.status,
        error_message=report.error_message,
        created_at=report.created_at,
        updated_at=report.updated_at,
        company_id=report.company_id,
        market=report.market,
    )


@app.get("/api/reports/{report_id}/metrics", response_model=list[MetricResponse])
def get_report_metrics(report_id: str):
    """Get computed metrics for a report."""
    with session_scope() as s:
        stmt = select(ComputedMetric).where(ComputedMetric.report_id == report_id)
        metrics = s.execute(stmt).scalars().all()
        return [
            MetricResponse(
                metric_code=m.metric_code,
                metric_name=m.metric_name,
                value=m.value,
                unit=m.unit,
                period_end=m.period_end,
            )
            for m in metrics
        ]


@app.get("/api/reports/{report_id}/alerts", response_model=list[AlertResponse])
def get_report_alerts(report_id: str):
    """Get alerts for a report."""
    with session_scope() as s:
        stmt = select(Alert).where(Alert.report_id == report_id)
        alerts = s.execute(stmt).scalars().all()
        return [
            AlertResponse(
                id=a.id,
                alert_code=a.alert_code,
                level=a.level,
                title=a.title,
                message=a.message,
                period_end=a.period_end,
            )
            for a in alerts
        ]


@app.get("/api/alerts", response_model=list[AlertResponse])
def get_all_alerts(level: Optional[str] = None, limit: int = 50):
    """Get all alerts, optionally filtered by level."""
    with session_scope() as s:
        stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if level:
            stmt = stmt.where(Alert.level == level)
        alerts = s.execute(stmt).scalars().all()
        return [
            AlertResponse(
                id=a.id,
                alert_code=a.alert_code,
                level=a.level,
                title=a.title,
                message=a.message,
                period_end=a.period_end,
            )
            for a in alerts
        ]


@app.get("/api/alerts/summary")
def get_alerts_summary():
    """Get alerts summary by level."""
    with session_scope() as s:
        high = s.execute(select(func.count(Alert.id)).where(Alert.level == "high")).scalar() or 0
        medium = s.execute(select(func.count(Alert.id)).where(Alert.level == "medium")).scalar() or 0
        low = s.execute(select(func.count(Alert.id)).where(Alert.level == "low")).scalar() or 0
    return {"high": high, "medium": medium, "low": low}


def _get_stock_spot_data(market: str):
    """Get real-time stock data from akshare."""
    try:
        market = (market or "CN").upper()
        disable_proxies_for_process()
        import akshare as ak
        
        if market == "CN":
            return ak.stock_zh_a_spot_em()
        elif market == "HK":
            return ak.stock_hk_spot_em()
        elif market == "US":
            return ak.stock_us_spot_em()
        return None
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return None


def _tencent_quote_code(symbol: str, market: str) -> str | None:
    import re

    s = (symbol or "").strip().upper()
    m = (market or "").strip().upper()
    if m == "CN":
        if "." in s:
            code, suffix = s.split(".", 1)
            suffix = suffix.upper()
            if suffix == "SH":
                return f"sh{code}"
            if suffix == "SZ":
                return f"sz{code}"
            if suffix == "BJ":
                return f"bj{code}"
        if s.isdigit() and len(s) == 6:
            return f"sh{s}" if s.startswith("6") else f"sz{s}"
        return None
    if m == "HK":
        code = s.replace(".HK", "")
        if code.isdigit():
            return f"hk{code.zfill(5)}"
        return None
    if m == "US":
        base = s.split(".", 1)[0]
        if re.fullmatch(r"[A-Z.\-]{1,10}", base):
            return f"us{base}"
        return None
    return None


def _tencent_fetch_quote(symbol: str, market: str) -> Optional["StockPriceResponse"]:
    try:
        q = _tencent_quote_code(symbol, market)
        if not q:
            return None

        disable_proxies_for_process()
        import httpx

        with httpx.Client(timeout=10, follow_redirects=True) as client:
            text = client.get(f"https://qt.gtimg.cn/q={q}").text

        if '"' not in text:
            return None
        payload = text.split('"', 2)[1]
        parts = payload.split("~")

        def _to_float(v):
            if v is None:
                return None
            if isinstance(v, str) and not v.strip():
                return None
            try:
                return float(v)
            except Exception:
                return None

        def _pick(i: int):
            if i < len(parts):
                return _to_float(parts[i])
            return None

        name = (parts[1] if len(parts) > 1 else "") or ""
        price = _pick(3)
        prev_close = _pick(4)
        open_p = _pick(5)
        high = _pick(33)
        low = _pick(34)
        volume = _pick(36)

        amount = None
        if len(parts) > 35 and parts[35]:
            seg = str(parts[35]).split("/")
            if len(seg) >= 3:
                amount = _to_float(seg[2])
        if amount is None:
            amount = _pick(37)
        if amount is None and price is not None and volume is not None:
            amount = price * volume

        change = None
        change_pct = None
        if price is not None and prev_close is not None and prev_close != 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100

        bid = _pick(9)
        ask = _pick(11)

        market_cap = None
        mkt = (market or "").upper()
        if mkt == "US":
            cand = _pick(62) or _pick(63)
            if cand is not None and cand > 1e8:
                market_cap = cand
        elif mkt in {"CN", "HK"}:
            # Tencent quote uses market cap in "亿" for CN/HK (e.g. 18004.14 means 18004.14亿)
            cand = _pick(45) or _pick(44)
            if cand is not None and cand > 0:
                market_cap = cand * 1e8

        return StockPriceResponse(
            symbol=symbol,
            name=name or symbol,
            market=(market or "CN").upper(),
            price=price,
            change=change,
            change_pct=change_pct,
            volume=volume,
            amount=amount,
            market_cap=market_cap,
            high=high,
            low=low,
            open=open_p,
            prev_close=prev_close,
            turnover_rate=None,
            volume_ratio=None,
            amplitude=None,
            bid=bid,
            ask=ask,
        )
    except Exception:
        return None


def _stooq_fetch_history_df(symbol: str, count: int = 420):
    try:
        import csv
        import pandas as pd
        import datetime as dt

        sym = (symbol or "").strip().lower()
        if not sym:
            return None
        sym = sym.split(".", 1)[0]
        if not sym.endswith(".us"):
            sym = f"{sym}.us"

        disable_proxies_for_process()
        import httpx

        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = resp.text

        reader = csv.DictReader(text.splitlines())
        rows = [r for r in reader if r.get("Close") and r.get("Close") != "-"]
        if not rows:
            return None

        if count and len(rows) > count:
            rows = rows[-count:]

        def _num(v):
            if v in (None, "", "-"):
                return None
            try:
                return float(v)
            except Exception:
                return None

        out = pd.DataFrame(
            {
                "date": pd.to_datetime([r.get("Date") for r in rows], errors="coerce"),
                "open": pd.to_numeric([_num(r.get("Open")) for r in rows], errors="coerce"),
                "high": pd.to_numeric([_num(r.get("High")) for r in rows], errors="coerce"),
                "low": pd.to_numeric([_num(r.get("Low")) for r in rows], errors="coerce"),
                "close": pd.to_numeric([_num(r.get("Close")) for r in rows], errors="coerce"),
                "volume": pd.to_numeric([_num(r.get("Volume")) for r in rows], errors="coerce"),
            }
        )
        out = out.dropna(subset=["date"]).sort_values("date")
        if out.empty:
            return None
        out["amount"] = out["close"] * out["volume"]

        try:
            min_date = (dt.date.today() - dt.timedelta(days=420)).isoformat()
            out = out[out["date"] >= pd.to_datetime(min_date)]
        except Exception:
            pass
        return out if not out.empty else None
    except Exception:
        return None


def _tencent_fetch_history_df(symbol: str, market: str, count: int = 420):
    try:
        import pandas as pd

        q = _tencent_quote_code(symbol, market)
        if not q:
            return None

        disable_proxies_for_process()
        import httpx

        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={q},day,,,{count},qfq"
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        qdata = ((data or {}).get("data") or {}).get(q) or {}
        kdata = qdata.get("day") or qdata.get("qfqday")
        if not kdata:
            return None

        out = pd.DataFrame(
            {
                "date": pd.to_datetime([r[0] for r in kdata], errors="coerce"),
                "open": pd.to_numeric([r[1] for r in kdata], errors="coerce"),
                "close": pd.to_numeric([r[2] for r in kdata], errors="coerce"),
                "high": pd.to_numeric([r[3] for r in kdata], errors="coerce"),
                "low": pd.to_numeric([r[4] for r in kdata], errors="coerce"),
                "volume": pd.to_numeric([r[5] for r in kdata], errors="coerce"),
            }
        )
        out = out.dropna(subset=["date"]).sort_values("date")
        out["amount"] = out["close"] * out["volume"]
        return out
    except Exception:
        return None


@app.get("/api/stock/search", response_model=list[StockSearchResult])
def search_stocks(q: str, market: str = "CN"):
    """Search for stocks by keyword using real market data."""
    try:
        def _tencent_smartbox(query: str) -> list[StockSearchResult]:
            try:
                import httpx

                disable_proxies_for_process()
                url = f"https://smartbox.gtimg.cn/s3/?q={query}&t=all"
                with httpx.Client(timeout=10, follow_redirects=True) as client:
                    text = client.get(url).text

                if '"' not in text:
                    return []
                payload = text.split('"', 2)[1]
                items = [x for x in payload.split('^') if x]
                out: list[StockSearchResult] = []

                def _decode_name(s: str) -> str:
                    try:
                        if "\\\\u" in s or "\\\\U" in s:
                            s = s.replace("\\\\u", "\\u").replace("\\\\U", "\\U")
                        if "\\u" in s or "\\U" in s:
                            return s.encode("utf-8").decode("unicode_escape")
                    except Exception:
                        pass
                    return s

                for it in items:
                    parts = it.split('~')
                    if len(parts) < 3:
                        continue
                    m = (parts[0] or '').lower()
                    code = (parts[1] or '').strip()
                    name = _decode_name((parts[2] or '').strip() or code)

                    if m in {"hk"}:
                        if code.isdigit():
                            sym = f"{code.zfill(5)}.HK"
                            out.append(StockSearchResult(symbol=sym, name=name, market="HK"))
                    elif m in {"sh", "sz", "bj"}:
                        if code.isdigit() and len(code) == 6:
                            suf = "SH" if m == "sh" else "SZ" if m == "sz" else "BJ"
                            sym = f"{code}.{suf}"
                            out.append(StockSearchResult(symbol=sym, name=name, market="CN"))
                    elif m in {"us"}:
                        base = code.split('.', 1)[0].upper()
                        if base:
                            out.append(StockSearchResult(symbol=base, name=name, market="US"))
                    if len(out) >= 10:
                        break
                return out
            except Exception:
                return []

        df = _get_stock_spot_data(market)
        if df is None or df.empty:
            # Fallback to Tencent smartbox (all markets)
            out = _tencent_smartbox(q.strip())
            if out:
                return out

            # Last fallback to mock data
            mock_stocks = [
                {"symbol": "600519.SH", "name": "贵州茅台", "market": "CN"},
                {"symbol": "00700.HK", "name": "腾讯控股", "market": "HK"},
                {"symbol": "AAPL", "name": "苹果公司", "market": "US"},
                {"symbol": "BABA", "name": "阿里巴巴", "market": "US"},
                {"symbol": "601318.SH", "name": "中国平安", "market": "CN"},
                {"symbol": "000858.SZ", "name": "五粮液", "market": "CN"},
            ]
            q_lower = q.lower()
            return [
                StockSearchResult(symbol=s["symbol"], name=s["name"], market=s["market"])
                for s in mock_stocks
                if q_lower in s["symbol"].lower() or q_lower in s["name"].lower()
            ][:10]
        
        # Search in real data
        code_col = "代码" if "代码" in df.columns else df.columns[0]
        name_col = "名称" if "名称" in df.columns else (df.columns[1] if len(df.columns) > 1 else None)
        
        q_lower = q.lower()
        results = []
        
        for _, row in df.iterrows():
            code = str(row.get(code_col, ""))
            name = str(row.get(name_col, "")) if name_col else ""
            
            if q_lower in code.lower() or q_lower in name.lower():
                # Format symbol based on market
                if market == "CN":
                    if code.startswith("6"):
                        symbol = f"{code}.SH"
                    elif code.startswith(("0", "3")):
                        symbol = f"{code}.SZ"
                    else:
                        symbol = f"{code}.BJ"
                elif market == "HK":
                    symbol = f"{code.zfill(5)}.HK"
                else:
                    symbol = code
                
                results.append(StockSearchResult(symbol=symbol, name=name, market=market))
                
                if len(results) >= 10:
                    break

        if results:
            return results

        # If the specified market cannot find results (e.g. search HK code/name while market=CN), fallback
        return _tencent_smartbox(q.strip())
    except Exception as e:
        print(f"Search error: {e}")
        return []


class StockPriceResponse(BaseModel):
    symbol: str
    name: str
    market: str
    price: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[float]
    market_cap: Optional[float]
    high: Optional[float] = None
    low: Optional[float] = None
    amount: Optional[float] = None
    open: Optional[float] = None
    prev_close: Optional[float] = None
    turnover_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    amplitude: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None


class StockIndicatorsResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    market: str
    currency: Optional[str] = None
    as_of: Optional[str] = None

    market_cap: Optional[float] = None
    amount: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None

    ma5: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    rsi14: Optional[float] = None
    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    macd_hist: Optional[float] = None

    buy_price_aggressive: Optional[float] = None
    buy_price_stable: Optional[float] = None
    sell_price: Optional[float] = None

    signal_golden_cross: Optional[bool] = None
    signal_death_cross: Optional[bool] = None
    signal_macd_bullish: Optional[bool] = None
    signal_rsi_overbought: Optional[bool] = None
    signal_vol_gt_ma5: Optional[bool] = None
    signal_vol_gt_ma10: Optional[bool] = None


@app.get("/api/stock/price", response_model=Optional[StockPriceResponse])
def get_stock_price(symbol: str, market: str = "CN"):
    """Get real-time stock price."""
    try:
        market = (market or "CN").upper()
        df = _get_stock_spot_data(market)
        if df is None or df.empty:
            return _tencent_fetch_quote(symbol, market)
        
        # Extract code from symbol
        if market == "CN":
            code = symbol.split(".")[0]
        elif market == "HK":
            code = symbol.replace(".HK", "").zfill(5)
        else:
            code = symbol
        
        code_upper = str(code).upper()
        candidate_code_cols = [
            c
            for c in [
                "代码",
                "symbol",
                "Symbol",
                "股票代码",
                "ticker",
                "Ticker",
            ]
            if c in df.columns
        ]
        if not candidate_code_cols:
            candidate_code_cols = [df.columns[0]]

        row_df = None
        for ccol in candidate_code_cols:
            tmp = df[df[ccol].astype(str).str.upper() == code_upper]
            if not tmp.empty:
                row_df = tmp
                break
        if row_df is None or row_df.empty:
            # Fallback: contains match
            for ccol in candidate_code_cols:
                tmp = df[df[ccol].astype(str).str.upper().str.contains(code_upper, na=False)]
                if not tmp.empty:
                    row_df = tmp
                    break
        if row_df is None or row_df.empty:
            return _tencent_fetch_quote(symbol, market)

        row = row_df.iloc[0]
        
        def _to_float(v):
            if v is None:
                return None
            if isinstance(v, str) and not v.strip():
                return None
            try:
                return float(v)
            except Exception:
                return None

        def _pick_float(keys: list[str]):
            for k in keys:
                if k in df.columns and row.get(k) is not None and row.get(k) != "":
                    val = _to_float(row.get(k))
                    if val is not None:
                        return val
            return None

        # Extract data based on column names
        name = str(row.get("名称") or row.get("name") or row.get("Name") or "")
        price = _pick_float(["最新价", "现价", "收盘", "price", "Price", "last"])
        change = _pick_float(["涨跌额", "涨跌", "change", "Change"])
        change_pct = _pick_float(["涨跌幅", "涨跌幅%", "涨跌幅(%)", "pct", "pct_chg", "change_pct", "ChangePct"])
        volume = _pick_float(["成交量", "成交量(手)", "成交量(股)", "volume", "Volume"])
        amount = _pick_float(["成交额", "成交额(元)", "成交金额", "成交金额(元)", "amount", "Amount"])
        market_cap = _pick_float(["总市值", "市值", "总市值(元)", "market_cap", "MarketCap"])
        open_p = _pick_float(["今开", "开盘", "开盘价", "open", "Open"])
        prev_close = _pick_float(["昨收", "前收盘", "昨收盘", "prev_close", "PrevClose"])
        turnover_rate = _pick_float(["换手率", "换手率(%)", "turnover", "turnover_rate", "TurnoverRate"])
        volume_ratio = _pick_float(["量比", "量比(%)", "volume_ratio", "VolumeRatio"])
        amplitude = _pick_float(["振幅", "振幅(%)", "amplitude", "Amplitude"])
        bid = _pick_float(["买一", "买一价", "买入", "bid", "Bid"])
        ask = _pick_float(["卖一", "卖一价", "卖出", "ask", "Ask"])

        high = None
        low = None
        if "最高" in df.columns and row.get("最高") is not None and row.get("最高") != "":
            try:
                high = float(row.get("最高"))
            except Exception:
                high = None
        if "最低" in df.columns and row.get("最低") is not None and row.get("最低") != "":
            try:
                low = float(row.get("最低"))
            except Exception:
                low = None
        if high is None:
            high = _pick_float(["最高", "high", "High"])
        if low is None:
            low = _pick_float(["最低", "low", "Low"])
        
        return StockPriceResponse(
            symbol=symbol,
            name=name,
            market=market,
            price=price,
            change=change,
            change_pct=change_pct,
            volume=volume,
            amount=amount,
            market_cap=market_cap,
            high=high,
            low=low,
            open=open_p,
            prev_close=prev_close,
            turnover_rate=turnover_rate,
            volume_ratio=volume_ratio,
            amplitude=amplitude,
            bid=bid,
            ask=ask,
        )
    except Exception as e:
        print(f"Price error: {e}")
        return None


_INDICATOR_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}


def _rsi14(series):
    import pandas as pd

    s = series.astype(float)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _macd(series):
    s = series.astype(float)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def _find_cross(ma_fast, ma_slow, lookback: int = 20):
    import pandas as pd

    if ma_fast is None or ma_slow is None:
        return None, None
    s = (ma_fast - ma_slow).dropna()
    if s.empty:
        return None, None
    s = s.tail(lookback + 1)
    prev = s.shift(1)
    cross_up = (prev <= 0) & (s > 0)
    cross_down = (prev >= 0) & (s < 0)
    idx_up = s[cross_up].index
    idx_down = s[cross_down].index
    last_up = idx_up[-1] if len(idx_up) else None
    last_down = idx_down[-1] if len(idx_down) else None
    return last_up, last_down


def _fetch_history_df(symbol: str, market: str):
    import pandas as pd
    import datetime as dt

    m = (market or "CN").upper()
    end = dt.date.today()
    start = end - dt.timedelta(days=420)

    if m == "CN":
        try:
            disable_proxies_for_process()
            import akshare as ak

            code = symbol.split(".")[0]
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="",
            )
            if df is None or df.empty:
                raise ValueError("empty akshare history")
            out = pd.DataFrame(
                {
                    "date": pd.to_datetime(df["日期"], errors="coerce"),
                    "open": pd.to_numeric(df.get("开盘"), errors="coerce"),
                    "high": pd.to_numeric(df.get("最高"), errors="coerce"),
                    "low": pd.to_numeric(df.get("最低"), errors="coerce"),
                    "close": pd.to_numeric(df.get("收盘"), errors="coerce"),
                    "volume": pd.to_numeric(df.get("成交量"), errors="coerce"),
                    "amount": pd.to_numeric(df.get("成交额"), errors="coerce"),
                }
            )
            out = out.dropna(subset=["date"]).sort_values("date")
            return out
        except Exception:
            out = None

        tdf = _tencent_fetch_history_df(symbol, market)
        if tdf is not None and not tdf.empty:
            return tdf
        return None

    try:
        disable_proxies_for_process()
        import yfinance as yf

        yf_symbol = symbol
        if m == "HK":
            if not yf_symbol.upper().endswith(".HK"):
                base = yf_symbol.replace(".HK", "")
                yf_symbol = f"{base.zfill(4)}.HK" if base.isdigit() else f"{base}.HK"
        df = yf.download(yf_symbol, start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat(), progress=False)
        if df is None or df.empty:
            tdf = _tencent_fetch_history_df(symbol, market)
            if tdf is not None and not tdf.empty:
                return tdf
            return None
        df = df.reset_index()
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["Date"], errors="coerce"),
                "open": pd.to_numeric(df.get("Open"), errors="coerce"),
                "high": pd.to_numeric(df.get("High"), errors="coerce"),
                "low": pd.to_numeric(df.get("Low"), errors="coerce"),
                "close": pd.to_numeric(df.get("Close"), errors="coerce"),
                "volume": pd.to_numeric(df.get("Volume"), errors="coerce"),
            }
        )
        out = out.dropna(subset=["date"]).sort_values("date")
        out["amount"] = out["close"] * out["volume"]

        if m == "US" and len(out) < 60:
            sdf = _stooq_fetch_history_df(symbol)
            if sdf is not None and not sdf.empty:
                return sdf
        return out
    except Exception:
        tdf = _tencent_fetch_history_df(symbol, market)
        if tdf is not None and not tdf.empty:
            if m == "US" and len(tdf) < 60:
                sdf = _stooq_fetch_history_df(symbol)
                if sdf is not None and not sdf.empty:
                    return sdf
            return tdf
        if m == "US":
            sdf = _stooq_fetch_history_df(symbol)
            if sdf is not None and not sdf.empty:
                return sdf
        return None


@app.get("/api/stock/indicators", response_model=Optional[StockIndicatorsResponse])
def get_stock_indicators(symbol: str, market: str = "CN"):
    import time
    import pandas as pd

    key = (market or "CN").upper(), (symbol or "").upper()
    now = time.time()
    cached = _INDICATOR_CACHE.get(key)
    if cached and (now - cached[0]) < 300:
        return cached[1]

    df = _fetch_history_df(symbol, market)
    if df is None or df.empty:
        return None

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float)

    ma5 = close.rolling(window=5).mean()
    ma20 = close.rolling(window=20).mean()
    ma60 = close.rolling(window=60).mean()
    rsi = _rsi14(close)
    dif, dea, hist = _macd(close)

    tail252 = df.tail(252)
    high_52w = float(pd.to_numeric(tail252["high"], errors="coerce").max()) if not tail252.empty else None
    low_52w = float(pd.to_numeric(tail252["low"], errors="coerce").min()) if not tail252.empty else None

    last_row = df.iloc[-1]
    as_of = None
    try:
        as_of = pd.to_datetime(last_row["date"]).date().isoformat()
    except Exception:
        as_of = None

    amount = None
    try:
        amount = float(last_row.get("amount")) if last_row.get("amount") is not None else None
    except Exception:
        amount = None

    # signals
    last_up, last_down = _find_cross(ma5, ma20, lookback=30)
    signal_golden_cross = bool(last_up is not None and (last_down is None or last_up > last_down))
    signal_death_cross = bool(last_down is not None and (last_up is None or last_down > last_up))

    macd_dif = float(dif.iloc[-1]) if not dif.empty and pd.notna(dif.iloc[-1]) else None
    macd_dea = float(dea.iloc[-1]) if not dea.empty and pd.notna(dea.iloc[-1]) else None
    macd_hist = float(hist.iloc[-1]) if not hist.empty and pd.notna(hist.iloc[-1]) else None
    signal_macd_bullish = None
    if macd_dif is not None and macd_dea is not None:
        signal_macd_bullish = macd_dif > macd_dea
    elif macd_hist is not None:
        signal_macd_bullish = macd_hist > 0

    rsi14 = float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else None
    signal_rsi_overbought = True if (rsi14 is not None and rsi14 > 70) else False if rsi14 is not None else None

    vol_ma5 = vol.rolling(window=5).mean()
    vol_ma10 = vol.rolling(window=10).mean()
    signal_vol_gt_ma5 = None
    signal_vol_gt_ma10 = None
    if len(vol) >= 6 and pd.notna(vol.iloc[-1]) and pd.notna(vol_ma5.iloc[-2]):
        signal_vol_gt_ma5 = float(vol.iloc[-1]) > float(vol_ma5.iloc[-2])
    if len(vol) >= 11 and pd.notna(vol.iloc[-1]) and pd.notna(vol_ma10.iloc[-2]):
        signal_vol_gt_ma10 = float(vol.iloc[-1]) > float(vol_ma10.iloc[-2])

    # Strict criteria: only output prices when signals meet criteria
    buy_ok = bool(signal_golden_cross) and bool(signal_macd_bullish) and (signal_rsi_overbought is False)
    if signal_vol_gt_ma5 is not None or signal_vol_gt_ma10 is not None:
        buy_ok = buy_ok and bool(signal_vol_gt_ma5 or signal_vol_gt_ma10)

    buy_price_aggressive = float(ma20.iloc[-1]) if (buy_ok and pd.notna(ma20.iloc[-1])) else None
    buy_price_stable = None
    if buy_ok and last_up is not None:
        try:
            if last_up in df.index:
                buy_price_stable = float(df.loc[last_up, "close"])
            elif isinstance(last_up, (int, float)):
                buy_price_stable = float(df.iloc[int(last_up)]["close"])
        except Exception:
            buy_price_stable = None

    sell_price = None
    try:
        if len(ma20.dropna()) >= 6:
            ma20_tail = ma20.dropna().tail(5)
            slope = float(ma20_tail.iloc[-1] - ma20_tail.iloc[0])
            last_close = float(close.iloc[-1]) if pd.notna(close.iloc[-1]) else None
            last_ma20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None
            if last_close is not None and last_ma20 is not None and last_close < last_ma20 and slope <= 0:
                sell_price = last_ma20
    except Exception:
        sell_price = None

    currency = "CNY" if market.upper() == "CN" else ("HKD" if market.upper() == "HK" else "USD")
    name = None
    market_cap = None
    if market.upper() in {"US", "HK"}:
        try:
            disable_proxies_for_process()
            import yfinance as yf

            yf_symbol = symbol
            if market.upper() == "HK" and not yf_symbol.upper().endswith(".HK"):
                base = yf_symbol.replace(".HK", "")
                yf_symbol = f"{base.zfill(4)}.HK" if base.isdigit() else f"{base}.HK"
            t = yf.Ticker(yf_symbol)
            info = getattr(t, "fast_info", None) or {}
            try:
                name = (t.info or {}).get("shortName") or (t.info or {}).get("longName")
            except Exception:
                name = None
            try:
                market_cap = (t.info or {}).get("marketCap")
            except Exception:
                market_cap = None
            try:
                currency = (t.info or {}).get("currency") or currency
            except Exception:
                pass
        except Exception:
            pass

    payload = StockIndicatorsResponse(
        symbol=symbol,
        name=name,
        market=market,
        currency=currency,
        as_of=as_of,
        market_cap=market_cap,
        amount=amount,
        high_52w=high_52w,
        low_52w=low_52w,
        ma5=float(ma5.iloc[-1]) if pd.notna(ma5.iloc[-1]) else None,
        ma20=float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None,
        ma60=float(ma60.iloc[-1]) if pd.notna(ma60.iloc[-1]) else None,
        rsi14=rsi14,
        macd_dif=macd_dif,
        macd_dea=macd_dea,
        macd_hist=macd_hist,
        buy_price_aggressive=buy_price_aggressive,
        buy_price_stable=buy_price_stable,
        sell_price=sell_price,
        signal_golden_cross=signal_golden_cross,
        signal_death_cross=signal_death_cross,
        signal_macd_bullish=signal_macd_bullish,
        signal_rsi_overbought=signal_rsi_overbought,
        signal_vol_gt_ma5=signal_vol_gt_ma5,
        signal_vol_gt_ma10=signal_vol_gt_ma10,
    )

    out = payload.model_dump()
    _INDICATOR_CACHE[key] = (now, out)
    return out


@app.post("/api/reports/{report_id}/reanalyze")
def reanalyze_uploaded_report(report_id: str, background_tasks: BackgroundTasks):
    """Re-run PDF analysis for an uploaded report."""
    try:
        with session_scope() as s:
            r = s.get(Report, report_id)
            if not r:
                raise HTTPException(status_code=404, detail="报告不存在")
            if r.source_type != "file_upload":
                raise HTTPException(status_code=400, detail="仅支持对上传文件报告重新分析")

            try:
                meta = json.loads(r.source_meta or "{}")
            except Exception:
                meta = {}

            pdf_path = (meta.get("upload_saved_path") or "").strip()
            if not pdf_path:
                raise HTTPException(status_code=400, detail="未找到上传文件路径，无法重新分析")

            r.status = "running"
            r.error_message = None
            r.updated_at = int(time.time())

        background_tasks.add_task(run_pdf_analysis_in_background, report_id, pdf_path)
        return {"report_id": report_id, "status": "running", "message": "已开始重新分析"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")


def run_analysis_in_background(report_id: str):
    """Run analysis in background thread."""
    try:
        disable_proxies_for_process()
        ingest_and_analyze_a_share(report_id)
    except Exception as e:
        # Update report status to failed
        with session_scope() as s:
            r = s.get(Report, report_id)
            if r:
                r.status = "failed"
                r.error_message = str(e)


def run_pdf_analysis_in_background(report_id: str, pdf_path: str):
    """Run PDF analysis in background thread."""
    import time
    try:
        # Update status to running
        with session_scope() as s:
            r = s.get(Report, report_id)
            if r:
                r.status = "running"
                r.updated_at = int(time.time())
        
        # Try to extract financials from PDF (prefer force AI, fallback to regex when missing API key)
        from core.pdf_analyzer import extract_financials_from_pdf
        try:
            financials = extract_financials_from_pdf(pdf_path, use_ai=True, force_ai=True)
        except Exception as e:
            msg = str(e)
            if "ai_required_no_api_key" in msg or "missing_api_key" in msg:
                financials = extract_financials_from_pdf(pdf_path, use_ai=False, force_ai=False)
            else:
                raise
        
        # Update report with extracted data and save metrics
        with session_scope() as s:
            r = s.get(Report, report_id)
            if not r:
                return

            # Clear existing children to avoid duplicates
            delete_report_children(report_id)

            r.updated_at = int(time.time())

            # Update period_end if extracted
            period_end = financials.report_period or r.period_end
            if financials.report_period:
                r.period_end = financials.report_period

            # Infer period_type from period_end (best-effort)
            if financials.report_period:
                if financials.report_period.endswith(("-03-31", "-06-30", "-09-30")):
                    r.period_type = "quarter"
                elif financials.report_period.endswith("-12-31"):
                    r.period_type = "annual"

            period_type = r.period_type
            company_id = r.company_id

            # Save extracted metrics to computed_metrics table
            metrics_to_save: list[tuple[str, str, float, str]] = []
            if financials.gross_margin_direct is not None:
                metrics_to_save.append(("GROSS_MARGIN", "毛利率", financials.gross_margin_direct, "%"))
            if financials.net_margin_direct is not None:
                metrics_to_save.append(("NET_MARGIN", "净利率", financials.net_margin_direct, "%"))
            if financials.roe_direct is not None:
                metrics_to_save.append(("ROE", "ROE (净资产收益率)", financials.roe_direct, "%"))
            if financials.roa_direct is not None:
                metrics_to_save.append(("ROA", "ROA (总资产收益率)", financials.roa_direct, "%"))
            if financials.current_ratio_direct is not None:
                metrics_to_save.append(("CURRENT_RATIO", "流动比率", financials.current_ratio_direct, ""))
            if financials.debt_ratio_direct is not None:
                metrics_to_save.append(("DEBT_ASSET", "资产负债率", financials.debt_ratio_direct, "%"))

            # Calculate metrics from raw data if direct metrics not available
            if financials.revenue and financials.gross_profit and financials.gross_margin_direct is None:
                gm = (financials.gross_profit / financials.revenue) * 100
                metrics_to_save.append(("GROSS_MARGIN", "毛利率", gm, "%"))
            if financials.revenue and financials.net_profit and financials.net_margin_direct is None:
                nm = (financials.net_profit / financials.revenue) * 100
                metrics_to_save.append(("NET_MARGIN", "净利率", nm, "%"))
            if financials.total_equity and financials.net_profit and financials.roe_direct is None:
                roe = (financials.net_profit / financials.total_equity) * 100
                metrics_to_save.append(("ROE", "ROE (净资产收益率)", roe, "%"))
            if financials.total_assets and financials.net_profit and financials.roa_direct is None:
                roa = (financials.net_profit / financials.total_assets) * 100
                metrics_to_save.append(("ROA", "ROA (总资产收益率)", roa, "%"))
            if financials.current_assets and financials.current_liabilities and financials.current_ratio_direct is None:
                cr = financials.current_assets / financials.current_liabilities
                metrics_to_save.append(("CURRENT_RATIO", "流动比率", cr, ""))
            if financials.total_assets and financials.total_liabilities and financials.debt_ratio_direct is None:
                dr = (financials.total_liabilities / financials.total_assets) * 100
                metrics_to_save.append(("DEBT_ASSET", "资产负债率", dr, "%"))

            for code, name, value, unit in metrics_to_save:
                s.add(
                    ComputedMetric(
                        report_id=report_id,
                        company_id=company_id,
                        period_end=period_end,
                        period_type=period_type,
                        metric_code=code,
                        metric_name=name,
                        value=value,
                        unit=unit,
                    )
                )

            if metrics_to_save:
                r.status = "done"
                r.error_message = None
            else:
                r.status = "failed"
                r.error_message = "未能从PDF中提取到可用的财务指标"

            print(f"PDF analysis completed: {len(metrics_to_save)} metrics saved for report {report_id}")
    except Exception as e:
        print(f"PDF analysis error: {e}")
        import traceback
        traceback.print_exc()
        # Update report status to failed
        with session_scope() as s:
            r = s.get(Report, report_id)
            if r:
                r.status = "failed"
                msg = str(e)
                if "ai_required_no_api_key" in msg or "missing_api_key" in msg:
                    r.error_message = "未配置 DASHSCOPE_API_KEY，已设置为强制AI解析，因此无法完成。请先配置API Key。"
                else:
                    r.error_message = f"PDF解析失败: {msg}"
                r.updated_at = int(time.time())


@app.post("/api/reports/upload")
async def upload_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_name: str = Form(""),
    period_type: str = Form("annual"),
    period_end: str = Form(None),
):
    """Upload a financial report file."""
    try:
        # Read file content
        content = await file.read()
        
        # Save file using core function
        saved_path = save_uploaded_file(
            filename=file.filename or "upload",
            data=content
        )
        
        # Determine period_end
        if not period_end:
            period_end = date.today().isoformat()
        
        final_company = company_name.strip() if company_name.strip() else "待识别"
        decoded_filename = file.filename or "upload"
        try:
            if "%" in decoded_filename:
                decoded_filename = unquote(decoded_filename)
        except Exception:
            decoded_filename = file.filename or "upload"
        report_name = f"{final_company} - {decoded_filename}"
        filetype = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
        
        meta = {
            "upload_company_name": final_company,
            "upload_filename": file.filename,
            "upload_filetype": filetype,
            "upload_saved_path": str(saved_path),
        }
        
        # Create report record
        report_id = upsert_report_file_upload(
            upload_company_name=final_company,
            report_name=report_name,
            period_type=period_type,
            period_end=period_end,
            source_meta=meta,
        )
        
        # Start PDF analysis in background if it's a PDF file
        if filetype == "pdf":
            background_tasks.add_task(run_pdf_analysis_in_background, report_id, str(saved_path))
        
        return {"report_id": report_id, "message": "上传成功，正在分析中", "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.post("/api/reports/fetch")
def fetch_market_report(
    background_tasks: BackgroundTasks,
    symbol: str,
    market: str = "CN",
    period_type: str = "annual",
    period_end: str = "2024-12-31",
):
    """Fetch financial report from market data and start analysis."""
    try:
        disable_proxies_for_process()
        
        # Normalize symbol
        symbol_norm = normalize_symbol(market, symbol)
        
        # Create company record
        company_id = upsert_company(market=market, symbol=symbol_norm)
        
        # Create report record
        report_id = upsert_report_market_fetch(
            company_id=company_id,
            report_name=f"{symbol_norm} {period_end}",
            market=market,
            period_type=period_type,
            period_end=period_end,
            source_meta={"symbol": symbol_norm, "market": market},
        )
        
        # Start analysis in background
        background_tasks.add_task(run_analysis_in_background, report_id)
        
        return {
            "report_id": report_id, 
            "message": "已开始获取财报数据，分析正在进行中",
            "status": "running"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
