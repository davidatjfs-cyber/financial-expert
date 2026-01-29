from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select

from core.db import session_scope
from core.models import ComputedMetric
from core.repository import list_reports
from core.schema import init_db
from core.styles import inject_css, render_sidebar_nav, render_mobile_nav


def main() -> None:
    st.set_page_config(page_title="趋势分析", page_icon="📉", layout="wide")
    inject_css()
    init_db()

    with st.sidebar:
        render_sidebar_nav()

    # 移动端导航栏
    render_mobile_nav(title="趋势分析", show_back=True, back_url="app.py")

    st.markdown('<div class="page-title">趋势分析</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">追踪财务指标的变化趋势，洞察企业发展方向</div>', unsafe_allow_html=True)

    metrics = _load_all_metrics()

    if metrics.empty:
        st.info("暂无指标数据，请先上传并分析财务报表")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('''
        <div class="category-card">
            <div class="category-header">📈 盈利能力趋势</div>
            <div style="font-size:0.875rem;color:#888;">毛利率与净利率变化</div>
        </div>
        ''', unsafe_allow_html=True)

        profit_metrics = metrics[metrics["metric_code"].isin(["GROSS_MARGIN", "NET_MARGIN"])].copy()
        if not profit_metrics.empty:
            fig1 = go.Figure()
            for metric_name in profit_metrics["metric_name"].unique():
                data = profit_metrics[profit_metrics["metric_name"] == metric_name].sort_values("period_end")
                fig1.add_trace(go.Scatter(
                    x=data["period_end"], y=data["value"],
                    mode="lines+markers", name=metric_name,
                    fill="tozeroy", line=dict(width=2),
                ))
            fig1.update_layout(
                height=280, margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                yaxis_title="百分比 (%)", xaxis_title="",
                plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("暂无盈利能力数据")

    with col2:
        st.markdown('''
        <div class="category-card">
            <div class="category-header">📊 偿债能力趋势</div>
            <div style="font-size:0.875rem;color:#888;">流动比率变化</div>
        </div>
        ''', unsafe_allow_html=True)

        debt_metrics = metrics[metrics["metric_code"].isin(["CURRENT_RATIO", "DEBT_ASSET"])].copy()
        if not debt_metrics.empty:
            fig2 = go.Figure()
            for metric_name in debt_metrics["metric_name"].unique():
                data = debt_metrics[debt_metrics["metric_name"] == metric_name].sort_values("period_end")
                fig2.add_trace(go.Scatter(
                    x=data["period_end"], y=data["value"],
                    mode="lines+markers", name=metric_name,
                    line=dict(width=2),
                ))
            fig2.update_layout(
                height=280, margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                yaxis_title="倍数 / 百分比", xaxis_title="",
                plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("暂无偿债能力数据")

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("#### 报表时间线")
    st.caption("已分析的财务报表按时间排列")

    reports = list_reports(limit=20)
    done_reports = [r for r in reports if r.status == "done"]

    if not done_reports:
        st.info("暂无已分析的报表")
    else:
        for r in done_reports:
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(f'''
                <div class="report-item">
                    <div class="report-icon" style="background:#e3f2fd;">📅</div>
                    <div class="report-info">
                        <div class="report-title">{r.report_name}</div>
                        <div class="report-meta">{r.source_type} · {r.period_end}</div>
                    </div>
                    <div class="report-arrow">›</div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                if st.button("→", key=f"timeline_{r.id}"):
                    st.session_state["active_report_id"] = r.id
                    st.switch_page("pages/3_分析报告.py")


def _load_all_metrics() -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(ComputedMetric)
        rows = s.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
            {"report_id": r.report_id, "period_end": r.period_end, "metric_code": r.metric_code, "metric_name": r.metric_name, "value": r.value, "unit": r.unit}
            for r in rows
        ])


if __name__ == "__main__":
    main()
