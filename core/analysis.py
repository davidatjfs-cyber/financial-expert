from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MetricResult:
    metric_code: str
    metric_name: str
    value: float | None
    unit: str | None
    calc_trace: dict


@dataclass(frozen=True)
class AlertResult:
    alert_code: str
    level: str
    title: str
    message: str
    evidence: dict


STANDARD_ITEM_NAMES: dict[str, str] = {
    "IS.REVENUE": "营业收入",
    "IS.COGS": "营业成本",
    "IS.NET_PROFIT": "净利润",
    "IS.SELLING_EXP": "销售费用",
    "IS.GA_EXP": "管理费用",
    "IS.FIN_EXP": "财务费用",
    "BS.CASH": "货币资金",
    "BS.AR": "应收账款",
    "BS.INVENTORY": "存货",
    "BS.CA_TOTAL": "流动资产合计",
    "BS.CL_TOTAL": "流动负债合计",
    "BS.ASSET_TOTAL": "资产总计",
    "BS.LIAB_TOTAL": "负债合计",
    "BS.EQUITY_TOTAL": "所有者权益合计",
    "BS.DEBT_INTEREST": "有息负债",
    "CF.CFO": "经营活动现金流净额",
}


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return a / b


def avg(a: float | None, b: float | None) -> float | None:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2


def compute_p0_metrics(items_by_code: dict[str, float | None], prev_items_by_code: dict[str, float | None] | None = None) -> list[MetricResult]:
    revenue = items_by_code.get("IS.REVENUE")
    cogs = items_by_code.get("IS.COGS")
    net_profit = items_by_code.get("IS.NET_PROFIT")

    cash = items_by_code.get("BS.CASH")
    ar = items_by_code.get("BS.AR")
    inv = items_by_code.get("BS.INVENTORY")

    ca = items_by_code.get("BS.CA_TOTAL")
    cl = items_by_code.get("BS.CL_TOTAL")
    asset_total = items_by_code.get("BS.ASSET_TOTAL")
    liab_total = items_by_code.get("BS.LIAB_TOTAL")
    equity_total = items_by_code.get("BS.EQUITY_TOTAL")

    cfo = items_by_code.get("CF.CFO")

    prev_asset_total = prev_items_by_code.get("BS.ASSET_TOTAL") if prev_items_by_code else None
    prev_equity_total = prev_items_by_code.get("BS.EQUITY_TOTAL") if prev_items_by_code else None
    prev_ar = prev_items_by_code.get("BS.AR") if prev_items_by_code else None
    prev_inv = prev_items_by_code.get("BS.INVENTORY") if prev_items_by_code else None

    metrics: list[MetricResult] = []

    gross_profit = None
    if revenue is not None and cogs is not None:
        gross_profit = revenue - cogs

    gross_margin = safe_div(gross_profit, revenue)
    metrics.append(
        MetricResult(
            metric_code="GROSS_MARGIN",
            metric_name="毛利率",
            value=None if gross_margin is None else gross_margin * 100,
            unit="%",
            calc_trace={"formula": "(REVENUE-COGS)/REVENUE", "REVENUE": revenue, "COGS": cogs},
        )
    )

    net_margin = safe_div(net_profit, revenue)
    metrics.append(
        MetricResult(
            metric_code="NET_MARGIN",
            metric_name="净利率",
            value=None if net_margin is None else net_margin * 100,
            unit="%",
            calc_trace={"formula": "NET_PROFIT/REVENUE", "NET_PROFIT": net_profit, "REVENUE": revenue},
        )
    )

    roe = safe_div(net_profit, avg(equity_total, prev_equity_total))
    metrics.append(
        MetricResult(
            metric_code="ROE",
            metric_name="ROE",
            value=None if roe is None else roe * 100,
            unit="%",
            calc_trace={
                "formula": "NET_PROFIT/avg(EQUITY)",
                "NET_PROFIT": net_profit,
                "EQUITY_T": equity_total,
                "EQUITY_T-1": prev_equity_total,
            },
        )
    )

    roa = safe_div(net_profit, avg(asset_total, prev_asset_total))
    metrics.append(
        MetricResult(
            metric_code="ROA",
            metric_name="ROA",
            value=None if roa is None else roa * 100,
            unit="%",
            calc_trace={
                "formula": "NET_PROFIT/avg(ASSET_TOTAL)",
                "NET_PROFIT": net_profit,
                "ASSET_T": asset_total,
                "ASSET_T-1": prev_asset_total,
            },
        )
    )

    current_ratio = safe_div(ca, cl)
    metrics.append(
        MetricResult(
            metric_code="CURRENT_RATIO",
            metric_name="流动比率",
            value=current_ratio,
            unit="times",
            calc_trace={"formula": "CA_TOTAL/CL_TOTAL", "CA_TOTAL": ca, "CL_TOTAL": cl},
        )
    )

    quick_ratio = safe_div(None if ca is None or inv is None else ca - inv, cl)
    metrics.append(
        MetricResult(
            metric_code="QUICK_RATIO",
            metric_name="速动比率",
            value=quick_ratio,
            unit="times",
            calc_trace={"formula": "(CA_TOTAL-INVENTORY)/CL_TOTAL", "CA_TOTAL": ca, "INVENTORY": inv, "CL_TOTAL": cl},
        )
    )

    debt_asset = safe_div(liab_total, asset_total)
    metrics.append(
        MetricResult(
            metric_code="DEBT_ASSET",
            metric_name="资产负债率",
            value=None if debt_asset is None else debt_asset * 100,
            unit="%",
            calc_trace={"formula": "LIAB_TOTAL/ASSET_TOTAL", "LIAB_TOTAL": liab_total, "ASSET_TOTAL": asset_total},
        )
    )

    debt_equity = safe_div(liab_total, equity_total)
    metrics.append(
        MetricResult(
            metric_code="DEBT_EQUITY",
            metric_name="产权比率",
            value=debt_equity,
            unit="times",
            calc_trace={"formula": "LIAB_TOTAL/EQUITY_TOTAL", "LIAB_TOTAL": liab_total, "EQUITY_TOTAL": equity_total},
        )
    )

    asset_turnover = safe_div(revenue, avg(asset_total, prev_asset_total))
    metrics.append(
        MetricResult(
            metric_code="ASSET_TURNOVER",
            metric_name="总资产周转率",
            value=asset_turnover,
            unit="times",
            calc_trace={"formula": "REVENUE/avg(ASSET_TOTAL)", "REVENUE": revenue, "ASSET_T": asset_total, "ASSET_T-1": prev_asset_total},
        )
    )

    # DSO/DIO with rough days
    days = 90
    ar_avg = avg(ar, prev_ar)
    dso = None
    if ar_avg is not None and revenue is not None and revenue != 0:
        dso = ar_avg / revenue * days
    metrics.append(
        MetricResult(
            metric_code="DSO",
            metric_name="应收账款周转天数",
            value=dso,
            unit="days",
            calc_trace={"formula": "avg(AR)/REVENUE*days", "AR_T": ar, "AR_T-1": prev_ar, "REVENUE": revenue, "days": days},
        )
    )

    inv_avg = avg(inv, prev_inv)
    dio = None
    if inv_avg is not None and cogs is not None and cogs != 0:
        dio = inv_avg / cogs * days
    metrics.append(
        MetricResult(
            metric_code="DIO",
            metric_name="存货周转天数",
            value=dio,
            unit="days",
            calc_trace={"formula": "avg(INV)/COGS*days", "INV_T": inv, "INV_T-1": prev_inv, "COGS": cogs, "days": days},
        )
    )

    cfo_np = safe_div(cfo, net_profit)
    metrics.append(
        MetricResult(
            metric_code="CFO_NP",
            metric_name="经营现金流/净利润",
            value=cfo_np,
            unit="times",
            calc_trace={"formula": "CFO/NET_PROFIT", "CFO": cfo, "NET_PROFIT": net_profit},
        )
    )

    return metrics


def risk_p0(items_by_code: dict[str, float | None]) -> list[AlertResult]:
    """基于原始财务数据生成风险预警 - 增强版"""
    cash = items_by_code.get("BS.CASH")
    asset_total = items_by_code.get("BS.ASSET_TOTAL")
    debt_interest = items_by_code.get("BS.DEBT_INTEREST")
    cfo = items_by_code.get("CF.CFO")
    net_profit = items_by_code.get("IS.NET_PROFIT")
    revenue = items_by_code.get("IS.REVENUE")
    cogs = items_by_code.get("IS.COGS")
    ca = items_by_code.get("BS.CA_TOTAL")
    cl = items_by_code.get("BS.CL_TOTAL")
    liab_total = items_by_code.get("BS.LIAB_TOTAL")
    equity_total = items_by_code.get("BS.EQUITY_TOTAL")
    inventory = items_by_code.get("BS.INVENTORY")
    ar = items_by_code.get("BS.AR")

    alerts: list[AlertResult] = []

    # 计算关键指标
    gross_margin = None
    if revenue and cogs and revenue > 0:
        gross_margin = (revenue - cogs) / revenue * 100

    net_margin = None
    if revenue and net_profit and revenue > 0:
        net_margin = net_profit / revenue * 100

    current_ratio = None
    if ca and cl and cl > 0:
        current_ratio = ca / cl

    debt_asset = None
    if asset_total and liab_total and asset_total > 0:
        debt_asset = liab_total / asset_total * 100

    roe = None
    if equity_total and net_profit and equity_total > 0:
        roe = net_profit / equity_total * 100

    # ========== 存贷双高 ==========
    if cash is not None and asset_total and debt_interest is not None and asset_total != 0:
        cash_ratio = cash / asset_total
        debt_ratio = debt_interest / asset_total
        x, y = 0.2, 0.2
        if cash_ratio > x and debt_ratio > y:
            alerts.append(
                AlertResult(
                    alert_code="RF_CASH_DEBT_HIGH",
                    level="high",
                    title="存贷双高",
                    message="货币资金与有息负债同时偏高，关注资金结构与真实负债压力。",
                    evidence={"cash": cash, "debt_interest": debt_interest, "cash_ratio": cash_ratio, "debt_ratio": debt_ratio},
                )
            )

    # ========== 利润含金量偏低 ==========
    if cfo is not None and net_profit is not None:
        if cfo < 0 and net_profit > 0:
            alerts.append(
                AlertResult(
                    alert_code="RF_CFO_NEGATIVE",
                    level="high",
                    title="利润含金量偏低",
                    message="净利润为正但经营性现金流为负，关注应收、存货或非经常性项目影响。",
                    evidence={"cfo": cfo, "net_profit": net_profit},
                )
            )

    # ========== 流动性资产利用效率低下 ==========
    if current_ratio and current_ratio > 3:
        alerts.append(
            AlertResult(
                alert_code="RF_HIGH_LIQUIDITY",
                level="medium",
                title="流动性资产利用效率低下",
                message=f"流动比率高达 {current_ratio:.2f}，远超安全范围（通常2.0左右），表明公司持有大量现金和类现金资产。这虽然提供了极高的偿债保障，但也意味着大量资金未被有效投入到高回报的增长项目或资本支出中，存在资金闲置成本。",
                evidence={"current_ratio": current_ratio, "ca": ca, "cl": cl},
            )
        )

    # ========== 短期偿债能力不足 ==========
    if current_ratio and current_ratio < 1:
        alerts.append(
            AlertResult(
                alert_code="RF_LOW_CURRENT",
                level="high",
                title="短期偿债能力不足",
                message=f"流动比率为 {current_ratio:.2f}，低于1.0警戒线，表明流动资产不足以覆盖流动负债，短期偿债压力较大。",
                evidence={"current_ratio": current_ratio, "ca": ca, "cl": cl},
            )
        )

    # ========== 财务杠杆过高 ==========
    if debt_asset and debt_asset > 70:
        alerts.append(
            AlertResult(
                alert_code="RF_HIGH_DEBT",
                level="high",
                title="财务杠杆过高",
                message=f"资产负债率达到 {debt_asset:.1f}%，超过70%警戒线，财务杠杆较高，在经济下行期可能面临偿债压力。",
                evidence={"debt_asset": debt_asset, "liab_total": liab_total, "asset_total": asset_total},
            )
        )

    # ========== 财务杠杆利用不足 ==========
    if debt_asset and debt_asset < 20:
        alerts.append(
            AlertResult(
                alert_code="RF_LOW_LEVERAGE",
                level="low",
                title="财务杠杆利用不足",
                message=f"资产负债率仅为 {debt_asset:.1f}%，财务结构过于保守。虽然财务风险极低，但可能未能充分利用财务杠杆提升股东回报，存在资本效率优化空间。",
                evidence={"debt_asset": debt_asset, "liab_total": liab_total, "asset_total": asset_total},
            )
        )

    # ========== 增长放缓及基数效应风险 ==========
    if gross_margin and gross_margin > 50 and net_margin and net_margin > 30:
        alerts.append(
            AlertResult(
                alert_code="RF_GROWTH_CEILING",
                level="medium",
                title="增长放缓及基数效应风险",
                message=f"作为高利润率企业（毛利率{gross_margin:.1f}%，净利率{net_margin:.1f}%），未来的营收增长将面临巨大的基数效应挑战。持续保持高净利率和高ROE，需要不断开拓新市场或提高产品结构附加值，存在增长瓶颈的潜在风险。",
                evidence={"gross_margin": gross_margin, "net_margin": net_margin},
            )
        )

    # ========== 盈利能力偏弱 ==========
    if net_margin and net_margin < 5:
        alerts.append(
            AlertResult(
                alert_code="RF_LOW_MARGIN",
                level="medium",
                title="盈利能力偏弱",
                message=f"净利率为 {net_margin:.1f}%，低于行业平均水平，盈利能力较弱。需关注成本控制、定价策略和产品结构优化。",
                evidence={"net_margin": net_margin, "net_profit": net_profit, "revenue": revenue},
            )
        )

    # ========== ROE 偏低 ==========
    if roe and roe < 8:
        alerts.append(
            AlertResult(
                alert_code="RF_LOW_ROE",
                level="medium",
                title="股东回报效率偏低",
                message=f"净资产收益率为 {roe:.1f}%，低于8%的基准水平，资本回报效率不高。建议优化资本结构、提升资产周转率或改善利润率。",
                evidence={"roe": roe, "net_profit": net_profit, "equity_total": equity_total},
            )
        )

    return alerts


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
