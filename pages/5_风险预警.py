from __future__ import annotations

import streamlit as st
from sqlalchemy import select, func

from core.db import session_scope
from core.models import Alert
from core.repository import list_reports
from core.schema import init_db
from core.styles import inject_css, render_sidebar_nav, render_mobile_nav, risk_card, badge


def main() -> None:
    st.set_page_config(page_title="风险预警", page_icon="⚠️", layout="wide")
    inject_css()
    init_db()

    with st.sidebar:
        render_sidebar_nav()

    # 移动端导航栏
    render_mobile_nav(title="风险预警", show_back=True, back_url="app.py")

    st.markdown('<div class="page-title">风险预警中心</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">监控所有财务报表的风险状况，及时发现潜在问题</div>', unsafe_allow_html=True)

    stats = _get_risk_stats()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(risk_card("严重风险", stats["critical"], "需立即处理", "critical"), unsafe_allow_html=True)
    with col2:
        st.markdown(risk_card("较高风险", stats["high"], "需重点关注", "high"), unsafe_allow_html=True)
    with col3:
        st.markdown(risk_card("中等风险", stats["medium"], "建议改进", "medium"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("#### 已分析报表")
    st.caption("点击查看各报表的详细风险分析")

    reports = list_reports(limit=50)
    done_reports = [r for r in reports if r.status == "done"]

    if not done_reports:
        st.info("暂无已分析的报表")
    else:
        for r in done_reports:
            report_alerts = _get_report_alerts(r.id)
            has_risk = len(report_alerts) > 0

            col1, col2 = st.columns([6, 1])
            with col1:
                icon = "⚠️" if has_risk else "✅"
                icon_bg = "#fff3e0" if has_risk else "#e8f5e9"
                st.markdown(f'''
                <div class="report-item">
                    <div class="report-icon" style="background:{icon_bg};">{icon}</div>
                    <div class="report-info">
                        <div class="report-title">{r.report_name}</div>
                        <div class="report-meta">{r.source_type} · {r.period_end}</div>
                    </div>
                    <div class="report-arrow">›</div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                if st.button("→", key=f"risk_{r.id}"):
                    st.session_state["active_report_id"] = r.id
                    st.switch_page("pages/3_分析报告.py")


def _get_risk_stats() -> dict:
    with session_scope() as s:
        critical = s.execute(select(func.count(Alert.id)).where(Alert.level == "critical")).scalar() or 0
        high = s.execute(select(func.count(Alert.id)).where(Alert.level == "high")).scalar() or 0
        medium = s.execute(select(func.count(Alert.id)).where(Alert.level == "medium")).scalar() or 0
    return {"critical": critical, "high": high, "medium": medium}


def _get_report_alerts(report_id: str) -> list:
    with session_scope() as s:
        stmt = select(Alert).where(Alert.report_id == report_id)
        return s.execute(stmt).scalars().all()


if __name__ == "__main__":
    main()
