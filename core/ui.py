from __future__ import annotations

import json
from datetime import date

import streamlit as st

from core.repository import ReportSummary


def set_page_config() -> None:
    st.set_page_config(page_title="财务分析专家", layout="wide")


def sidebar_market_period() -> tuple[str, str, str]:
    market = st.sidebar.selectbox("市场", ["A股", "港股", "美股"], index=0)
    period_type = st.sidebar.selectbox("期间口径", ["quarter", "annual"], index=0, format_func=lambda x: "季度" if x == "quarter" else "年度")
    period_end = st.sidebar.date_input("报告期末", value=date.today())
    return market, period_type, period_end.isoformat()


def render_report_card(r: ReportSummary) -> None:
    cols = st.columns([5, 2, 2, 2, 1])
    cols[0].write(r.report_name)
    cols[1].write(r.source_type)
    cols[2].write("季度" if r.period_type == "quarter" else "年度")
    cols[3].write(r.status)
    if cols[4].button("进入", key=f"open_{r.id}"):
        st.session_state["active_report_id"] = r.id
        st.switch_page("pages/3_分析报告.py")


def pretty_json(text: str) -> str:
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return text
