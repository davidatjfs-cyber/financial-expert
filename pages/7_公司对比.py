from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.db import session_scope
from core.models import Report, ComputedMetric
from core.schema import init_db
from core.styles import inject_css, render_sidebar_nav


METRIC_NAMES = {
    "GROSS_MARGIN": "毛利率",
    "NET_MARGIN": "净利率",
    "ROE": "ROE",
    "ROA": "ROA",
    "CURRENT_RATIO": "流动比率",
    "QUICK_RATIO": "速动比率",
    "DEBT_ASSET": "资产负债率",
    "EQUITY_RATIO": "产权比率",
    "ASSET_TURNOVER": "资产周转率",
}


def main() -> None:
    st.set_page_config(page_title="公司对比", page_icon="📊", layout="wide")
    inject_css()
    init_db()

    with st.sidebar:
        render_sidebar_nav()

    st.markdown("### 📊 多公司财务对比")
    st.markdown("对比多家公司的关键财务指标")

    # 获取要对比的报告
    report_ids = st.session_state.get("compare_report_ids", [])
    
    if not report_ids or len(report_ids) < 2:
        st.warning("请从仪表盘选择至少 2 家公司进行对比")
        if st.button("← 返回仪表盘"):
            st.switch_page("app.py")
        return

    # 加载报告和指标数据
    reports_data = []
    with session_scope() as session:
        for rid in report_ids:
            report = session.query(Report).filter(Report.id == rid).first()
            if report:
                metrics = session.query(ComputedMetric).filter(ComputedMetric.report_id == rid).all()
                metric_dict = {m.metric_code: m.value for m in metrics}
                reports_data.append({
                    "name": report.report_name,
                    "period": report.period_end,
                    "metrics": metric_dict
                })

    if len(reports_data) < 2:
        st.error("数据加载失败，请重新选择")
        return

    # 显示对比公司
    st.markdown("**对比公司：**")
    cols = st.columns(len(reports_data))
    for i, rd in enumerate(reports_data):
        with cols[i]:
            st.markdown(f'''
            <div style="background:#f8f9fa;padding:1rem;border-radius:8px;text-align:center;">
                <div style="font-weight:600;color:#1a1a2e;">{rd["name"]}</div>
                <div style="font-size:0.8rem;color:#666;">{rd["period"]}</div>
            </div>
            ''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 对比表格
    st.markdown("#### 📋 指标对比表")
    
    compare_data = []
    for metric_code, metric_name in METRIC_NAMES.items():
        row = {"指标": metric_name}
        for rd in reports_data:
            value = rd["metrics"].get(metric_code)
            if value is not None:
                if metric_code in ["GROSS_MARGIN", "NET_MARGIN", "ROE", "ROA", "DEBT_ASSET"]:
                    row[rd["name"]] = f"{value:.2f}%"
                else:
                    row[rd["name"]] = f"{value:.2f}"
            else:
                row[rd["name"]] = "N/A"
        compare_data.append(row)
    
    df = pd.DataFrame(compare_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 雷达图对比
    st.markdown("#### 📈 综合能力雷达图")
    
    radar_metrics = ["NET_MARGIN", "ROE", "ROA", "CURRENT_RATIO", "ASSET_TURNOVER"]
    radar_names = [METRIC_NAMES[m] for m in radar_metrics]
    
    fig = go.Figure()
    
    colors = ['#1976d2', '#e53935', '#43a047', '#fb8c00', '#8e24aa']
    
    for i, rd in enumerate(reports_data):
        values = []
        for m in radar_metrics:
            v = rd["metrics"].get(m)
            if v is not None:
                # 归一化处理
                if m == "NET_MARGIN":
                    values.append(min(v / 50 * 100, 100))
                elif m == "ROE":
                    values.append(min(v / 30 * 100, 100))
                elif m == "ROA":
                    values.append(min(v / 15 * 100, 100))
                elif m == "CURRENT_RATIO":
                    values.append(min(v / 3 * 100, 100))
                elif m == "ASSET_TURNOVER":
                    values.append(min(v / 2 * 100, 100))
                else:
                    values.append(50)
            else:
                values.append(0)
        
        values.append(values[0])  # 闭合雷达图
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=radar_names + [radar_names[0]],
            fill='toself',
            name=rd["name"],
            line_color=colors[i % len(colors)],
            fillcolor=colors[i % len(colors)],
            opacity=0.3
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        showlegend=True,
        height=500,
        margin=dict(l=80, r=80, t=40, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 柱状图对比
    st.markdown("#### 📊 关键指标柱状图对比")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 盈利能力对比
        fig_profit = go.Figure()
        for rd in reports_data:
            fig_profit.add_trace(go.Bar(
                name=rd["name"],
                x=["净利率", "ROE", "ROA"],
                y=[
                    rd["metrics"].get("NET_MARGIN", 0) or 0,
                    rd["metrics"].get("ROE", 0) or 0,
                    rd["metrics"].get("ROA", 0) or 0,
                ]
            ))
        fig_profit.update_layout(
            title="盈利能力对比",
            barmode='group',
            height=350,
            yaxis_title="%"
        )
        st.plotly_chart(fig_profit, use_container_width=True)

    with col2:
        # 偿债能力对比
        fig_debt = go.Figure()
        for rd in reports_data:
            fig_debt.add_trace(go.Bar(
                name=rd["name"],
                x=["资产负债率", "流动比率", "产权比率"],
                y=[
                    rd["metrics"].get("DEBT_ASSET", 0) or 0,
                    (rd["metrics"].get("CURRENT_RATIO", 0) or 0) * 10,  # 放大以便对比
                    rd["metrics"].get("EQUITY_RATIO", 0) or 0,
                ]
            ))
        fig_debt.update_layout(
            title="偿债能力对比",
            barmode='group',
            height=350,
        )
        st.plotly_chart(fig_debt, use_container_width=True)

    # 返回按钮
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← 返回仪表盘"):
        st.switch_page("app.py")


if __name__ == "__main__":
    main()
