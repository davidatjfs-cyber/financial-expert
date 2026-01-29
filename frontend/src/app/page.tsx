'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import ReportItem from '@/components/ReportItem';
import { getStats, getReports, type Stats, type Report } from '@/services/api';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ total: 0, done: 0, risks: 0, rate: 0 });
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsData, reportsData] = await Promise.all([
          getStats(),
          getReports(5),
        ]);
        setStats(statsData);
        setReports(reportsData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">财务分析专家</h1>
          <p className="text-[#6B6B70] text-sm mt-1">智能财务决策助手</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-[#16161A] border border-[#2A2A2E] flex items-center justify-center">
            <span className="text-lg">🔔</span>
          </div>
          <div className="w-11 h-11 rounded-full bg-[#16161A] border border-[#2A2A2E] flex items-center justify-center">
            <span className="text-lg">👤</span>
          </div>
        </div>
      </div>

      {/* Stats Grid - 2x2 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
          <div className="text-[#6B6B70] text-sm mb-2">分析报告</div>
          <div className="text-[#FAFAF9] text-4xl font-bold">{loading ? '-' : stats.total}</div>
        </div>
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
          <div className="text-[#6B6B70] text-sm mb-2">已完成</div>
          <div className="text-[#32D583] text-4xl font-bold">{loading ? '-' : stats.done}</div>
        </div>
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
          <div className="text-[#6B6B70] text-sm mb-2">风险预警</div>
          <div className="text-[#E85A4F] text-4xl font-bold">{loading ? '-' : stats.risks}</div>
        </div>
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
          <div className="text-[#6B6B70] text-sm mb-2">完成率</div>
          <div className="text-[#6366F1] text-4xl font-bold">{loading ? '-' : `${stats.rate}%`}</div>
        </div>
      </div>

      {/* Multi-Company Comparison */}
      <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
        <h3 className="text-[#FAFAF9] text-lg font-semibold mb-2">多公司财务对比</h3>
        <p className="text-[#6B6B70] text-sm mb-4">选择公司进行横向财务指标对比分析</p>
        <div className="flex gap-3 mb-4">
          <div className="flex-1 bg-[#1A1A1E] rounded-xl py-4 px-4 text-[#FAFAF9] text-base border border-[#2A2A2E]">
            腾讯控股
          </div>
          <div className="flex-1 bg-[#1A1A1E] rounded-xl py-4 px-4 text-[#FAFAF9] text-base border border-[#2A2A2E]">
            阿里巴巴
          </div>
        </div>
        <Link
          href="/compare"
          className="block bg-[#6366F1] text-white rounded-xl py-4 px-4 text-center font-semibold text-base"
        >
          🔍 开始对比分析
        </Link>
      </div>

      {/* Recent Analysis */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[#FAFAF9] text-lg font-semibold">最近分析</h3>
          <Link href="/reports" className="text-[#32D583] text-sm font-medium">
            查看全部 →
          </Link>
        </div>
        <div className="flex flex-col gap-3">
          {loading ? (
            <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70]">加载中...</p>
            </div>
          ) : reports.length > 0 ? (
            reports.map((report) => (
              <ReportItem
                key={report.id}
                title={report.report_name}
                source={report.source_type}
                date={report.period_end}
                status={report.status}
              />
            ))
          ) : (
            <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70]">暂无报告，点击上传开始分析</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
