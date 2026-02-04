from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select

from core.db import session_scope
from core.models import Alert, Company, ComputedMetric, Job, Report, Statement, StatementItem, Watchlist
from core.stock_search import normalize_symbol


@dataclass(frozen=True)
class ReportSummary:
    id: str
    report_name: str
    source_type: str
    period_type: str
    period_end: str
    status: str
    created_at: int
    updated_at: int


def normalize_market(market: str) -> str:
    m = (market or "").strip().upper()
    if m in {"A股", "CN", "A"}:
        return "CN"
    if m in {"港股", "HK"}:
        return "HK"
    if m in {"美股", "US"}:
        return "US"
    return m or "CN"


def build_company_id(market: str, symbol: str) -> str:
    return f"{normalize_market(market)}:{symbol.strip().upper()}"


def upsert_company(
    *,
    market: str,
    symbol: str,
    name: str | None = None,
    currency: str | None = None,
    industry_code: str | None = None,
) -> str:
    market_norm = normalize_market(market)
    symbol_norm = normalize_symbol(market_norm, symbol)
    company_id = build_company_id(market_norm, symbol_norm)

    with session_scope() as s:
        existing = s.get(Company, company_id)
        now = int(time.time())
        if existing:
            if name:
                existing.name = name
            if currency:
                existing.currency = currency
            if industry_code:
                existing.industry_code = industry_code
            existing.updated_at = now
            return existing.id

        c = Company(
            id=company_id,
            market=market_norm,
            symbol=symbol_norm,
            name=name,
            currency=currency,
            industry_code=industry_code,
            created_at=now,
            updated_at=now,
        )
        s.add(c)
        return c.id


def build_report_natural_key_market_fetch(company_id: str, period_type: str, period_end: str) -> str:
    return f"{company_id}|{period_type}|{period_end}|market_fetch"


def build_report_natural_key_file_upload(upload_company_name: str, period_type: str, period_end: str) -> str:
    return f"{upload_company_name.strip()}|{period_type}|{period_end}|file_upload"


def delete_report_children(report_id: str) -> None:
    with session_scope() as s:
        s.execute(delete(Alert).where(Alert.report_id == report_id))
        s.execute(delete(ComputedMetric).where(ComputedMetric.report_id == report_id))
        s.execute(delete(StatementItem).where(StatementItem.report_id == report_id))
        s.execute(delete(Statement).where(Statement.report_id == report_id))
        s.execute(delete(Job).where(Job.report_id == report_id))


def upsert_report_market_fetch(
    *,
    company_id: str,
    report_name: str,
    market: str,
    period_type: str,
    period_end: str,
    source_meta: dict,
) -> str:
    natural_key = build_report_natural_key_market_fetch(company_id, period_type, period_end)
    now = int(time.time())

    with session_scope() as s:
        stmt = select(Report).where(Report.natural_key == natural_key)
        existing = s.execute(stmt).scalars().first()

        if existing:
            delete_report_children(existing.id)
            existing.company_id = company_id
            existing.report_name = report_name
            existing.source_meta = json.dumps(source_meta, ensure_ascii=False)
            existing.market = normalize_market(market)
            existing.period_type = period_type
            existing.period_end = period_end
            existing.status = "pending"
            existing.error_message = None
            existing.updated_at = now
            return existing.id

        r = Report(
            id=str(uuid.uuid4()),
            natural_key=natural_key,
            company_id=company_id,
            report_name=report_name,
            source_type="market_fetch",
            source_meta=json.dumps(source_meta, ensure_ascii=False),
            market=normalize_market(market),
            period_type=period_type,
            period_start=None,
            period_end=period_end,
            status="pending",
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        s.add(r)
        return r.id


def upsert_report_file_upload(
    *,
    upload_company_name: str,
    report_name: str,
    period_type: str,
    period_end: str,
    source_meta: dict,
) -> str:
    # IMPORTANT: for file uploads we should not overwrite previous reports.
    # Users may upload multiple versions for the same company/period.
    # Use a unique natural_key suffix so every upload is persisted.
    natural_key = build_report_natural_key_file_upload(upload_company_name, period_type, period_end)
    natural_key = f"{natural_key}|{uuid.uuid4()}"
    now = int(time.time())

    with session_scope() as s:
        r = Report(
            id=str(uuid.uuid4()),
            natural_key=natural_key,
            company_id=None,
            report_name=report_name,
            source_type="file_upload",
            source_meta=json.dumps(source_meta, ensure_ascii=False),
            market=None,
            period_type=period_type,
            period_start=None,
            period_end=period_end,
            status="pending",
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        s.add(r)
        return r.id


def list_reports(limit: int = 50) -> list[ReportSummary]:
    with session_scope() as s:
        stmt = (
            select(
                Report.id,
                Report.report_name,
                Report.source_type,
                Report.period_type,
                Report.period_end,
                Report.status,
                Report.created_at,
                Report.updated_at,
            )
            .order_by(Report.updated_at.desc())
            .limit(limit)
        )
        rows = s.execute(stmt).all()
        return [
            ReportSummary(
                id=r[0],
                report_name=r[1],
                source_type=r[2],
                period_type=r[3],
                period_end=r[4],
                status=r[5],
                created_at=r[6],
                updated_at=r[7],
            )
            for r in rows
        ]


def get_report(report_id: str) -> Report | None:
    with session_scope() as s:
        return s.get(Report, report_id)


def update_report_status(report_id: str, status: str, error_message: str | None = None) -> None:
    with session_scope() as s:
        r = s.get(Report, report_id)
        if not r:
            return
        r.status = status
        r.error_message = error_message
        r.updated_at = int(time.time())


def add_to_watchlist(company_id: str, market: str, note: str | None = None) -> None:
    with session_scope() as s:
        stmt = select(Watchlist).where(Watchlist.company_id == company_id)
        existing = s.execute(stmt).scalars().first()
        now = int(time.time())
        if existing:
            existing.market = normalize_market(market)
            existing.note = note
            existing.updated_at = now
            return

        s.add(
            Watchlist(
                company_id=company_id,
                market=normalize_market(market),
                note=note,
                created_at=now,
                updated_at=now,
            )
        )


def list_watchlist() -> list[Watchlist]:
    with session_scope() as s:
        stmt = select(Watchlist).order_by(Watchlist.updated_at.desc())
        return list(s.execute(stmt).scalars().all())
