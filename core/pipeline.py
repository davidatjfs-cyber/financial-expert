from __future__ import annotations

import json
import time
import uuid

import pandas as pd
from sqlalchemy import delete, select

from core.a_share import fetch_a_share_financials, row_payload
from core.analysis import STANDARD_ITEM_NAMES, dumps, risk_p0, compute_p0_metrics
from core.db import session_scope
from core.models import Alert, ComputedMetric, Report, Statement, StatementItem
from core.net import disable_proxies_for_process
from core.stock_search import normalize_symbol
from core.repository import upsert_company


PROFIT_MAP = {
    "IS.REVENUE": ("OPERATE_INCOME", "营业收入"),
    "IS.COGS": ("OPERATE_COST", "营业成本"),
    "IS.NET_PROFIT": ("PARENT_NETPROFIT", "净利润"),
    "IS.SELLING_EXP": ("SALE_EXPENSE", "销售费用"),
    "IS.GA_EXP": ("MANAGE_EXPENSE", "管理费用"),
    "IS.FIN_EXP": ("FINANCE_EXPENSE", "财务费用"),
    "BS.DEBT_INTEREST": (None, "有息负债"),
}

BALANCE_MAP = {
    "BS.CASH": ("MONETARYFUNDS", "货币资金"),
    "BS.AR": ("ACCOUNTS_RECE", "应收账款"),
    "BS.INVENTORY": ("INVENTORY", "存货"),
    "BS.CA_TOTAL": ("TOTAL_CURRENT_ASSETS", "流动资产合计"),
    "BS.CL_TOTAL": ("TOTAL_CURRENT_LIAB", "流动负债合计"),
    "BS.ASSET_TOTAL": ("TOTAL_ASSETS", "资产总计"),
    "BS.LIAB_TOTAL": ("TOTAL_LIABILITIES", "负债合计"),
    "BS.EQUITY_TOTAL": ("TOTAL_PARENT_EQUITY", "所有者权益合计"),
}

CASH_MAP = {
    "CF.CFO": ("NETCASH_OPERATE", "经营活动现金流净额"),
}


def _period_end_from_row(row: pd.Series) -> str:
    dt = row.get("REPORT_DATE")
    if isinstance(dt, pd.Timestamp):
        return dt.date().isoformat()
    return str(dt)[:10]


def _safe_float(v) -> float | None:
    try:
        if v is None:
            return None
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def delete_report_children_full(report_id: str) -> None:
    with session_scope() as s:
        s.execute(delete(Alert).where(Alert.report_id == report_id))
        s.execute(delete(ComputedMetric).where(ComputedMetric.report_id == report_id))
        s.execute(delete(StatementItem).where(StatementItem.report_id == report_id))
        s.execute(delete(Statement).where(Statement.report_id == report_id))


def ingest_and_analyze_a_share(report_id: str) -> None:
    disable_proxies_for_process()
    with session_scope() as s:
        r = s.get(Report, report_id)
        if not r:
            raise ValueError("report not found")
        if not r.company_id:
            raise ValueError("A股报告缺少 company_id")

        company_id = r.company_id
        period_type = r.period_type
        period_end = r.period_end

        symbol = company_id.split(":", 1)[1]
        symbol = normalize_symbol("CN", symbol)

        r.status = "running"
        r.error_message = None
        r.updated_at = int(time.time())

    delete_report_children_full(report_id)

    fin = fetch_a_share_financials(symbol)

    # 补齐行业信息（用于行业基准对比）
    try:
        import akshare as ak

        code = symbol.split(".")[0]
        stock_info = ak.stock_individual_info_em(symbol=code)
        if stock_info is not None and not stock_info.empty:
            info_dict = dict(zip(stock_info["item"], stock_info["value"]))
            industry = (
                info_dict.get("所属行业")
                or info_dict.get("行业")
                or info_dict.get("所属板块")
                or info_dict.get("行业分类")
            )
            industry = (str(industry).strip() if industry is not None else None) or None

            if industry:
                # 同步到公司表
                try:
                    upsert_company(market="CN", symbol=symbol, industry_code=industry)
                except Exception:
                    pass

                # 写入报告 source_meta
                with session_scope() as s2:
                    rr = s2.get(Report, report_id)
                    if rr:
                        try:
                            meta = json.loads(rr.source_meta or "{}")
                        except Exception:
                            meta = {}
                        meta["industry"] = industry
                        if "industry_bucket" not in meta:
                            meta["industry_bucket"] = None
                        rr.source_meta = json.dumps(meta, ensure_ascii=False)
                        rr.updated_at = int(time.time())
    except Exception:
        pass

    _ingest_statement(report_id, company_id, "is", period_type, fin.profit, PROFIT_MAP, source="akshare_em")
    _ingest_statement(report_id, company_id, "bs", period_type, fin.balance, BALANCE_MAP, source="akshare_em")
    _ingest_statement(report_id, company_id, "cf", period_type, fin.cash, CASH_MAP, source="akshare_em")

    _compute_metrics_and_alerts(report_id, company_id, focus_period_end=period_end, period_type=period_type)

    with session_scope() as s:
        r2 = s.get(Report, report_id)
        if r2:
            r2.status = "done"
            r2.updated_at = int(time.time())


def _ingest_statement(
    report_id: str,
    company_id: str,
    statement_type: str,
    period_type: str,
    df: pd.DataFrame,
    mapping: dict[str, tuple[str | None, str]],
    source: str,
) -> None:
    keep_cols = ["REPORT_DATE", "CURRENCY"] + [c for c, _ in mapping.values() if c]

    with session_scope() as s:
        for _, row in df.iterrows():
            period_end = _period_end_from_row(row)
            currency = str(row.get("CURRENCY")) if row.get("CURRENCY") is not None else None

            st_obj = Statement(
                id=str(uuid.uuid4()),
                report_id=report_id,
                company_id=company_id,
                statement_type=statement_type,
                period_end=period_end,
                period_type=period_type,
                source=source,
                raw_payload=row_payload(row, keep_cols),
                created_at=int(time.time()),
            )
            s.add(st_obj)

            for code, (col, name) in mapping.items():
                if col is None:
                    # placeholder for fields not mapped in P0
                    continue
                v = _safe_float(row.get(col))
                item = StatementItem(
                    id=str(uuid.uuid4()),
                    statement_id=st_obj.id,
                    report_id=report_id,
                    company_id=company_id,
                    statement_type=statement_type,
                    period_end=period_end,
                    period_type=period_type,
                    standard_item_code=code,
                    standard_item_name=STANDARD_ITEM_NAMES.get(code, name),
                    value=v,
                    currency=currency,
                    original_item_name=col,
                    mapping_confidence=1.0,
                )
                s.add(item)


def _items_for_period(report_id: str, period_end: str) -> dict[str, float | None]:
    with session_scope() as s:
        stmt = select(StatementItem).where(StatementItem.report_id == report_id, StatementItem.period_end == period_end)
        items = s.execute(stmt).scalars().all()
        return {i.standard_item_code: i.value for i in items}


def _sorted_periods(report_id: str) -> list[str]:
    with session_scope() as s:
        stmt = select(Statement.period_end).where(Statement.report_id == report_id).distinct()
        periods = sorted({p[0] for p in s.execute(stmt).all()})
        return periods


def _compute_metrics_and_alerts(report_id: str, company_id: str, focus_period_end: str, period_type: str) -> None:
    periods = _sorted_periods(report_id)
    if not periods:
        return

    # compute metrics for all periods with prev period for avg fields
    with session_scope() as s:
        for idx, pe in enumerate(periods):
            cur_items = _items_for_period(report_id, pe)
            prev_items = _items_for_period(report_id, periods[idx - 1]) if idx > 0 else None
            metrics = compute_p0_metrics(cur_items, prev_items)
            for m in metrics:
                s.add(
                    ComputedMetric(
                        id=str(uuid.uuid4()),
                        report_id=report_id,
                        company_id=company_id,
                        period_end=pe,
                        period_type=period_type,
                        metric_code=m.metric_code,
                        metric_name=m.metric_name,
                        value=m.value,
                        unit=m.unit,
                        calc_trace=dumps(m.calc_trace),
                        created_at=int(time.time()),
                    )
                )

    # alerts only for focus period (latest selected)
    focus_items = _items_for_period(report_id, focus_period_end)
    alerts = risk_p0(focus_items)
    with session_scope() as s:
        for a in alerts:
            s.add(
                Alert(
                    id=str(uuid.uuid4()),
                    report_id=report_id,
                    company_id=company_id,
                    period_end=focus_period_end,
                    period_type=period_type,
                    alert_code=a.alert_code,
                    level=a.level,
                    title=a.title,
                    message=a.message,
                    evidence=dumps(a.evidence),
                    created_at=int(time.time()),
                )
            )
