from __future__ import annotations

import os
import streamlit as st
from sqlalchemy import func, select
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from core.db import session_scope
from core.models import Alert, Report
from core.repository import list_reports
from core.schema import init_db
from core.styles import inject_css, render_sidebar_nav, render_mobile_nav, stat_card, badge


def main() -> None:
    st.set_page_config(page_title="财务分析专家", page_icon="📊", layout="wide")
    inject_css()
    init_db()

    with st.sidebar:
        render_sidebar_nav()

    # 移动端导航栏
    render_mobile_nav(title="仪表盘", show_back=False)

    # 页面标题
    st.markdown('<div class="page-title">财务分析仪表盘</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">智能分析财务报表，洞察经营状况</div>', unsafe_allow_html=True)

    # 统计卡片
    stats = _get_stats()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(stat_card("分析报告", stats["total"], "已上传的财务报表", "📄"), unsafe_allow_html=True)
    with c2:
        st.markdown(stat_card("已完成分析", stats["done"], "分析完成的报表", "✅"), unsafe_allow_html=True)
    with c3:
        st.markdown(stat_card("风险预警", stats["risks"], "高风险报表数量", "⚠️"), unsafe_allow_html=True)
    with c4:
        rate = f"{stats['rate']}%" if stats["total"] > 0 else "0%"
        st.markdown(stat_card("分析完成率", rate, "报表分析完成比例", "📊"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 快速操作
    st.markdown("#### 快速操作")

    if st.button("📤 上传财务报表", type="primary", use_container_width=True):
        st.switch_page("pages/2_上传报表.py")

    if st.button("📋 查看分析报告", use_container_width=True):
        st.switch_page("pages/3_分析报告.py")

    if st.button("⚠️ 风险预警中心", use_container_width=True):
        st.switch_page("pages/5_风险预警.py")

    st.markdown("<br>", unsafe_allow_html=True)

    # 多公司对比功能
    st.markdown('''
    <div style="margin-bottom:1rem;">
        <div style="font-size:1.125rem;font-weight:600;color:#1a1a2e;margin-bottom:0.5rem;">📊 多公司财务对比</div>
        <div style="font-size:0.8125rem;color:#666;">选择多家公司进行横向财务指标对比分析</div>
    </div>
    ''', unsafe_allow_html=True)
    
    # 获取已完成分析的报告
    done_reports = [r for r in list_reports(limit=20) if r.status == "done"]
    
    if len(done_reports) >= 2:
        selected_reports = st.multiselect(
            "选择要对比的公司（2-5家）",
            options=[(r.id, r.report_name) for r in done_reports],
            format_func=lambda x: x[1],
            max_selections=5,
            key="compare_reports"
        )
        
        if len(selected_reports) >= 2:
            if st.button("🔍 开始对比分析", type="primary"):
                st.session_state["compare_report_ids"] = [r[0] for r in selected_reports]
                st.switch_page("pages/7_公司对比.py")
        else:
            st.markdown('<div style="font-size:0.8125rem;color:#888;">请至少选择 2 家公司进行对比</div>', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div style="padding:1rem;background:#f8f9fa;border-radius:8px;border:1px solid #eee;">
            <div style="font-size:0.875rem;color:#666;">💡 需要至少 2 份已完成分析的报告才能进行对比</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 最近分析
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("#### 最近分析")
    with col2:
        if st.button("查看全部", type="secondary"):
            st.switch_page("pages/3_分析报告.py")

    reports = list_reports(limit=5)
    if not reports:
        st.info("暂无报告，点击上方「上传财务报表」开始")
    else:
        for r in reports:
            status_map = {
                "done": ("success", "已完成"),
                "running": ("warning", "分析中"),
                "failed": ("danger", "失败"),
                "pending": ("pending", "待识别"),
            }
            s, t = status_map.get(r.status, ("pending", "待识别"))

            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(f'''
                <div class="report-item">
                    <div class="report-icon">📄</div>
                    <div class="report-info">
                        <div class="report-title">{r.report_name} {badge(t, s)}</div>
                        <div class="report-meta">📁 {r.source_type} · 📅 {r.period_end}</div>
                    </div>
                    <div class="report-arrow">›</div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                if st.button("→", key=f"go_{r.id}"):
                    st.session_state["active_report_id"] = r.id
                    st.switch_page("pages/3_分析报告.py")


def _get_stats() -> dict:
    with session_scope() as s:
        total = s.execute(select(func.count(Report.id))).scalar() or 0
        done = s.execute(select(func.count(Report.id)).where(Report.status == "done")).scalar() or 0
        risks = s.execute(select(func.count(func.distinct(Alert.report_id))).where(Alert.level == "high")).scalar() or 0
        rate = int(done / total * 100) if total > 0 else 0
    return {"total": total, "done": done, "risks": risks, "rate": rate}


if __name__ == "__main__":
    main()
