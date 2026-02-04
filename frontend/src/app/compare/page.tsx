'use client';

import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import { ArrowLeft } from 'lucide-react';

const comparisonData = [
  { metric: '毛利率', company1: 'N/A', company2: '46.91%', highlight: 2 },
  { metric: '净利率', company1: '3.81%', company2: '26.92%', highlight: 2 },
  { metric: 'ROE', company1: '11.62%', company2: '171.42%', highlight: 2 },
  { metric: 'ROA', company1: '0.93%', company2: '30.93%', highlight: 2 },
  { metric: '流动比率', company1: 'N/A', company2: '0.89', highlight: 0 },
  { metric: '资产负债率', company1: '91.02%', company2: '79.48%', highlight: 0 },
];

export default function ComparePage() {
  const download = (data: BlobPart, filename: string, mime: string) => {
    const blob = new Blob([data], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const exportCsv = () => {
    const header = ['指标', '公司1', '公司2'];
    const rows = comparisonData.map((r) => [r.metric, r.company1, r.company2]);
    const esc = (s: any) => {
      const v = String(s ?? '');
      if (/[",\n]/.test(v)) return '"' + v.replace(/"/g, '""') + '"';
      return v;
    };
    const csv = [header, ...rows].map((r) => r.map(esc).join(',')).join('\n');
    download(csv, 'compare.csv', 'text/csv;charset=utf-8');
  };

  const exportHtml = () => {
    const rows = comparisonData
      .map(
        (r) =>
          `<tr><td>${r.metric}</td><td>${r.company1}</td><td>${r.company2}</td></tr>`
      )
      .join('');
    const html = `<!doctype html><html><head><meta charset="utf-8" /><title>对比报告</title>
<style>body{font-family:Arial,Helvetica,sans-serif;padding:20px;} table{border-collapse:collapse;width:100%;} th,td{border:1px solid #ddd;padding:8px;} th{background:#f5f5f5;}</style>
</head><body><h2>多公司财务对比</h2><table><thead><tr><th>指标</th><th>公司1</th><th>公司2</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
    download(html, 'compare.html', 'text/html;charset=utf-8');
  };

  return (
    <div className="p-4 md:p-6 max-w-4xl">
      <PageHeader
        icon="📊"
        title="多公司财务对比"
        subtitle="对比多家公司的关键财务指标"
      />

      {/* Company Cards */}
      <div className="mb-4">
        <p className="text-[#6B6B70] text-xs mb-2">对比公司:</p>
        <div className="flex gap-2">
          <div className="flex-1 bg-[#16161A] rounded-xl p-3 border border-[#6366F1]">
            <p className="text-[#FAFAF9] text-sm font-semibold">平安银行</p>
            <p className="text-[#6B6B70] text-xs">2025年三季度报告</p>
            <p className="text-[#6366F1] text-xs">2025-09-30</p>
          </div>
          <div className="flex-1 bg-[#16161A] rounded-xl p-3 border border-[#E85A4F]">
            <p className="text-[#FAFAF9] text-sm font-semibold">苹果</p>
            <p className="text-[#6B6B70] text-xs">2025年年度报告</p>
            <p className="text-[#E85A4F] text-xs">2025-12-31</p>
          </div>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">📋</span>
          <h2 className="text-[#FAFAF9] text-sm font-semibold">指标对比表</h2>
        </div>

        <div className="flex gap-2 mb-2">
          <button
            onClick={exportCsv}
            className="flex-1 bg-[#16161A] text-[#FAFAF9] rounded-xl py-3 px-4 font-medium text-sm border border-[#2A2A2E]"
          >
            ⬇️ 导出 CSV
          </button>
          <button
            onClick={exportHtml}
            className="flex-1 bg-[#16161A] text-[#FAFAF9] rounded-xl py-3 px-4 font-medium text-sm border border-[#2A2A2E]"
          >
            ⬇️ 导出 HTML
          </button>
        </div>
        <div className="bg-[#16161A] rounded-xl overflow-hidden border border-[#2A2A2E]">
          {/* Header */}
          <div className="flex border-b border-[#2A2A2E] px-3 py-2">
            <div className="w-20 text-[#6B6B70] text-xs">指标</div>
            <div className="flex-1 text-center text-[#6366F1] text-xs">平安银行</div>
            <div className="flex-1 text-center text-[#E85A4F] text-xs">苹果</div>
          </div>
          {/* Rows */}
          {comparisonData.map((row, i) => (
            <div
              key={row.metric}
              className={`flex px-3 py-2 ${i < comparisonData.length - 1 ? 'border-b border-[#2A2A2E]' : ''}`}
            >
              <div className="w-20 text-[#FAFAF9] text-xs">{row.metric}</div>
              <div className={`flex-1 text-center text-xs ${row.highlight === 1 ? 'text-[#32D583]' : row.company1 === 'N/A' ? 'text-[#6B6B70]' : 'text-[#FAFAF9]'}`}>
                {row.company1}
              </div>
              <div className={`flex-1 text-center text-xs ${row.highlight === 2 ? 'text-[#32D583]' : 'text-[#FAFAF9]'}`}>
                {row.company2}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Radar Chart */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">📈</span>
          <h2 className="text-[#FAFAF9] text-sm font-semibold">综合能力雷达图</h2>
        </div>
        <div className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E]">
          <div className="flex items-center justify-center gap-4 mb-3">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-[#6366F1]" />
              <span className="text-[#6B6B70] text-xs">平安银行</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-[#E85A4F]" />
              <span className="text-[#6B6B70] text-xs">苹果</span>
            </div>
          </div>
          {/* Mock Radar */}
          <div className="w-32 h-24 mx-auto bg-[#1A1A1E] rounded-full relative">
            <div className="absolute inset-4 bg-[#6366F1]/30 rounded-full" />
            <div className="absolute inset-8 bg-[#E85A4F]/30 rounded-full" />
          </div>
        </div>
      </div>

      {/* Bar Charts */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">📊</span>
          <h2 className="text-[#FAFAF9] text-sm font-semibold">关键指标柱状图对比</h2>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 bg-[#16161A] rounded-xl p-3 border border-[#2A2A2E]">
            <p className="text-[#FAFAF9] text-xs font-semibold mb-2">盈利能力对比</p>
            <div className="h-12 flex items-end justify-around gap-1">
              <div className="flex gap-0.5">
                <div className="w-2.5 h-2 bg-[#6366F1] rounded-t" />
                <div className="w-2.5 h-10 bg-[#60A5FA] rounded-t" />
              </div>
              <div className="flex gap-0.5">
                <div className="w-2.5 h-5 bg-[#6366F1] rounded-t" />
                <div className="w-2.5 h-3 bg-[#60A5FA] rounded-t" />
              </div>
              <div className="flex gap-0.5">
                <div className="w-2.5 h-1 bg-[#6366F1] rounded-t" />
                <div className="w-2.5 h-2 bg-[#60A5FA] rounded-t" />
              </div>
            </div>
          </div>
          <div className="flex-1 bg-[#16161A] rounded-xl p-3 border border-[#2A2A2E]">
            <p className="text-[#FAFAF9] text-xs font-semibold mb-2">偿债能力对比</p>
            <div className="h-12 flex items-end justify-around gap-1">
              <div className="flex gap-0.5">
                <div className="w-2.5 h-10 bg-[#6366F1] rounded-t" />
                <div className="w-2.5 h-9 bg-[#60A5FA] rounded-t" />
              </div>
              <div className="flex gap-0.5">
                <div className="w-2.5 h-1 bg-[#6366F1] rounded-t" />
                <div className="w-2.5 h-1 bg-[#60A5FA] rounded-t" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Back Button */}
      <Link
        href="/"
        className="flex items-center justify-center gap-2 bg-[#1A1A1E] text-[#FAFAF9] rounded-xl py-3 px-4 font-medium text-sm border border-[#2A2A2E] hover:border-[#32D583] transition-all"
      >
        <ArrowLeft size={16} />
        返回仪表盘
      </Link>
    </div>
  );
}
