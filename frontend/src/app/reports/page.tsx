'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ReportItem from '@/components/ReportItem';
import { Search } from 'lucide-react';
import { getReports, type Report } from '@/services/api';

export default function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all');

  const formatDateTime = (tsSeconds: number) => {
    const d = new Date(tsSeconds * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  useEffect(() => {
    async function fetchReports() {
      try {
        const data = await getReports(50);
        setReports(data);
      } catch (error) {
        console.error('Failed to fetch reports:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchReports();
  }, []);

  const filteredReports = reports.filter((report) => {
    const matchesSearch = report.report_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filter === 'all' || report.status === filter;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto pb-24">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">分析报告</h1>
        <p className="text-[#6B6B70] text-sm mt-1">查看所有已上传和分析的财务报表</p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-5 top-1/2 -translate-y-1/2 text-[#6B6B70]" size={22} />
        <input
          type="text"
          placeholder="搜索报告..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-[#16161A] text-[#FAFAF9] rounded-xl py-4 pl-14 pr-5 text-base border border-[#2A2A2E] focus:border-[#32D583] focus:outline-none placeholder:text-[#6B6B70]"
        />
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {[
          { key: 'all', label: '全部' },
          { key: 'done', label: '已完成' },
          { key: 'running', label: '分析中' },
          { key: 'pending', label: '待识别' },
          { key: 'failed', label: '失败' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`px-5 py-3 rounded-xl text-base font-medium whitespace-nowrap ${
              filter === tab.key
                ? 'bg-[#32D583] text-white'
                : 'bg-[#16161A] text-[#6B6B70] border border-[#2A2A2E]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tip */}
      <div className="bg-[#6366F1]/10 rounded-xl p-4 border border-[#6366F1]/30">
        <p className="text-[#6366F1] text-sm">
          💡 提示：通过"股票查询"获取的A股报告（如贵州茅台、五粮液）有完整的财务分析数据
        </p>
      </div>

      {/* Reports List */}
      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
            <p className="text-[#6B6B70] text-base">加载中...</p>
          </div>
        ) : filteredReports.length > 0 ? (
          filteredReports.map((report) => (
            <ReportItem
              key={report.id}
              title={report.report_name}
              source={report.source_type === 'market_fetch' ? '市场数据' : '文件上传'}
              date={formatDateTime(report.created_at)}
              status={report.status}
              onClick={() => router.push(`/reports/${report.id}`)}
            />
          ))
        ) : (
          <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
            <p className="text-[#6B6B70] text-base">没有找到匹配的报告</p>
          </div>
        )}
      </div>
    </div>
  );
}
