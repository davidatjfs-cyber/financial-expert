'use client';

import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import { ArrowLeft } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getReportMetrics, getReports, type Metric, type Report } from '@/services/api';

type CompareRow = {
  metric: string;
  company1: string;
  company2: string;
  highlight: 0 | 1 | 2;
};

const METRICS: Array<{ code: string; name: string; isPct?: boolean; higherIsBetter?: boolean }> = [
  { code: 'GROSS_MARGIN', name: '毛利率', isPct: true, higherIsBetter: true },
  { code: 'NET_MARGIN', name: '净利率', isPct: true, higherIsBetter: true },
  { code: 'ROE', name: 'ROE', isPct: true, higherIsBetter: true },
  { code: 'ROA', name: 'ROA', isPct: true, higherIsBetter: true },
  { code: 'CURRENT_RATIO', name: '流动比率', isPct: false, higherIsBetter: true },
  { code: 'QUICK_RATIO', name: '速动比率', isPct: false, higherIsBetter: true },
  { code: 'DEBT_ASSET', name: '资产负债率', isPct: true, higherIsBetter: false },
  { code: 'ASSET_TURNOVER', name: '总资产周转率', isPct: false, higherIsBetter: true },
  { code: 'INVENTORY_TURNOVER', name: '存货周转率', isPct: false, higherIsBetter: true },
  { code: 'RECEIVABLE_TURNOVER', name: '应收账款周转率', isPct: false, higherIsBetter: true },
];

export default function ComparePage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [reportId1, setReportId1] = useState<string>('');
  const [reportId2, setReportId2] = useState<string>('');
  const [m1, setM1] = useState<Metric[]>([]);
  const [m2, setM2] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const r1 = useMemo(() => reports.find((r) => r.id === reportId1) || null, [reports, reportId1]);
  const r2 = useMemo(() => reports.find((r) => r.id === reportId2) || null, [reports, reportId2]);

  useEffect(() => {
    async function init() {
      setMessage('');
      try {
        const list = await getReports(50);
        setReports(list);
        if (list.length >= 2) {
          setReportId1(list[0].id);
          setReportId2(list[1].id);
        } else if (list.length === 1) {
          setReportId1(list[0].id);
        }
      } catch (e) {
        console.error(e);
        setMessage('加载报告列表失败');
      }
    }
    init();
  }, []);

  useEffect(() => {
    async function load() {
      if (!reportId1 || !reportId2 || reportId1 === reportId2) {
        return;
      }
      setLoading(true);
      setMessage('');
      try {
        const [a, b] = await Promise.all([getReportMetrics(reportId1), getReportMetrics(reportId2)]);
        setM1(a);
        setM2(b);
      } catch (e) {
        console.error(e);
        setM1([]);
        setM2([]);
        setMessage('加载对比指标失败');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [reportId1, reportId2]);

  const findMetric = (list: Metric[], code: string) => list.find((m) => m.metric_code === code)?.value ?? null;
  const fmt = (v: number | null, isPct?: boolean) => {
    if (v == null || Number.isNaN(v)) return '-';
    return isPct ? `${Number(v).toFixed(2)}%` : `${Number(v).toFixed(2)}`;
  };

  const rows: CompareRow[] = useMemo(() => {
    const out: CompareRow[] = [];
    for (const m of METRICS) {
      const v1 = findMetric(m1, m.code);
      const v2 = findMetric(m2, m.code);
      let highlight: 0 | 1 | 2 = 0;
      if (v1 != null && v2 != null) {
        const higherIsBetter = m.higherIsBetter !== false;
        if (higherIsBetter) {
          highlight = v1 > v2 ? 1 : v2 > v1 ? 2 : 0;
        } else {
          highlight = v1 < v2 ? 1 : v2 < v1 ? 2 : 0;
        }
      }
      out.push({ metric: m.name, company1: fmt(v1, m.isPct), company2: fmt(v2, m.isPct), highlight });
    }
    return out;
  }, [m1, m2]);

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
    const rows2 = rows.map((r) => [r.metric, r.company1, r.company2]);
    const esc = (s: any) => {
      const v = String(s ?? '');
      if (/[",\n]/.test(v)) return '"' + v.replace(/"/g, '""') + '"';
      return v;
    };
    const csv = [header, ...rows2].map((r) => r.map(esc).join(',')).join('\n');
    const name = `${(r1?.report_name || 'report1').slice(0, 12)}_vs_${(r2?.report_name || 'report2').slice(0, 12)}`;
    download(csv, `${name}.csv`, 'text/csv;charset=utf-8');
  };

  const exportHtml = () => {
    const rowsHtml = rows
      .map(
        (r) =>
          `<tr><td>${r.metric}</td><td>${r.company1}</td><td>${r.company2}</td></tr>`
      )
      .join('');
    const html = `<!doctype html><html><head><meta charset="utf-8" /><title>对比报告</title>
<style>body{font-family:Arial,Helvetica,sans-serif;padding:20px;} table{border-collapse:collapse;width:100%;} th,td{border:1px solid #ddd;padding:8px;} th{background:#f5f5f5;}</style>
</head><body><h2>多公司财务对比</h2><p>公司1：${r1?.report_name || '-'}</p><p>公司2：${r2?.report_name || '-'}</p><table><thead><tr><th>指标</th><th>公司1</th><th>公司2</th></tr></thead><tbody>${rowsHtml}</tbody></table></body></html>`;
    const name = `${(r1?.report_name || 'report1').slice(0, 12)}_vs_${(r2?.report_name || 'report2').slice(0, 12)}`;
    download(html, `${name}.html`, 'text/html;charset=utf-8');
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="bg-[#16161A] rounded-xl p-3 border border-[#6366F1]">
            <div className="text-[#6B6B70] text-xs mb-2">公司 1</div>
            <select
              value={reportId1}
              onChange={(e) => setReportId1(e.target.value)}
              className="w-full bg-[#0B0B0E] text-[#FAFAF9] rounded-xl px-3 py-3 text-sm border border-[#2A2A2E]"
            >
              <option value="">请选择报告</option>
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.report_name} - {r.period_end}
                </option>
              ))}
            </select>
            <div className="text-[#FAFAF9] text-sm font-semibold mt-2 truncate">{r1?.report_name || '-'}</div>
            <div className="text-[#6B6B70] text-xs truncate">{r1?.period_end || '-'}</div>
          </div>

          <div className="bg-[#16161A] rounded-xl p-3 border border-[#E85A4F]">
            <div className="text-[#6B6B70] text-xs mb-2">公司 2</div>
            <select
              value={reportId2}
              onChange={(e) => setReportId2(e.target.value)}
              className="w-full bg-[#0B0B0E] text-[#FAFAF9] rounded-xl px-3 py-3 text-sm border border-[#2A2A2E]"
            >
              <option value="">请选择报告</option>
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.report_name} - {r.period_end}
                </option>
              ))}
            </select>
            <div className="text-[#FAFAF9] text-sm font-semibold mt-2 truncate">{r2?.report_name || '-'}</div>
            <div className="text-[#6B6B70] text-xs truncate">{r2?.period_end || '-'}</div>
          </div>
        </div>

        {message && (
          <div className="mt-2 text-[#E85A4F] text-xs">{message}</div>
        )}
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
            disabled={loading || rows.length === 0}
            className="flex-1 bg-[#16161A] text-[#FAFAF9] rounded-xl py-3 px-4 font-medium text-sm border border-[#2A2A2E]"
          >
            ⬇️ 导出 CSV
          </button>
          <button
            onClick={exportHtml}
            disabled={loading || rows.length === 0}
            className="flex-1 bg-[#16161A] text-[#FAFAF9] rounded-xl py-3 px-4 font-medium text-sm border border-[#2A2A2E]"
          >
            ⬇️ 导出 HTML
          </button>
        </div>
        <div className="bg-[#16161A] rounded-xl overflow-hidden border border-[#2A2A2E]">
          {/* Header */}
          <div className="flex border-b border-[#2A2A2E] px-3 py-2">
            <div className="w-20 text-[#6B6B70] text-xs">指标</div>
            <div className="flex-1 text-center text-[#6366F1] text-xs truncate">{r1?.report_name || '公司1'}</div>
            <div className="flex-1 text-center text-[#E85A4F] text-xs truncate">{r2?.report_name || '公司2'}</div>
          </div>
          {/* Rows */}
          {rows.map((row, i) => (
            <div
              key={row.metric}
              className={`flex px-3 py-2 ${i < rows.length - 1 ? 'border-b border-[#2A2A2E]' : ''}`}
            >
              <div className="w-20 text-[#FAFAF9] text-xs">{row.metric}</div>
              <div className={`flex-1 text-center text-xs ${row.highlight === 1 ? 'text-[#32D583]' : (row.company1 === 'N/A' || row.company1 === '-') ? 'text-[#6B6B70]' : 'text-[#FAFAF9]'}`}>
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
