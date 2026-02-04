"""
FastAPI backend for the Financial Analyzer frontend.
Run with: uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import json
import multiprocessing
import os
import threading
import time
from io import BytesIO
from pathlib import Path
from datetime import date
from typing import Optional
from urllib.parse import unquote
import numpy as np
import pandas as pd
import requests

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from core.db import session_scope
from core.models import (
    Alert,
    Company,
    ComputedMetric,
    PortfolioPosition,
    PortfolioTrade,
    Report,
    Statement,
    StatementItem,
)
from core.repository import (
    list_reports,
    get_report,
    normalize_market,
    upsert_company,
    delete_report_children,
    upsert_report_market_fetch,
    upsert_report_file_upload,
)
from core.schema import init_db
from core.uploads import save_uploaded_file, save_uploaded_file_stream
from core.pipeline import ingest_and_analyze_market_fetch
from core.stock_search import normalize_symbol
from core.net import disable_proxies_for_process

# Initialize database
init_db()


_MAX_UPLOAD_BYTES = int((os.environ.get("MAX_UPLOAD_MB") or "30").strip() or "30") * 1024 * 1024
_PDF_ANALYSIS_SEM = threading.Semaphore(int((os.environ.get("PDF_ANALYSIS_CONCURRENCY") or "1").strip() or "1"))

_SPOT_CACHE: dict[str, tuple[float, "pd.DataFrame"]] = {}

# If yfinance is rate-limited for US symbols, skip yfinance for a short cooldown window.
_YF_US_COOLDOWN_UNTIL: float = 0.0


def _pdf_extract_worker(
    conn,
    path: str,
    use_ai: bool,
    force_ai: bool,
    max_mem_mb: int,
    cpu_seconds: int,
):
    """Worker for PDF extraction in a subprocess.

    Must be module-level to support multiprocessing 'spawn' start method.
    """
    try:
        try:
            import resource

            if max_mem_mb and max_mem_mb > 0:
                limit_bytes = int(max_mem_mb) * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
            if cpu_seconds and cpu_seconds > 0:
                resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_seconds), int(cpu_seconds)))
        except Exception:
            pass

        try:
            disable_proxies_for_process()
        except Exception:
            pass

        from core.pdf_analyzer import extract_financials_from_pdf

        res = extract_financials_from_pdf(path, use_ai=use_ai, force_ai=force_ai)
        try:
            conn.send({"ok": True, "data": res})
        except Exception:
            pass
    except Exception as e:
        try:
            import traceback

            msg = str(e) if e is not None else ""
            if not msg:
                msg = f"{type(e).__name__}"
            tb = traceback.format_exc(limit=50)
            conn.send({"ok": False, "error": msg, "traceback": tb})
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

app = FastAPI(title="Financial Analyzer API", version="1.0.0")


@app.get("/api/version")
def api_version():
    rev = None
    try:
        p = Path("/app/.app_rev")
        if p.exists():
            rev = p.read_text(encoding="utf-8").strip() or None
    except Exception:
        rev = None

    return {
        "app_rev": rev,
        "force_pdf_ai": (os.environ.get("FORCE_PDF_AI") or "").strip(),
        "enable_ocr": (os.environ.get("ENABLE_OCR") or "").strip(),
        "auto_ocr_fallback": (os.environ.get("AUTO_OCR_FALLBACK") or "").strip(),
    }

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
    industry_code: Optional[str] = None


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


class PortfolioPositionResponse(BaseModel):
    id: str
    market: str
    symbol: str
    name: Optional[str] = None
    quantity: float
    avg_cost: float
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    strategy_buy_price: Optional[float] = None
    strategy_buy_ok: Optional[bool] = None
    strategy_buy_reason: Optional[str] = None
    strategy_sell_price: Optional[float] = None
    strategy_sell_ok: Optional[bool] = None
    strategy_sell_reason: Optional[str] = None
    updated_at: int


class PortfolioCreatePositionRequest(BaseModel):
    market: str
    symbol: str
    name: Optional[str] = None
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None


class PortfolioUpdatePositionRequest(BaseModel):
    name: Optional[str] = None
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None


class PortfolioTradeRequest(BaseModel):
    position_id: str
    side: str  # BUY / SELL
    quantity: float


class PortfolioTradeResponse(BaseModel):
    id: str
    position_id: str
    side: str
    price: float
    quantity: float
    amount: float
    created_at: int


class PortfolioAlertResponse(BaseModel):
    key: str
    position_id: str
    market: str
    symbol: str
    name: Optional[str] = None
    alert_type: str
    message: str
    current_price: Optional[float] = None
    trigger_price: Optional[float] = None


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

    industry_code = None
    try:
        if report.company_id:
            with session_scope() as s:
                c = s.get(Company, report.company_id)
                if c and c.industry_code:
                    industry_code = c.industry_code
    except Exception:
        industry_code = None

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
        industry_code=industry_code,
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


@app.get("/api/portfolio/positions", response_model=list[PortfolioPositionResponse])
def list_portfolio_positions():
    def _normalize_market(m: str) -> str:
        mm = (m or "").strip().upper()
        return mm or "CN"

    out: list[PortfolioPositionResponse] = []
    with session_scope() as s:
        rows = s.execute(select(PortfolioPosition).order_by(PortfolioPosition.updated_at.desc())).scalars().all()
        for p in rows:
            market = _normalize_market(p.market)
            symbol = (p.symbol or "").strip().upper()
            name = (p.name or "").strip() or None

            current_price = None
            try:
                sp = get_stock_price(symbol=symbol, market=market)
                current_price = getattr(sp, "price", None) if sp is not None else None
            except Exception:
                current_price = None

            qty = float(p.quantity or 0.0)
            avg_cost = float(p.avg_cost or 0.0)
            mv = None
            pnl = None
            pnl_pct = None
            if current_price is not None:
                mv = current_price * qty
                pnl = (current_price - avg_cost) * qty
                pnl_pct = None if avg_cost <= 0 else (current_price / avg_cost - 1.0) * 100.0

            strategy_buy_price = None
            strategy_buy_ok = None
            strategy_buy_reason = None
            strategy_sell_price = None
            strategy_sell_ok = None
            strategy_sell_reason = None
            try:
                si = get_stock_indicators(symbol=symbol, market=market)
                if isinstance(si, dict):
                    strategy_buy_price = si.get("buy_price_aggressive")
                    strategy_buy_ok = si.get("buy_price_aggressive_ok")
                    strategy_buy_reason = si.get("buy_reason")
                    strategy_sell_price = si.get("sell_price")
                    strategy_sell_ok = si.get("sell_price_ok")
                    strategy_sell_reason = si.get("sell_reason")
                else:
                    strategy_buy_price = getattr(si, "buy_price_aggressive", None)
                    strategy_buy_ok = getattr(si, "buy_price_aggressive_ok", None)
                    strategy_buy_reason = getattr(si, "buy_reason", None)
                    strategy_sell_price = getattr(si, "sell_price", None)
                    strategy_sell_ok = getattr(si, "sell_price_ok", None)
                    strategy_sell_reason = getattr(si, "sell_reason", None)
            except Exception:
                strategy_buy_price = None
                strategy_buy_ok = None
                strategy_buy_reason = None
                strategy_sell_price = None
                strategy_sell_ok = None
                strategy_sell_reason = None

            out.append(
                PortfolioPositionResponse(
                    id=p.id,
                    market=market,
                    symbol=symbol,
                    name=name,
                    quantity=qty,
                    avg_cost=avg_cost,
                    target_buy_price=p.target_buy_price,
                    target_sell_price=p.target_sell_price,
                    current_price=current_price,
                    market_value=mv,
                    unrealized_pnl=pnl,
                    unrealized_pnl_pct=pnl_pct,
                    strategy_buy_price=strategy_buy_price,
                    strategy_buy_ok=strategy_buy_ok,
                    strategy_buy_reason=strategy_buy_reason,
                    strategy_sell_price=strategy_sell_price,
                    strategy_sell_ok=strategy_sell_ok,
                    strategy_sell_reason=strategy_sell_reason,
                    updated_at=int(p.updated_at or 0),
                )
            )

    return out


@app.post("/api/portfolio/positions", response_model=PortfolioPositionResponse)
def create_portfolio_position(req: PortfolioCreatePositionRequest):
    market = (req.market or "CN").strip().upper()
    symbol = normalize_symbol(market, req.symbol)
    name = (req.name or "").strip() or None
    now = int(time.time())

    with session_scope() as s:
        existing = s.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.market == market,
                PortfolioPosition.symbol == symbol,
            )
        ).scalars().first()

        if existing:
            if name is not None:
                existing.name = name
            existing.target_buy_price = req.target_buy_price
            existing.target_sell_price = req.target_sell_price
            existing.updated_at = now
            p = existing
        else:
            p = PortfolioPosition(
                market=market,
                symbol=symbol,
                name=name,
                quantity=0.0,
                avg_cost=0.0,
                target_buy_price=req.target_buy_price,
                target_sell_price=req.target_sell_price,
                created_at=now,
                updated_at=now,
            )
            s.add(p)
            s.flush()

    # reuse list calculation logic
    res = list_portfolio_positions()
    for it in res:
        if it.market == market and it.symbol == symbol:
            return it
    raise HTTPException(status_code=500, detail="create_position_failed")


@app.patch("/api/portfolio/positions/{position_id}", response_model=PortfolioPositionResponse)
def update_portfolio_position(position_id: str, req: PortfolioUpdatePositionRequest):
    now = int(time.time())
    with session_scope() as s:
        p = s.get(PortfolioPosition, position_id)
        if not p:
            raise HTTPException(status_code=404, detail="position not found")
        if req.name is not None:
            p.name = (req.name or "").strip() or None
        if req.target_buy_price is not None or req.target_buy_price is None:
            p.target_buy_price = req.target_buy_price
        if req.target_sell_price is not None or req.target_sell_price is None:
            p.target_sell_price = req.target_sell_price
        p.updated_at = now
        market = (p.market or "CN").strip().upper()
        symbol = (p.symbol or "").strip().upper()

    res = list_portfolio_positions()
    for it in res:
        if it.market == market and it.symbol == symbol:
            return it
    raise HTTPException(status_code=500, detail="update_position_failed")


@app.delete("/api/portfolio/positions/{position_id}")
def delete_portfolio_position(position_id: str):
    with session_scope() as s:
        p = s.get(PortfolioPosition, position_id)
        if not p:
            return {"ok": True}
        s.execute(delete(PortfolioTrade).where(PortfolioTrade.position_id == position_id))
        s.execute(delete(PortfolioPosition).where(PortfolioPosition.id == position_id))
    return {"ok": True}


@app.post("/api/portfolio/trades", response_model=PortfolioTradeResponse)
def create_portfolio_trade(req: PortfolioTradeRequest):
    side = (req.side or "").strip().upper()
    if side not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="invalid side")
    try:
        qty = float(req.quantity)
    except Exception:
        qty = 0.0
    if qty <= 0:
        raise HTTPException(status_code=400, detail="invalid quantity")

    now = int(time.time())
    with session_scope() as s:
        p = s.get(PortfolioPosition, req.position_id)
        if not p:
            raise HTTPException(status_code=404, detail="position not found")
        market = (p.market or "CN").strip().upper()
        symbol = (p.symbol or "").strip().upper()

        sp = get_stock_price(symbol=symbol, market=market)
        price = getattr(sp, "price", None) if sp is not None else None
        if price is None:
            raise HTTPException(status_code=400, detail="cannot_get_latest_price")
        price = float(price)

        amount = price * qty
        old_qty = float(p.quantity or 0.0)
        old_avg = float(p.avg_cost or 0.0)

        if side == "BUY":
            new_qty = old_qty + qty
            new_avg = 0.0 if new_qty <= 0 else (old_qty * old_avg + qty * price) / new_qty
            p.quantity = new_qty
            p.avg_cost = new_avg
        else:
            new_qty = max(0.0, old_qty - qty)
            p.quantity = new_qty
            if new_qty <= 0:
                p.avg_cost = 0.0

        p.updated_at = now

        t = PortfolioTrade(
            position_id=p.id,
            side=side,
            price=price,
            quantity=qty,
            amount=amount,
            created_at=now,
        )
        s.add(t)
        s.flush()

        return PortfolioTradeResponse(
            id=t.id,
            position_id=p.id,
            side=side,
            price=price,
            quantity=qty,
            amount=amount,
            created_at=now,
        )


@app.get("/api/portfolio/alerts", response_model=list[PortfolioAlertResponse])
def get_portfolio_alerts():
    alerts: list[PortfolioAlertResponse] = []

    with session_scope() as s:
        positions = s.execute(select(PortfolioPosition)).scalars().all()

    for p in positions:
        market = (p.market or "CN").strip().upper()
        symbol = (p.symbol or "").strip().upper()
        name = (p.name or "").strip() or None

        sp = None
        try:
            sp = get_stock_price(symbol=symbol, market=market)
        except Exception:
            sp = None
        current_price = getattr(sp, "price", None) if sp is not None else None
        try:
            current_price = None if current_price is None else float(current_price)
        except Exception:
            current_price = None

        # User targets
        if current_price is not None and p.target_buy_price is not None:
            try:
                tb = float(p.target_buy_price)
                if current_price <= tb:
                    alerts.append(
                        PortfolioAlertResponse(
                            key=f"{p.id}:target_buy:{int(tb * 10000)}",
                            position_id=p.id,
                            market=market,
                            symbol=symbol,
                            name=name,
                            alert_type="target_buy",
                            message=f"已到达目标买入价 {tb:.2f}",
                            current_price=current_price,
                            trigger_price=tb,
                        )
                    )
            except Exception:
                pass

        if current_price is not None and p.target_sell_price is not None:
            try:
                ts = float(p.target_sell_price)
                if current_price >= ts:
                    alerts.append(
                        PortfolioAlertResponse(
                            key=f"{p.id}:target_sell:{int(ts * 10000)}",
                            position_id=p.id,
                            market=market,
                            symbol=symbol,
                            name=name,
                            alert_type="target_sell",
                            message=f"已到达目标卖出价 {ts:.2f}",
                            current_price=current_price,
                            trigger_price=ts,
                        )
                    )
            except Exception:
                pass

        # Strategy signals
        try:
            si = get_stock_indicators(symbol=symbol, market=market)
        except Exception:
            si = None

        if si is not None:
            if getattr(si, "buy_price_aggressive_ok", None) is True and getattr(si, "buy_price_aggressive", None) is not None:
                bp = getattr(si, "buy_price_aggressive", None)
                try:
                    bp = float(bp)
                except Exception:
                    bp = None
                alerts.append(
                    PortfolioAlertResponse(
                        key=f"{p.id}:signal_buy",
                        position_id=p.id,
                        market=market,
                        symbol=symbol,
                        name=name,
                        alert_type="signal_buy",
                        message=f"出现买入信号（参考价 {('-' if bp is None else f'{bp:.2f}')}）",
                        current_price=current_price,
                        trigger_price=bp,
                    )
                )

            if getattr(si, "sell_price_ok", None) is True and getattr(si, "sell_price", None) is not None:
                spx = getattr(si, "sell_price", None)
                try:
                    spx = float(spx)
                except Exception:
                    spx = None
                alerts.append(
                    PortfolioAlertResponse(
                        key=f"{p.id}:signal_sell",
                        position_id=p.id,
                        market=market,
                        symbol=symbol,
                        name=name,
                        alert_type="signal_sell",
                        message=f"出现卖出信号（参考价 {('-' if spx is None else f'{spx:.2f}')}）",
                        current_price=current_price,
                        trigger_price=spx,
                    )
                )

    return alerts


def _register_cjk_font_for_pdf() -> str:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return "Helvetica"

    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]

    for fp in candidates:
        try:
            if fp and Path(fp).exists():
                font_name = "CJKFont"
                pdfmetrics.registerFont(TTFont(font_name, fp))
                return font_name
        except Exception:
            continue
    return "Helvetica"


def _build_report_pdf_bytes(report: Report, metrics: list[ComputedMetric], alerts: list[Alert]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.enums import TA_LEFT
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib import colors
    except Exception as e:
        raise RuntimeError(f"reportlab_import_failed:{e}")

    cjk_font = _register_cjk_font_for_pdf()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    try:
        styles["Title"].fontName = cjk_font
        styles["Normal"].fontName = cjk_font
        styles["Heading2"].fontName = cjk_font
        styles["Heading3"].fontName = cjk_font
        styles["Normal"].alignment = TA_LEFT
    except Exception:
        pass

    story = []
    title = getattr(report, "report_name", None) or "分析报告"
    story.append(Paragraph(str(title), styles["Title"]))

    meta_lines: list[str] = []
    if getattr(report, "source_type", None):
        meta_lines.append(f"来源：{report.source_type}")
    if getattr(report, "status", None):
        meta_lines.append(f"状态：{report.status}")
    if getattr(report, "period_end", None):
        meta_lines.append(f"报告期：{report.period_end}")
    if getattr(report, "market", None):
        meta_lines.append(f"市场：{report.market}")
    if meta_lines:
        story.append(Spacer(1, 8))
        story.append(Paragraph("<br/>".join(meta_lines), styles["Normal"]))

    story.append(Spacer(1, 12))

    # ====== Helpers ======
    def _fmt(v: float | None, digits: int = 2) -> str:
        if v is None:
            return "-"
        try:
            return f"{float(v):.{digits}f}"
        except Exception:
            return "-"

    def _value(code: str) -> float | None:
        m = latest_map.get(code)
        if not m:
            return None
        try:
            return None if m.value is None else float(m.value)
        except Exception:
            return None

    # Latest period selection
    metrics_sorted = sorted(metrics or [], key=lambda m: str(getattr(m, "period_end", "") or ""), reverse=True)
    latest_period = (getattr(report, "period_end", None) or "").strip() or (metrics_sorted[0].period_end if metrics_sorted else None)
    latest_metrics = [m for m in (metrics or []) if latest_period and m.period_end == latest_period]
    latest_map = {str(m.metric_code or ""): m for m in latest_metrics}

    gross_margin = _value("GROSS_MARGIN")
    net_margin = _value("NET_MARGIN")
    roe = _value("ROE")
    roa = _value("ROA")
    current_ratio = _value("CURRENT_RATIO")
    debt_ratio = _value("DEBT_ASSET")
    quick_ratio = _value("QUICK_RATIO")
    asset_turnover = _value("ASSET_TURNOVER")
    inv_turnover = _value("INVENTORY_TURNOVER")
    recv_turnover = _value("RECEIVABLE_TURNOVER")

    # Same heuristic constants as frontend
    industry_avg = {
        "grossMargin": 35.0,
        "netMargin": 10.0,
        "roe": 15.0,
        "roa": 8.0,
        "currentRatio": 1.5,
        "debtRatio": 50.0,
        "assetTurnover": 0.8,
    }

    # ====== Overview ======
    story.append(Paragraph("概览", styles["Heading2"]))
    overview_rows = [
        ["关键指标", "数值"],
        ["毛利率", ("-" if gross_margin is None else f"{_fmt(gross_margin)}%")],
        ["净利率", ("-" if net_margin is None else f"{_fmt(net_margin)}%")],
        ["ROE", ("-" if roe is None else f"{_fmt(roe)}%")],
        ["ROA", ("-" if roa is None else f"{_fmt(roa)}%")],
        ["流动比率", _fmt(current_ratio)],
        ["速动比率", _fmt(quick_ratio)],
        ["资产负债率", ("-" if debt_ratio is None else f"{_fmt(debt_ratio)}%")],
    ]
    tbl0 = Table(overview_rows, repeatRows=1, hAlign="LEFT", colWidths=[160, 190])
    tbl0.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f6")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d7de")),
                ("FONTNAME", (0, 0), (-1, -1), cjk_font),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(tbl0)

    story.append(Spacer(1, 10))
    lvl_counts = {"high": 0, "medium": 0, "low": 0}
    for a in alerts or []:
        lvl = str(getattr(a, "level", "") or "").lower()
        if lvl in lvl_counts:
            lvl_counts[lvl] += 1
    story.append(Paragraph(f"风险预警：高风险 {lvl_counts['high']} 条，中风险 {lvl_counts['medium']} 条，低风险 {lvl_counts['low']} 条", styles["Normal"]))

    story.append(Spacer(1, 12))

    # ====== Financial metrics (all periods) ======
    story.append(Paragraph("财务指标", styles["Heading2"]))
    if not metrics:
        story.append(Paragraph("暂无财务指标数据", styles["Normal"]))
    else:
        rows = [["指标", "数值", "单位", "报告期"]]
        for m in metrics_sorted:
            try:
                v = None if m.value is None else float(m.value)
            except Exception:
                v = None
            vstr = "-" if v is None else f"{v:.4g}"
            rows.append([str(m.metric_name or m.metric_code), vstr, str(m.unit or ""), str(m.period_end or "")])
        rows = rows[:1 + min(80, max(0, len(rows) - 1))]
        tbl = Table(rows, repeatRows=1, hAlign="LEFT", colWidths=[150, 80, 40, 70])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f6")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d7de")),
                    ("FONTNAME", (0, 0), (-1, -1), cjk_font),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tbl)

    story.append(Spacer(1, 12))

    # ====== Risk analysis ======
    story.append(Paragraph("风险分析", styles["Heading2"]))
    def _risk_texts() -> list[str]:
        out: list[str] = []
        if net_margin is None:
            out.append("净利率数据缺失，建议补齐利润表相关字段以提高分析质量。")
        elif net_margin < industry_avg["netMargin"]:
            out.append(f"净利率 {_fmt(net_margin)}% 低于行业均值 {industry_avg['netMargin']}%，需关注费用率、一次性损益与价格竞争导致的利润挤压。")
        else:
            out.append(f"净利率 {_fmt(net_margin)}% 高于行业均值 {industry_avg['netMargin']}%，但仍需关注高利润是否来自阶段性红利（原材料、补贴、资产处置等）。")

        if debt_ratio is None:
            out.append("资产负债率数据缺失，建议补齐资产负债表相关字段。")
        elif debt_ratio > 70:
            out.append(f"资产负债率 {_fmt(debt_ratio)}% 偏高，利率上行或现金流波动时可能带来再融资压力，需重点关注短期债务结构与融资成本。")
        else:
            out.append(f"资产负债率 {_fmt(debt_ratio)}% 处于可控区间，但仍建议关注表外负债与或有事项（担保/诉讼/回购条款）。")

        if current_ratio is None:
            out.append("流动比率数据缺失，建议补齐流动资产/流动负债相关字段。")
        elif current_ratio < 1:
            out.append(f"流动比率 {_fmt(current_ratio)} 偏低，短期偿债安全边际不足；若同时出现应收回款变慢或存货积压，风险将放大。")
        else:
            out.append(f"流动比率 {_fmt(current_ratio)} 尚可，仍建议结合速动比率与经营性现金流一起判断真实流动性。")

        if asset_turnover is None:
            out.append("总资产周转率数据缺失，建议补齐收入/资产规模相关字段。")
        elif asset_turnover < industry_avg["assetTurnover"]:
            out.append(f"总资产周转率 {_fmt(asset_turnover)} 低于行业均值 {industry_avg['assetTurnover']}，可能存在产能利用率偏低或资本开支效率不高的问题。")
        else:
            out.append(f"总资产周转率 {_fmt(asset_turnover)} 不低于行业均值 {industry_avg['assetTurnover']}，运营效率相对稳健。")

        return out

    for t in _risk_texts():
        story.append(Paragraph(f"• {t}", styles["Normal"]))

    if alerts:
        story.append(Spacer(1, 8))
        story.append(Paragraph("风险预警明细", styles["Heading3"]))
        for a in alerts:
            lvl = getattr(a, "level", "") or ""
            ttl = getattr(a, "title", "") or ""
            msg = getattr(a, "message", "") or ""
            story.append(Paragraph(f"[{lvl}] {ttl}", styles["Normal"]))
            story.append(Paragraph(str(msg).replace("\n", "<br/>") or "-", styles["Normal"]))
            story.append(Spacer(1, 4))
    else:
        story.append(Spacer(1, 4))
        story.append(Paragraph("暂无风险预警", styles["Normal"]))

    story.append(Spacer(1, 12))

    # ====== Opportunities ======
    story.append(Paragraph("机会识别", styles["Heading2"]))
    def _opp_texts() -> list[str]:
        out: list[str] = []
        if gross_margin is None:
            out.append("毛利率数据缺失，建议补齐成本/收入口径后再评估盈利弹性。")
        elif gross_margin >= industry_avg["grossMargin"]:
            out.append(f"毛利率 {_fmt(gross_margin)}% 不低于行业均值 {industry_avg['grossMargin']}%，若在竞争加剧环境下仍能维持，体现较强议价能力。")
        else:
            out.append(f"毛利率 {_fmt(gross_margin)}% 低于行业均值 {industry_avg['grossMargin']}%，若未来通过产品结构升级/提价/降本改善，可能带来利润弹性。")

        if roe is None:
            out.append("ROE 数据缺失，建议补齐净利润与净资产口径。")
        elif roe > industry_avg["roe"]:
            out.append(f"ROE {_fmt(roe)}% 高于行业均值 {industry_avg['roe']}%，若盈利可持续，具备长期复利潜力。")
        else:
            out.append(f"ROE {_fmt(roe)}% 低于行业均值 {industry_avg['roe']}%，通过改善利润率、周转率或优化资本结构存在提升空间。")

        if debt_ratio is None:
            out.append("资产负债率数据缺失，建议补齐资产负债表口径。")
        elif debt_ratio < industry_avg["debtRatio"]:
            out.append(f"资产负债率 {_fmt(debt_ratio)}% 低于行业均值 {industry_avg['debtRatio']}%，在周期波动或融资收紧时更具抗风险能力。")
        else:
            out.append(f"资产负债率 {_fmt(debt_ratio)}% 不低于行业均值 {industry_avg['debtRatio']}%，若公司具备稳定现金流，仍可能通过杠杆放大 ROE。")

        if asset_turnover is None:
            out.append("总资产周转率数据缺失，建议补齐收入与资产规模。")
        elif asset_turnover < industry_avg["assetTurnover"]:
            out.append(f"总资产周转率 {_fmt(asset_turnover)} 低于行业均值 {industry_avg['assetTurnover']}，若通过渠道效率、产能利用率或库存周转改善，有望提升 ROA/ROE。")
        else:
            out.append(f"总资产周转率 {_fmt(asset_turnover)} 不低于行业均值 {industry_avg['assetTurnover']}，运营效率具备一定优势。")

        return out

    for t in _opp_texts():
        story.append(Paragraph(f"• {t}", styles["Normal"]))

    story.append(Spacer(1, 12))

    # ====== AI Insights (rule-based, consistent with frontend) ======
    story.append(Paragraph("AI 洞察", styles["Heading2"]))
    if metrics_sorted:
        if gross_margin is not None and net_margin is not None:
            story.append(Paragraph(f"• 盈利能力：毛利率 {_fmt(gross_margin, 1)}%，净利率 {_fmt(net_margin, 1)}%，{('盈利能力较强' if net_margin > 10 else '盈利能力一般')}。", styles["Normal"]))
        else:
            story.append(Paragraph("• 盈利能力：数据不足，无法分析盈利能力。", styles["Normal"]))

        if roe is not None and roa is not None:
            story.append(Paragraph(f"• 资本效率：ROE {_fmt(roe, 1)}%，ROA {_fmt(roa, 1)}%，{('资本运用效率优秀' if roe > 15 else '资本运用效率一般')}。", styles["Normal"]))
        else:
            story.append(Paragraph("• 资本效率：数据不足，无法分析资本效率。", styles["Normal"]))

        if debt_ratio is not None and current_ratio is not None:
            story.append(Paragraph(f"• 财务健康：资产负债率 {_fmt(debt_ratio, 1)}%，流动比率 {_fmt(current_ratio, 2)}，{('财务结构稳健' if debt_ratio < 60 else '需关注债务风险')}。", styles["Normal"]))
        else:
            story.append(Paragraph("• 财务健康：数据不足，无法分析财务健康状况。", styles["Normal"]))

        story.append(Spacer(1, 6))
        story.append(Paragraph("投资建议", styles["Heading3"]))
        sugg: list[str] = []
        if roe is not None and roe > 20:
            sugg.append("高ROE表明公司具有竞争优势，可考虑长期持有")
        if debt_ratio is not None and debt_ratio > 70:
            sugg.append("负债率偏高，需关注偿债风险和利率变化影响")
        if net_margin is not None and net_margin > 20:
            sugg.append("净利率优秀，关注是否可持续及行业竞争态势")
        if current_ratio is not None and current_ratio < 1:
            sugg.append("流动比率偏低，需关注短期偿债能力")
        sugg.append("建议结合行业对比和历史趋势进行综合判断")
        for s in sugg:
            story.append(Paragraph(f"• {s}", styles["Normal"]))
    else:
        story.append(Paragraph("暂无足够数据生成AI洞察，请确保报告已完成分析。", styles["Normal"]))

    story.append(Spacer(1, 12))

    # ====== Summary ======
    story.append(Paragraph("分析总结", styles["Heading2"]))
    summary_lines: list[str] = []
    if net_margin is not None:
        summary_lines.append(f"盈利质量：净利率 {_fmt(net_margin)}%（行业均值 {industry_avg['netMargin']}%）")
    if roe is not None:
        summary_lines.append(f"资本回报：ROE {_fmt(roe)}%（行业均值 {industry_avg['roe']}%）")
    if debt_ratio is not None:
        summary_lines.append(f"杠杆水平：资产负债率 {_fmt(debt_ratio)}%（关注 >70% 的再融资压力）")
    if current_ratio is not None:
        summary_lines.append(f"流动性：流动比率 {_fmt(current_ratio)}（关注 <1 的短期偿债风险）")
    if asset_turnover is not None:
        summary_lines.append(f"运营效率：总资产周转率 {_fmt(asset_turnover)}（行业均值 {industry_avg['assetTurnover']}）")
    if not summary_lines:
        summary_lines.append("关键指标不足，建议补齐财务数据后再进行结论性判断。")
    for s in summary_lines:
        story.append(Paragraph(f"• {s}", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()


@app.get("/api/reports/{report_id}/export/pdf")
def export_report_pdf(report_id: str):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    with session_scope() as s:
        metrics = s.execute(select(ComputedMetric).where(ComputedMetric.report_id == report_id)).scalars().all()
        alerts = s.execute(select(Alert).where(Alert.report_id == report_id)).scalars().all()

    try:
        pdf_bytes = _build_report_pdf_bytes(report, metrics, alerts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"export_pdf_failed:{str(e)}")

    from urllib.parse import quote
    import re

    safe_name = (getattr(report, "report_name", None) or "report")
    try:
        if safe_name and "%" in safe_name:
            safe_name = unquote(safe_name)
    except Exception:
        pass
    safe_name = safe_name.replace("/", "-").replace("\\", "-")
    filename = f"{safe_name}-{getattr(report, 'period_end', None) or 'period'}.pdf"

    # Starlette headers are latin-1 encoded; for non-ascii filenames use RFC 5987 filename*
    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", filename) or "report.pdf"
    quoted = quote(filename, safe="")
    content_disposition = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition},
    )


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
        import time
        import pandas as pd

        market = (market or "CN").upper()

        ttl = float((os.environ.get("SPOT_CACHE_TTL_SECONDS") or "300").strip() or "300")
        cached = _SPOT_CACHE.get(market)
        if cached and (time.time() - float(cached[0])) < ttl:
            try:
                df0 = cached[1]
                if df0 is not None and not df0.empty:
                    return df0
            except Exception:
                pass

        disable_proxies_for_process()
        import akshare as ak
        
        out = None
        if market == "CN":
            out = ak.stock_zh_a_spot_em()
        elif market == "HK":
            out = ak.stock_hk_spot_em()
        elif market == "US":
            out = ak.stock_us_spot_em()
        if out is not None and not out.empty:
            _SPOT_CACHE[market] = (time.time(), out)
        return out
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
        mkt = (market or "").upper()
        if mkt == "CN" and volume is not None:
            volume = volume * 100

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

        # US quotes occasionally shift fields for certain symbols; guard against obviously wrong prices.
        if (market or "").upper() == "US" and price is not None and prev_close is not None and prev_close > 0:
            try:
                ratio = price / prev_close
                if ratio < 0.2 or ratio > 5.0:
                    return None
            except Exception:
                pass

        bid = _pick(9)
        ask = _pick(11)

        market_cap = None
        if mkt == "US":
            def _normalize_us_market_cap(raw: float | None) -> float | None:
                if raw is None or raw <= 0:
                    return None
                candidates = [raw, raw * 1e6, raw * 1e8, raw * 1e9]
                valid = [c for c in candidates if 5e8 <= c <= 5e12]
                return max(valid) if valid else None

            for raw in [_pick(45), _pick(44), _pick(62), _pick(63)]:
                market_cap = _normalize_us_market_cap(raw)
                if market_cap is not None:
                    break
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


def _tencent_fetch_pe_ratio(symbol: str, market: str) -> float | None:
    """Best-effort PE ratio from Tencent quote fields.

    This is used as a fallback when yfinance is rate-limited and AkShare spot APIs are unavailable.
    """
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

        def _num(idx: int) -> float | None:
            try:
                if idx < 0 or idx >= len(parts):
                    return None
                v = parts[idx]
                if v is None:
                    return None
                sv = str(v).strip()
                if not sv:
                    return None
                fv = float(sv)
                # sanity range
                if fv <= 0 or fv >= 5000:
                    return None
                return fv
            except Exception:
                return None

        m = (market or "CN").upper()

        # Indices are empirically derived from qt.gtimg.cn payloads.
        # HK: index 39 looks like PE (e.g. 06811 -> 16.41)
        # US: index 39 looks like trailing PE (e.g. AAPL -> ~34)
        # CN: index 65 looks like PE (e.g. 600519 -> ~35)
        if m == "HK":
            return _num(39)
        if m == "US":
            return _num(39) or _num(41)
        if m == "CN":
            return _num(65)
        return None
    except Exception:
        return None


@app.get("/api/qwen/ping")
def qwen_ping():
    """Check whether Qwen (DashScope) is reachable with current DASHSCOPE_API_KEY."""
    try:
        from core.llm_qwen import test_qwen_connection

        ok, msg = test_qwen_connection()
        has_key = bool((os.environ.get("DASHSCOPE_API_KEY") or "").strip())
        return {"ok": bool(ok), "message": msg, "has_key": has_key}
    except Exception as e:
        has_key = bool((os.environ.get("DASHSCOPE_API_KEY") or "").strip())
        return {"ok": False, "message": f"exception:{e}", "has_key": has_key}


def _stooq_fetch_history_df(symbol: str, count: int = 800):
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
        if (market or "").upper() == "CN":
            out["volume"] = pd.to_numeric(out["volume"], errors="coerce") * 100
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
    slope_raw: Optional[float] = None
    slope_pct: Optional[float] = None
    trend: Optional[str] = None
    slope_advice: Optional[str] = None
    pe_ratio: Optional[float] = None
    atr14: Optional[float] = None
    rsi14: Optional[float] = None
    rsi_rebound: Optional[bool] = None
    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    macd_hist: Optional[float] = None

    buy_price_aggressive: Optional[float] = None
    buy_price_stable: Optional[float] = None
    sell_price: Optional[float] = None

    buy_reason: Optional[str] = None
    sell_reason: Optional[str] = None

    buy_price_aggressive_ok: Optional[bool] = None
    buy_price_stable_ok: Optional[bool] = None
    sell_price_ok: Optional[bool] = None

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

        def _yfinance_market_cap_us(sym: str):
            try:
                disable_proxies_for_process()
                import yfinance as yf

                t = yf.Ticker(sym)
                info_fast = getattr(t, "fast_info", None) or {}
                cand = info_fast.get("market_cap") or info_fast.get("marketCap")
                if cand is None:
                    try:
                        cand = (t.info or {}).get("marketCap")
                    except Exception:
                        cand = None
                if cand is None:
                    return None
                mc = float(cand)
                if mc <= 0:
                    return None
                return mc
            except Exception:
                return None

        def _yfinance_quote_us(sym: str) -> Optional[StockPriceResponse]:
            try:
                disable_proxies_for_process()
                import yfinance as yf

                t = yf.Ticker(sym)
                fast = getattr(t, "fast_info", None) or {}
                info = {}
                try:
                    info = t.info or {}
                except Exception:
                    info = {}

                price = _safe_float(
                    fast.get("last_price")
                    or fast.get("lastPrice")
                    or fast.get("regularMarketPrice")
                    or info.get("regularMarketPrice")
                )
                prev_close = _safe_float(
                    fast.get("previous_close")
                    or fast.get("previousClose")
                    or info.get("previousClose")
                )
                open_p = _safe_float(fast.get("open") or info.get("open"))
                high = _safe_float(fast.get("day_high") or fast.get("dayHigh") or info.get("dayHigh"))
                low = _safe_float(fast.get("day_low") or fast.get("dayLow") or info.get("dayLow"))
                volume = _safe_float(fast.get("last_volume") or fast.get("lastVolume") or info.get("volume"))
                amount = (price * volume) if (price is not None and volume is not None) else None

                if price is None:
                    return None

                change = None
                change_pct = None
                if prev_close is not None and prev_close != 0:
                    change = price - prev_close
                    change_pct = (change / prev_close) * 100

                name = (info.get("shortName") or info.get("longName") or sym) if isinstance(info, dict) else sym
                mc = _yfinance_market_cap_us(sym)

                return StockPriceResponse(
                    symbol=sym,
                    name=str(name) if name is not None else sym,
                    market="US",
                    price=price,
                    change=change,
                    change_pct=change_pct,
                    volume=volume,
                    market_cap=mc,
                    high=high,
                    low=low,
                    amount=amount,
                    open=open_p,
                    prev_close=prev_close,
                    turnover_rate=None,
                    volume_ratio=None,
                    amplitude=None,
                    bid=None,
                    ask=None,
                )
            except Exception:
                return None

        tq_quote = None
        if market == "US":
            tq_quote = _tencent_fetch_quote(symbol, market)

            # For US, prefer Tencent quote for OHLC/volume/amount fields (AkShare US spot often has mismatched units/columns).
            if tq_quote is not None and tq_quote.price is not None:
                mc = _yfinance_market_cap_us(symbol)
                if mc is not None and mc > 0:
                    tq_quote.market_cap = mc
                return tq_quote

            yf_q = _yfinance_quote_us(symbol)
            if yf_q is not None:
                return yf_q

        df = _get_stock_spot_data(market)
        if df is None or df.empty:
            base = tq_quote or _tencent_fetch_quote(symbol, market)
            if base is None:
                return None
            if market == "US":
                mc = _yfinance_market_cap_us(symbol)
                if mc is not None and mc > 0:
                    base.market_cap = mc
            return base
        
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
            base = tq_quote or _tencent_fetch_quote(symbol, market)
            if base is None:
                return None
            if market == "US":
                mc = _yfinance_market_cap_us(symbol)
                if mc is not None and mc > 0:
                    base.market_cap = mc
            return base

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
        if market == "US":
            amount = None
        elif market == "CN":
            if volume is not None:
                volume = volume * 100

        if market == "US":
            mc = _yfinance_market_cap_us(symbol)
            if mc is not None and mc > 0:
                market_cap = mc
        
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

# Cache history data to reduce external calls (especially yfinance rate limits)
_HISTORY_CACHE: dict[tuple[str, str], tuple[float, "pd.DataFrame"]] = {}


def _rsi14(series):
    import pandas as pd

    s = pd.to_numeric(series, errors="coerce").astype(float)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    period = 14
    # Wilder RSI: first average is SMA over first `period` values, then recursive smoothing.
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    for i in range(period + 1, len(s)):
        if pd.isna(avg_gain.iat[i]) and not pd.isna(avg_gain.iat[i - 1]):
            avg_gain.iat[i] = avg_gain.iat[i - 1]
        if pd.isna(avg_loss.iat[i]) and not pd.isna(avg_loss.iat[i - 1]):
            avg_loss.iat[i] = avg_loss.iat[i - 1]
        if not pd.isna(avg_gain.iat[i - 1]):
            avg_gain.iat[i] = (avg_gain.iat[i - 1] * (period - 1) + gain.iat[i]) / period
        if not pd.isna(avg_loss.iat[i - 1]):
            avg_loss.iat[i] = (avg_loss.iat[i - 1] * (period - 1) + loss.iat[i]) / period

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


def _atr14(df, period: int = 14):
    import pandas as pd

    close = pd.to_numeric(df.get("close"), errors="coerce")
    high = pd.to_numeric(df.get("high"), errors="coerce")
    low = pd.to_numeric(df.get("low"), errors="coerce")

    # Some data sources may not provide high/low reliably; fall back to close.
    try:
        if high is None or high.isna().all():
            high = close
        else:
            high = high.fillna(close)
        if low is None or low.isna().all():
            low = close
        else:
            low = low.fillna(close)
    except Exception:
        pass
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder ATR: first ATR is SMA(period), then recursive smoothing.
    atr = tr.rolling(window=period, min_periods=period).mean()
    for i in range(period + 1, len(tr)):
        if not pd.isna(atr.iat[i - 1]):
            atr.iat[i] = (atr.iat[i - 1] * (period - 1) + tr.iat[i]) / period
    return atr


def _safe_float(v):
    try:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        fv = float(v)
        return fv
    except Exception:
        return None


def _fetch_history_df(symbol: str, market: str):
    import pandas as pd
    import datetime as dt

    global _YF_US_COOLDOWN_UNTIL

    key = ((market or "CN").upper(), (symbol or "").upper())
    now = dt.datetime.utcnow().timestamp()
    ttl_seconds = float((os.environ.get("HISTORY_CACHE_TTL_SECONDS") or "3600").strip() or "3600")
    cached = _HISTORY_CACHE.get(key)
    if cached and (now - float(cached[0])) < ttl_seconds:
        try:
            df0 = cached[1]
            if df0 is not None and not df0.empty:
                return df0.copy()
        except Exception:
            pass

    m = (market or "CN").upper()
    end = dt.date.today()
    start = end - dt.timedelta(days=800)

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
                    "volume": pd.to_numeric(df.get("成交量"), errors="coerce") * 100,
                    "amount": pd.to_numeric(df.get("成交额"), errors="coerce"),
                }
            )
            out = out.dropna(subset=["date"]).sort_values("date")
            if out is not None and not out.empty:
                _HISTORY_CACHE[key] = (now, out)
            return out
        except Exception:
            out = None

        tdf = _tencent_fetch_history_df(symbol, market)
        if tdf is not None and not tdf.empty:
            _HISTORY_CACHE[key] = (now, tdf)
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

        def _is_yf_rate_limited(err_text: str) -> bool:
            s = (err_text or "").lower()
            return "ratelimit" in s or "too many requests" in s or "rate limited" in s

        raw = None
        now_ts = float(now)
        in_cooldown = False
        if m == "US":
            try:
                in_cooldown = float(_YF_US_COOLDOWN_UNTIL or 0.0) > now_ts
            except Exception:
                in_cooldown = False

        if not in_cooldown:
            try:
                raw = yf.download(
                    yf_symbol,
                    start=start.isoformat(),
                    end=(end + dt.timedelta(days=1)).isoformat(),
                    progress=False,
                    threads=False,
                )
            except Exception as e:
                if m == "US" and _is_yf_rate_limited(str(e)):
                    try:
                        _YF_US_COOLDOWN_UNTIL = now_ts + 300.0
                    except Exception:
                        pass
                raw = None

        # yfinance sometimes returns empty on rate limit without raising
        if m == "US" and (raw is None or getattr(raw, "empty", True)):
            try:
                _YF_US_COOLDOWN_UNTIL = max(float(_YF_US_COOLDOWN_UNTIL or 0.0), now_ts + 300.0)
            except Exception:
                pass

        # Fallback: yfinance download sometimes fails but Ticker.history can work.
        # For US, if we are rate-limited, skip this fallback and go straight to Stooq.
        if raw is None or raw.empty:
            try:
                if m == "US" and float(_YF_US_COOLDOWN_UNTIL or 0.0) > now_ts:
                    raw = None
                else:
                    t = yf.Ticker(yf_symbol)
                    raw = t.history(period="2y", interval="1d")
            except Exception:
                raw = None

        if raw is None or raw.empty:
            if m == "US":
                sdf = _stooq_fetch_history_df(symbol)
                if sdf is not None and not sdf.empty:
                    _HISTORY_CACHE[key] = (now, sdf)
                    return sdf

            tdf = _tencent_fetch_history_df(symbol, market)
            if tdf is not None and not tdf.empty:
                _HISTORY_CACHE[key] = (now, tdf)
                return tdf
            return None

        raw = raw.reset_index()
        date_col = "Date" if "Date" in raw.columns else ("index" if "index" in raw.columns else raw.columns[0])
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(raw[date_col], errors="coerce"),
                "open": pd.to_numeric(raw.get("Open"), errors="coerce"),
                "high": pd.to_numeric(raw.get("High"), errors="coerce"),
                "low": pd.to_numeric(raw.get("Low"), errors="coerce"),
                "close": pd.to_numeric(raw.get("Close"), errors="coerce"),
                "volume": pd.to_numeric(raw.get("Volume"), errors="coerce"),
            }
        )
        out = out.dropna(subset=["date"]).sort_values("date")
        out["amount"] = out["close"] * out["volume"]

        def _looks_valid_history(df: "pd.DataFrame") -> bool:
            try:
                if df is None or df.empty:
                    return False
                if len(df) < 120:
                    return False
                c = pd.to_numeric(df.get("close"), errors="coerce").dropna()
                if len(c) < 120:
                    return False
                uniq = int(c.tail(120).nunique(dropna=True))
                if uniq <= 5:
                    return False
                std = float(c.tail(120).std()) if len(c) >= 2 else 0.0
                if std <= 1e-9:
                    return False
                return True
            except Exception:
                return False

        # US: Never use Tencent kline fallback (often returns only 2 bars). Prefer Stooq if yfinance data looks wrong.
        if m == "US" and not _looks_valid_history(out):
            sdf = _stooq_fetch_history_df(symbol)
            if sdf is not None and not sdf.empty and _looks_valid_history(sdf):
                _HISTORY_CACHE[key] = (now, sdf)
                return sdf
            return None

        if out is not None and not out.empty:
            _HISTORY_CACHE[key] = (now, out)
        return out
    except Exception:
        if m == "US":
            sdf = _stooq_fetch_history_df(symbol)
            if sdf is not None and not sdf.empty:
                _HISTORY_CACHE[key] = (now, sdf)
                return sdf
            return None

        tdf = _tencent_fetch_history_df(symbol, market)
        if tdf is not None and not tdf.empty:
            _HISTORY_CACHE[key] = (now, tdf)
            return tdf
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

    # Clean history to avoid NaN tails causing null indicators
    try:
        df = df.dropna(subset=["date", "close"])
        df = df.sort_values("date")
        df = df.drop_duplicates(subset=["date"], keep="last")
    except Exception:
        pass
    if df is None or df.empty:
        return None

    close = pd.to_numeric(df.get("close"), errors="coerce")
    high = pd.to_numeric(df.get("high"), errors="coerce")
    low = pd.to_numeric(df.get("low"), errors="coerce")
    vol = pd.to_numeric(df.get("volume"), errors="coerce")

    close = close.dropna()
    if close.empty:
        return None

    ma5 = close.rolling(window=5, min_periods=1).mean()
    ma20 = close.rolling(window=20, min_periods=1).mean()
    ma60 = close.rolling(window=60, min_periods=1).mean()
    rsi = _rsi14(close)
    dif, dea, hist = _macd(close)

    shift_n = 5
    try:
        shift_n = int(min(5, max(1, len(ma60) - 1)))
    except Exception:
        shift_n = 5
    slope_raw_s = (ma60 - ma60.shift(shift_n)) / float(shift_n)
    slope_pct_s = (slope_raw_s / ma60) * 100

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
    macd_hist_prev = None
    try:
        macd_hist_prev = float(hist.iloc[-2]) if len(hist) >= 2 and pd.notna(hist.iloc[-2]) else None
    except Exception:
        macd_hist_prev = None
    signal_macd_bullish = None
    try:
        macd_ok = False
        if macd_dif is not None and macd_dea is not None and float(macd_dif) > float(macd_dea):
            macd_ok = True
        if macd_hist_prev is not None and macd_hist is not None:
            if float(macd_hist_prev) < 0 <= float(macd_hist):
                macd_ok = True
        signal_macd_bullish = bool(macd_ok)
    except Exception:
        signal_macd_bullish = None

    rsi14 = float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else None
    signal_rsi_overbought = True if (rsi14 is not None and rsi14 > 70) else False if rsi14 is not None else None

    rsi_rebound = None
    try:
        if len(rsi) >= 3:
            rsi_today = rsi.iloc[-1]
            rsi_yesterday = rsi.iloc[-2]
            rsi_before_yesterday = rsi.iloc[-3]
            if pd.notna(rsi_today) and pd.notna(rsi_yesterday) and pd.notna(rsi_before_yesterday):
                is_hook_up = bool(float(rsi_yesterday) < float(rsi_before_yesterday) and float(rsi_today) > float(rsi_yesterday))
                is_low_position = bool(float(rsi_yesterday) < 40)
                rsi_rebound = bool(is_hook_up and is_low_position)
    except Exception:
        rsi_rebound = None

    vol_ma5 = vol.rolling(window=5).mean()
    vol_ma10 = vol.rolling(window=10).mean()
    signal_vol_gt_ma5 = None
    signal_vol_gt_ma10 = None
    if len(vol) >= 6 and pd.notna(vol.iloc[-1]) and pd.notna(vol_ma5.iloc[-2]):
        signal_vol_gt_ma5 = float(vol.iloc[-1]) > float(vol_ma5.iloc[-2])
    if len(vol) >= 11 and pd.notna(vol.iloc[-1]) and pd.notna(vol_ma10.iloc[-2]):
        signal_vol_gt_ma10 = float(vol.iloc[-1]) > float(vol_ma10.iloc[-2])

    last_close = float(close.iloc[-1]) if pd.notna(close.iloc[-1]) else None
    last_open = float(df["open"].astype(float).iloc[-1]) if "open" in df.columns and pd.notna(df["open"].astype(float).iloc[-1]) else None
    last_low = float(low.iloc[-1]) if pd.notna(low.iloc[-1]) else None
    ma5_now = float(ma5.iloc[-1]) if pd.notna(ma5.iloc[-1]) else None
    ma20_now = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None
    ma5_prev = float(ma5.iloc[-2]) if len(ma5) >= 2 and pd.notna(ma5.iloc[-2]) else None
    ma20_prev = float(ma20.iloc[-2]) if len(ma20) >= 2 and pd.notna(ma20.iloc[-2]) else None

    price_up = None
    try:
        if len(close) >= 2 and pd.notna(close.iloc[-2]) and last_close is not None:
            price_up = bool(last_close > float(close.iloc[-2]))
    except Exception:
        price_up = None

    vol_ok = None
    try:
        if (signal_vol_gt_ma5 is not None or signal_vol_gt_ma10 is not None) and (price_up is not None):
            vol_ok = bool(price_up is True and (signal_vol_gt_ma5 or signal_vol_gt_ma10))
        else:
            vol_ok = None
    except Exception:
        vol_ok = None

    ma20_up = None
    try:
        if ma20_now is not None and ma20_prev is not None:
            ma20_up = bool(ma20_now > ma20_prev)
    except Exception:
        ma20_up = None

    slope_raw = None
    slope_pct = None
    trend = None
    slope_advice = None
    try:
        sraw_valid = slope_raw_s.dropna()
        spct_valid = slope_pct_s.dropna()
        slope_raw = float(sraw_valid.iloc[-1]) if not sraw_valid.empty else None
        slope_pct = float(spct_valid.iloc[-1]) if not spct_valid.empty else None

        # If history is too short, slope_* at last point may be NaN; degrade to 0.
        if slope_raw is None or slope_pct is None:
            slope_raw = 0.0
            slope_pct = 0.0

        # 趋势：斜率大于 0 = 上涨；约等于 0 = 观望；小于 0 = 下跌
        eps = 0.02
        if slope_pct is None:
            trend = None
        elif abs(slope_pct) <= eps:
            trend = "观望"
        elif slope_pct > 0:
            trend = "上涨"
        else:
            trend = "下跌"

        # Slope 率建议：
        # - Slope% ≈ 0%：不要买
        # - 0% ~ 0.1%：小心买
        # - 0.2% ~ 0.3%：放心买
        # - 0.4%+：有危险
        if slope_pct is None:
            slope_advice = None
        elif abs(slope_pct) <= eps:
            slope_advice = "不要买"
        elif slope_pct < 0:
            slope_advice = "不要买"
        elif 0 < slope_pct < 0.1:
            slope_advice = "小心买"
        elif 0.2 <= slope_pct <= 0.3:
            slope_advice = "放心买"
        elif slope_pct >= 0.4:
            slope_advice = "有危险"
        else:
            slope_advice = "小心买"
    except Exception:
        slope_raw = None
        slope_pct = None
        trend = None
        slope_advice = None

    atr14_s = None
    atr14 = None
    try:
        atr14_s = _atr14(df, period=14)
        if atr14_s is not None and not atr14_s.empty:
            av = atr14_s.dropna()
            atr14 = float(av.iloc[-1]) if not av.empty else None
        if atr14 is None:
            atr14 = 0.0
    except Exception:
        atr14 = None

    pe_ratio = None
    try:
        m = (market or "CN").upper()

        def _find_pe_column(cols: list[str]) -> str | None:
            try:
                for c in cols:
                    if not isinstance(c, str):
                        continue
                    if "市盈率" in c:
                        return c
                for c in cols:
                    if not isinstance(c, str):
                        continue
                    cl = c.lower()
                    if "pe" == cl or "pe_ttm" in cl or "pettm" in cl or "pe(ttm" in cl or "pe (ttm" in cl:
                        return c
                    if "pe" in cl and "ratio" in cl:
                        return c
                for c in cols:
                    if not isinstance(c, str):
                        continue
                    if "PE" in c:
                        return c
            except Exception:
                return None
            return None

        if m in {"US", "HK"}:
            disable_proxies_for_process()
            import yfinance as yf

            yf_symbol = symbol
            if m == "HK" and not yf_symbol.upper().endswith(".HK"):
                base = yf_symbol.replace(".HK", "")
                yf_symbol = f"{base.zfill(4)}.HK" if base.isdigit() else f"{base}.HK"
            t = yf.Ticker(yf_symbol)
            info = {}
            fast = getattr(t, "fast_info", None) or {}
            try:
                info = t.info or {}
            except Exception:
                info = {}
            pe_ratio = _safe_float(
                fast.get("trailing_pe")
                or fast.get("trailingPE")
                or info.get("trailingPE")
                or info.get("forwardPE")
            )
            if pe_ratio is None and m in {"US", "HK"}:
                try:
                    disable_proxies_for_process()
                    import akshare as ak

                    spot = ak.stock_us_spot_em() if m == "US" else ak.stock_hk_spot_em()
                    if spot is not None and not spot.empty:
                        code_col = None
                        for c in ("代码", "symbol", "Symbol"):
                            if c in spot.columns:
                                code_col = c
                                break
                        if code_col:
                            base = (symbol or "").split(".", 1)[0].upper()
                            if m == "HK":
                                base = base.replace(".HK", "")
                                base = base.zfill(5) if base.isdigit() else base
                            hit = spot[spot[code_col].astype(str).str.upper() == base]
                            if not hit.empty:
                                row = hit.iloc[0]
                                pe_col = _find_pe_column([str(c) for c in list(spot.columns)])
                                if pe_col and pe_col in spot.columns:
                                    pe_ratio = _safe_float(row.get(pe_col))
                except Exception:
                    pe_ratio = None

            # Fallback: Tencent quote contains PE fields and is usually reachable.
            if pe_ratio is None:
                try:
                    pe_ratio = _safe_float(_tencent_fetch_pe_ratio(symbol, m))
                except Exception:
                    pe_ratio = None
        elif m == "CN":
            disable_proxies_for_process()
            import akshare as ak

            code = symbol.split(".")[0]
            try:
                pe_df = ak.stock_a_indicator_lg(symbol=code)
                if pe_df is not None and not pe_df.empty:
                    last = pe_df.iloc[-1]
                    for k in ["pe_ttm", "市盈率TTM", "市盈率(动)", "pe"]:
                        if k in pe_df.columns:
                            pe_ratio = _safe_float(last.get(k))
                            if pe_ratio is not None:
                                break
            except Exception:
                pe_ratio = None

            if pe_ratio is None:
                try:
                    spot = ak.stock_zh_a_spot_em()
                    if spot is not None and not spot.empty:
                        code_col = None
                        for c in ("代码", "symbol", "Symbol"):
                            if c in spot.columns:
                                code_col = c
                                break
                        if code_col:
                            base = (symbol or "").split(".", 1)[0].upper()
                            hit = spot[spot[code_col].astype(str).str.upper() == base]
                            if not hit.empty:
                                row = hit.iloc[0]
                                pe_col = _find_pe_column([str(c) for c in list(spot.columns)])
                                if pe_col and pe_col in spot.columns:
                                    pe_ratio = _safe_float(row.get(pe_col))
                except Exception:
                    pe_ratio = None

            if pe_ratio is None:
                try:
                    pe_ratio = _safe_float(_tencent_fetch_pe_ratio(symbol, m))
                except Exception:
                    pe_ratio = None
    except Exception:
        pe_ratio = None

    aggressive_ok = None
    stable_ok = None
    try:
        approx_ma20 = False
        if last_close is not None and ma20_now not in (None, 0):
            approx_ma20 = bool(abs(float(last_close) - float(ma20_now)) / max(abs(float(ma20_now)), 1e-9) <= 0.02)

        ma60_now = float(ma60.iloc[-1]) if ma60 is not None and pd.notna(ma60.iloc[-1]) else None

        # 买入价位：
        # 1) 买入价格(当前价) > MA60
        # 2) MA60 趋势向上：Slope% > 0
        # 3) 买入价格约等于 MA20
        # 4) RSI Rebound：RSI 昨日 < 前日 且 今日 > 昨日，且昨日 < 40
        buy_gt_ma60 = bool(last_close is not None and ma60_now is not None and float(last_close) > float(ma60_now))
        ma60_up = bool(slope_pct is not None and float(slope_pct) > 0)
        aggressive_ok = bool(buy_gt_ma60 and ma60_up and approx_ma20 and bool(rsi_rebound))
        stable_ok = None
    except Exception:
        aggressive_ok = None
        stable_ok = None

    buy_reason = None
    try:
        if aggressive_ok is True:
            buy_reason = "买入>MA60 且 MA60上行，买入≈MA20，RSI出现低位拐头"
        elif aggressive_ok is False:
            buy_reason = "条件未满足"
    except Exception:
        buy_reason = None

    sell_ok = None
    sell_price = None
    sell_reason = None
    try:
        reference_buy_price = float(last_close) if (aggressive_ok is True and last_close is not None) else None
        take_profit = False
        price_break_ma20 = False
        rsi_divergence = False
        stop_loss_trigger = False
        stop_line = None

        if last_close is not None and ma20_now is not None:
            price_break_ma20 = bool(float(last_close) < float(ma20_now))

        if rsi14 is not None and float(rsi14) > 70:
            take_profit = True
            try:
                win = min(20, len(close) - 1)
                if win >= 10:
                    prev_close_win = close.iloc[-(win + 1):-1]
                    prev_rsi_win = rsi.iloc[-(win + 1):-1]
                    prev_max_close = float(pd.to_numeric(prev_close_win, errors="coerce").max()) if not prev_close_win.empty else None
                    prev_max_rsi = float(pd.to_numeric(prev_rsi_win, errors="coerce").max()) if not prev_rsi_win.empty else None
                    if prev_max_close is not None and prev_max_rsi is not None and last_close is not None:
                        rsi_divergence = bool(float(last_close) > prev_max_close and float(rsi14) < prev_max_rsi)
            except Exception:
                rsi_divergence = False

        # 止损：买入价 - 2×ATR
        # 在“股票信息”页：用计算出来的买入价位（buy_price_aggressive=当前价）作为参考买入价
        if reference_buy_price is not None and atr14 is not None and last_close is not None:
            stop_line = float(reference_buy_price) - 2 * float(atr14)
            stop_loss_trigger = bool(float(last_close) <= float(stop_line))

        # 卖出价位：
        # - 参考止损线：买入价 - 2×ATR
        # - 参考止盈线：MA20（跌破则认为短期趋势结束）
        # sell_ok 仍表示“是否触发卖出条件”，sell_price 改为“参考卖出价位”（优先止损线，其次 MA20，其次现价）。
        sell_ok = bool((take_profit and rsi_divergence) or price_break_ma20 or stop_loss_trigger)
        if stop_line is not None:
            sell_price = float(stop_line)
        elif ma20_now is not None:
            sell_price = float(ma20_now)
        else:
            sell_price = float(last_close) if last_close is not None else None

        if sell_ok is True:
            if stop_loss_trigger:
                sell_reason = f"止损：跌破 买入价-2×ATR（止损线≈{stop_line:.3f}）"
            elif price_break_ma20:
                sell_reason = "止盈：跌破 MA20（短期趋势结束）"
            elif take_profit and rsi_divergence:
                sell_reason = "止盈：RSI>70 且顶背离"
            else:
                sell_reason = "触发卖出条件"
    except Exception:
        sell_ok = None
        sell_price = None
        sell_reason = None

    # 买入价位：输出为“参考买入价位”，默认用 MA20（更贴近回调买点）；若不可用则回退现价。
    # buy_price_aggressive_ok 仍表示是否满足当前策略的强条件。
    buy_price_aggressive = float(ma20_now) if ma20_now is not None else (float(last_close) if last_close is not None else None)
    buy_price_stable = float(ma60_now) if 'ma60_now' in locals() and ma60_now is not None else None

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
                market_cap = (
                    info.get("market_cap")
                    or info.get("marketCap")
                    or (t.info or {}).get("marketCap")
                )
                if market_cap is not None:
                    market_cap = float(market_cap)
            except Exception:
                market_cap = None
            try:
                currency = (t.info or {}).get("currency") or currency
            except Exception:
                pass
        except Exception:
            pass

    if market_cap is None and market.upper() in {"HK"}:
        tq = _tencent_fetch_quote(symbol, market)
        if tq is not None:
            if name is None and tq.name:
                name = tq.name
            if tq.market_cap is not None:
                market_cap = tq.market_cap

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
        slope_raw=slope_raw,
        slope_pct=slope_pct,
        trend=trend,
        slope_advice=slope_advice,
        pe_ratio=pe_ratio,
        atr14=atr14,
        rsi14=rsi14,
        rsi_rebound=rsi_rebound,
        macd_dif=macd_dif,
        macd_dea=macd_dea,
        macd_hist=macd_hist,
        buy_price_aggressive=buy_price_aggressive,
        buy_price_stable=buy_price_stable,
        sell_price=sell_price,

        buy_reason=buy_reason,
        sell_reason=sell_reason,

        buy_price_aggressive_ok=aggressive_ok,
        buy_price_stable_ok=stable_ok,
        sell_price_ok=sell_ok,
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
            if r.source_type not in {"file_upload", "market_fetch"}:
                raise HTTPException(status_code=400, detail="仅支持对上传文件/市场数据报告重新分析")

            r.status = "running"
            r.error_message = None
            r.updated_at = int(time.time())

            source_type = (r.source_type or "").strip()
            meta = {}
            try:
                meta = json.loads(r.source_meta or "{}")
            except Exception:
                meta = {}

        if source_type == "file_upload":
            pdf_path = (meta.get("upload_saved_path") or "").strip()
            if not pdf_path:
                raise HTTPException(status_code=400, detail="未找到上传文件路径，无法重新分析")
            threading.Thread(target=run_pdf_analysis_in_background, args=(report_id, pdf_path), daemon=True).start()
            return {"report_id": report_id, "status": "running", "message": "已开始重新分析（上传文件）"}

        threading.Thread(target=run_analysis_in_background, args=(report_id,), daemon=True).start()
        return {"report_id": report_id, "status": "running", "message": "已开始重新分析（市场数据）"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")


def run_analysis_in_background(report_id: str):
    """Run analysis in background thread."""
    try:
        disable_proxies_for_process()
        ingest_and_analyze_market_fetch(report_id)
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
        
        acquired = _PDF_ANALYSIS_SEM.acquire(blocking=False)
        if not acquired:
            with session_scope() as s:
                r = s.get(Report, report_id)
                if r:
                    r.status = "pending"
                    r.error_message = "解析任务排队中"
                    r.updated_at = int(time.time())
            _PDF_ANALYSIS_SEM.acquire()

        try:
            def _run_with_hard_timeout(path: str, use_ai: bool, force_ai: bool, timeout_seconds: float):
                max_mem_mb = int((os.environ.get("PDF_ANALYSIS_MAX_MEM_MB") or "1024").strip() or "1024")
                cpu_seconds = int((os.environ.get("PDF_ANALYSIS_MAX_CPU_SECONDS") or "180").strip() or "180")

                # IMPORTANT: use 'spawn' to avoid fork-from-thread deadlocks
                ctx = multiprocessing.get_context("spawn")
                parent_conn, child_conn = ctx.Pipe(duplex=False)
                p = ctx.Process(
                    target=_pdf_extract_worker,
                    args=(child_conn, path, use_ai, force_ai, max_mem_mb, cpu_seconds),
                )
                p.start()
                try:
                    child_conn.close()
                except Exception:
                    pass
                p.join(timeout_seconds)
                if p.is_alive():
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    try:
                        p.join(5)
                    except Exception:
                        pass
                    raise RuntimeError("pdf_extract_timeout")

                try:
                    if not parent_conn.poll(2.0):
                        try:
                            code = p.exitcode
                        except Exception:
                            code = None
                        raise RuntimeError(f"pdf_extract_failed exitcode={code}")
                    payload = parent_conn.recv()
                finally:
                    try:
                        parent_conn.close()
                    except Exception:
                        pass
                if not isinstance(payload, dict):
                    raise RuntimeError("pdf_extract_failed")
                if payload.get("ok") is True:
                    return payload.get("data")
                err = (payload.get("error") or "").strip()
                if not err:
                    err = "pdf_extract_failed"
                tb = (payload.get("traceback") or "").strip()
                if tb:
                    err = f"{err}; tb={tb[:800]}"
                raise RuntimeError(err)

            base_timeout = float((os.environ.get("PDF_EXTRACT_TIMEOUT_SECONDS") or "240").strip() or "240")
            ai_timeout = float((os.environ.get("PDF_AI_TIMEOUT_SECONDS") or "600").strip() or "600")
            enable_ai = (os.environ.get("ENABLE_PDF_AI") or "1").strip() != "0"
            # Default: do NOT force AI-only. AI-only sets force_ai=True which switches text extractor
            # to fast_only mode and can bypass OCR, causing scanned PDFs to extract nothing.
            force_ai_env = (os.environ.get("FORCE_PDF_AI") or "0").strip() == "1"
            has_key = bool((os.environ.get("DASHSCOPE_API_KEY") or "").strip())

            financials = None
            non_ai_err = None
            ai_err = None

            # FORCE_PDF_AI=1 means AI-only.
            if force_ai_env:
                if not enable_ai or not has_key:
                    raise RuntimeError("ai_required_no_api_key")
                financials = _run_with_hard_timeout(
                    pdf_path,
                    use_ai=True,
                    force_ai=True,
                    timeout_seconds=ai_timeout,
                )
            else:
                # Try non-AI first. If it fails, allow AI to rescue.
                try:
                    financials = _run_with_hard_timeout(pdf_path, use_ai=False, force_ai=False, timeout_seconds=base_timeout)
                except Exception as e:
                    non_ai_err = str(e)

                if enable_ai and has_key:
                    try:
                        financials_ai = _run_with_hard_timeout(
                            pdf_path,
                            use_ai=True,
                            force_ai=False,
                            timeout_seconds=ai_timeout,
                        )
                        if financials_ai is not None:
                            financials = financials_ai
                    except Exception as e:
                        ai_err = str(e)

            if financials is None:
                raise RuntimeError(f"pdf_extract_failed non_ai={non_ai_err} ai={ai_err}")
        finally:
            try:
                _PDF_ANALYSIS_SEM.release()
            except Exception:
                pass
        
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
            from core.pdf_analyzer import compute_metrics_from_extracted

            computed = compute_metrics_from_extracted(financials) or {}

            def _is_pct_code(code: str) -> bool:
                return code in {"GROSS_MARGIN", "NET_MARGIN", "ROE", "ROA", "DEBT_ASSET"}

            def _is_reasonable(code: str, v: float | None) -> bool:
                try:
                    if v is None:
                        return False
                    fv = float(v)
                    if code in {"GROSS_MARGIN", "NET_MARGIN"}:
                        return -50.0 <= fv <= 100.0
                    if code in {"ROE", "ROA"}:
                        return -200.0 <= fv <= 500.0
                    if code in {"DEBT_ASSET"}:
                        return -50.0 <= fv <= 200.0
                    if _is_pct_code(code):
                        return -200.0 <= fv <= 500.0
                    if code in {"CURRENT_RATIO", "QUICK_RATIO"}:
                        return 0.0 <= fv <= 50.0
                    if code in {"ASSET_TURNOVER", "INVENTORY_TURNOVER", "RECEIVABLE_TURNOVER"}:
                        return 0.0 <= fv <= 1000.0
                    return True
                except Exception:
                    return False

            metric_meta: dict[str, tuple[str, str]] = {
                "GROSS_MARGIN": ("毛利率", "%"),
                "NET_MARGIN": ("净利率", "%"),
                "ROE": ("ROE (净资产收益率)", "%"),
                "ROA": ("ROA (总资产收益率)", "%"),
                "CURRENT_RATIO": ("流动比率", ""),
                "QUICK_RATIO": ("速动比率", ""),
                "DEBT_ASSET": ("资产负债率", "%"),
                "EQUITY_RATIO": ("产权比率", ""),
                "ASSET_TURNOVER": ("总资产周转率", ""),
                "INVENTORY_TURNOVER": ("存货周转率", ""),
                "RECEIVABLE_TURNOVER": ("应收账款周转率", ""),
            }

            metrics_to_save: list[tuple[str, str, float, str]] = []
            for code, (name, unit) in metric_meta.items():
                v = computed.get(code)
                if _is_reasonable(code, v):
                    metrics_to_save.append((code, name, float(v), unit))

            raw_metric_meta: dict[str, tuple[str, str, float | None]] = {
                "IS.REVENUE": ("营业收入", "", financials.revenue),
                "IS.NET_PROFIT": ("净利润", "", financials.net_profit),
                "BS.ASSET_TOTAL": ("资产总计", "", financials.total_assets),
                "BS.LIAB_TOTAL": ("负债合计", "", financials.total_liabilities),
                "BS.EQUITY_TOTAL": ("所有者权益合计", "", financials.total_equity),
                "BS.CASH": ("货币资金", "", financials.cash),
            }
            for code, (name, unit, v) in raw_metric_meta.items():
                if v is None:
                    continue
                if _is_reasonable(code, v):
                    metrics_to_save.append((code, name, float(v), unit))

            # If ratio metrics are still empty but we extracted some raw amounts, do not hard-fail.
            raw_fields = [
                financials.revenue,
                financials.net_profit,
                financials.total_assets,
                financials.total_liabilities,
                financials.total_equity,
            ]
            has_some_raw = any(v is not None for v in raw_fields)

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

            if metrics_to_save or has_some_raw:
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
                if "pdf_extract_timeout" in msg:
                    r.error_message = "PDF 解析超时（可能是扫描版/内容过大/OCR或AI耗时）。请稍后重试或更换更清晰的 PDF。"
                elif "ai_required_no_api_key" in msg or "missing_api_key" in msg:
                    r.error_message = "AI-only 解析需要配置 DASHSCOPE_API_KEY（千问）。请先配置后重试。"
                else:
                    r.error_message = f"PDF解析失败: {msg}"
                r.updated_at = int(time.time())


@app.post("/api/reports/upload")
async def upload_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_name: str = Form(""),
    market: str = Form(""),
    symbol: str = Form(""),
    period_type: str = Form("annual"),
    period_end: str = Form(None),
):
    """Upload a financial report file."""
    try:
        filename_in = file.filename or "upload"
        try:
            saved_path = save_uploaded_file_stream(filename=filename_in, fileobj=file.file, max_bytes=_MAX_UPLOAD_BYTES)
        except ValueError as e:
            if "upload_too_large" in str(e):
                raise HTTPException(status_code=413, detail="上传文件过大")
            raise
        
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
        
        symbol_in = (symbol or "").strip()
        market_in = (market or "").strip()
        symbol_norm = None
        market_norm = None
        company_id = None
        industry_code = None

        # Optional: bind upload to a company if user provides market+symbol.
        if symbol_in:
            try:
                market_norm = normalize_market(market_in or "CN")
                symbol_norm = normalize_symbol(market_norm, symbol_in)

                if final_company == "待识别" and symbol_norm:
                    report_name = f"{symbol_norm} - {decoded_filename}"

                try:
                    mkt = (market_norm or "CN").upper()
                    if mkt in {"US", "HK"}:
                        disable_proxies_for_process()
                        import yfinance as yf

                        yf_symbol = symbol_norm
                        if mkt == "HK" and not yf_symbol.upper().endswith(".HK"):
                            base = yf_symbol.replace(".HK", "")
                            yf_symbol = f"{base.zfill(4)}.HK" if base.isdigit() else f"{base}.HK"
                        t = yf.Ticker(yf_symbol)
                        info = {}
                        try:
                            info = t.info or {}
                        except Exception:
                            info = {}
                        industry_code = (info.get("industry") or info.get("sector") or None)
                    elif mkt == "CN":
                        disable_proxies_for_process()
                        import akshare as ak

                        code = symbol_norm.split(".")[0]
                        try:
                            idf = ak.stock_individual_info_em(symbol=code)
                            if idf is not None and not idf.empty and "item" in idf.columns and "value" in idf.columns:
                                row = idf[idf["item"].astype(str).str.contains("行业", na=False)]
                                if not row.empty:
                                    industry_code = str(row.iloc[0]["value"]).strip() or None
                        except Exception:
                            industry_code = None
                except Exception:
                    industry_code = None

                display_name = final_company if final_company != "待识别" else symbol_norm
                company_id = upsert_company(market=market_norm, symbol=symbol_norm, name=display_name, industry_code=industry_code)
            except Exception:
                symbol_norm = None
                market_norm = None
                company_id = None

        meta = {
            "upload_company_name": final_company,
            "upload_filename": file.filename,
            "upload_filetype": filetype,
            "upload_saved_path": str(saved_path),
            "upload_market": market_norm,
            "upload_symbol": symbol_norm,
            "upload_company_id": company_id,
        }
        
        # Create report record
        report_id = upsert_report_file_upload(
            upload_company_name=final_company,
            report_name=report_name,
            period_type=period_type,
            period_end=period_end,
            source_meta=meta,
        )

        # Bind report to company if available.
        if company_id:
            try:
                with session_scope() as s:
                    r = s.get(Report, report_id)
                    if r:
                        r.company_id = company_id
                        r.market = market_norm
                        r.updated_at = int(time.time())
            except Exception:
                pass

        if filetype != "pdf":
            with session_scope() as s:
                r = s.get(Report, report_id)
                if r:
                    r.status = "failed"
                    r.error_message = "仅支持上传 PDF 文件进行解析"
                    r.updated_at = int(time.time())
            return {"report_id": report_id, "message": "上传成功，但仅支持PDF解析", "status": "failed"}

        with session_scope() as s:
            r = s.get(Report, report_id)
            if r:
                r.status = "running"
                r.error_message = None
                r.updated_at = int(time.time())

        threading.Thread(target=run_pdf_analysis_in_background, args=(report_id, str(saved_path)), daemon=True).start()

        return {"report_id": report_id, "message": "上传成功，正在分析中", "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.post("/api/reports/fetch")
def fetch_market_report(
    background_tasks: BackgroundTasks,
    symbol: str,
    market: str = "CN",
    company_name: str | None = None,
    period_type: str = "annual",
    period_end: str = "2024-12-31",
):
    """Fetch financial report from market data and start analysis."""
    try:
        disable_proxies_for_process()
        
        # Normalize symbol
        symbol_norm = normalize_symbol(market, symbol)

        display_name = (company_name or "").strip() or symbol_norm

        industry_code = None
        try:
            mkt = (market or "CN").upper()
            if mkt in {"US", "HK"}:
                disable_proxies_for_process()
                import yfinance as yf

                yf_symbol = symbol_norm
                if mkt == "HK" and not yf_symbol.upper().endswith(".HK"):
                    base = yf_symbol.replace(".HK", "")
                    yf_symbol = f"{base.zfill(4)}.HK" if base.isdigit() else f"{base}.HK"
                t = yf.Ticker(yf_symbol)
                info = {}
                try:
                    info = t.info or {}
                except Exception:
                    info = {}
                industry_code = (info.get("industry") or info.get("sector") or None)
            elif mkt == "CN":
                disable_proxies_for_process()
                import akshare as ak

                code = symbol_norm.split(".")[0]
                try:
                    idf = ak.stock_individual_info_em(symbol=code)
                    if idf is not None and not idf.empty and "item" in idf.columns and "value" in idf.columns:
                        row = idf[idf["item"].astype(str).str.contains("行业", na=False)]
                        if not row.empty:
                            industry_code = str(row.iloc[0]["value"]).strip() or None
                except Exception:
                    industry_code = None
        except Exception:
            industry_code = None
        
        # Create company record
        company_id = upsert_company(market=market, symbol=symbol_norm, name=display_name, industry_code=industry_code)
        
        # Create report record
        report_id = upsert_report_market_fetch(
            company_id=company_id,
            report_name=f"{display_name} {period_end}",
            market=market,
            period_type=period_type,
            period_end=period_end,
            source_meta={"symbol": symbol_norm, "market": market, "company_name": display_name},
        )
        
        # Start analysis in background
        threading.Thread(target=run_analysis_in_background, args=(report_id,), daemon=True).start()
        
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
