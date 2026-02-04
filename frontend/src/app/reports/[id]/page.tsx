'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, FileText, TrendingUp, AlertTriangle, Lightbulb, Brain, BarChart3, Download } from 'lucide-react';
import { getReportDetail, getReportMetrics, getReportAlerts, reanalyzeReport, type ReportDetail, type Metric, type Alert } from '@/services/api';

type TabType = 'overview' | 'metrics' | 'risks' | 'opportunities' | 'insights';

export default function ReportDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reportId = params.id as string;

  const [report, setReport] = useState<ReportDetail | null>(null);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [reanalyzing, setReanalyzing] = useState(false);
  const [pollTick, setPollTick] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [downloadTip, setDownloadTip] = useState<string | null>(null);

  async function fetchData() {
      try {
        const [reportData, metricsData, alertsData] = await Promise.all([
          getReportDetail(reportId),
          getReportMetrics(reportId),
          getReportAlerts(reportId),
        ]);
        setReport(reportData);
        setMetrics(metricsData);
        setAlerts(alertsData);
      } catch (error) {
        console.error('Failed to fetch report:', error);
      } finally {
        setLoading(false);
      }
  }

  useEffect(() => {
    if (reportId) {
      fetchData();
    }
  }, [reportId]);

  useEffect(() => {
    if (!reportId) return;
    if (!report) return;
    if (report.status !== 'running' && report.status !== 'pending') return;
    const t = setInterval(() => {
      setPollTick((x) => x + 1);
    }, 2500);
    return () => clearInterval(t);
  }, [reportId, report?.status]);

  useEffect(() => {
    if (!reportId) return;
    if (!report) return;
    if (report.status !== 'running' && report.status !== 'pending') return;
    fetchData();
  }, [pollTick]);

  const handleReanalyze = async () => {
    if (!reportId) return;
    setReanalyzing(true);
    try {
      await reanalyzeReport(reportId);
      setLoading(true);
      await fetchData();
    } catch (e) {
      console.error('Reanalyze failed:', e);
    } finally {
      setReanalyzing(false);
    }
  };

  const handleExportPdf = async () => {
    if (!reportId) return;
    setExporting(true);
    try {
      const resp = await fetch(`/api/reports/${encodeURIComponent(reportId)}/export/pdf`);
      if (!resp.ok) {
        throw new Error(`export_failed_${resp.status}`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = (report?.report_name || 'report').replace(/[/\\]/g, '-');
      const period = report?.period_end || 'period';
      a.download = `${safeName}-${period}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();

      const ua = typeof navigator !== 'undefined' ? navigator.userAgent : '';
      let tip = '已开始下载：请在浏览器的“下载”中查看文件';
      if (/MicroMessenger/i.test(ua)) {
        tip = '已开始下载：微信内置浏览器可能不显示下载记录，建议右上角菜单选择“在浏览器打开”后再下载';
      } else if (/iPhone|iPad|iPod/i.test(ua)) {
        tip = '已开始下载：请到“文件 App → 下载项”或 Safari 下载列表中查找';
      } else if (/Android/i.test(ua)) {
        tip = '已开始下载：请到“下载(Download)”文件夹或浏览器下载列表中查找';
      }
      setDownloadTip(tip);
      setTimeout(() => setDownloadTip(null), 8000);

      if (/MicroMessenger/i.test(ua) || /iPhone|iPad|iPod/i.test(ua)) {
        try {
          window.open(url, '_blank', 'noopener,noreferrer');
        } catch {
          // ignore
        }
      }

      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export PDF failed:', e);
    } finally {
      setExporting(false);
    }
  };

  const statusConfig = {
    done: { bg: 'bg-[#32D583]/20', text: 'text-[#32D583]', label: '已完成' },
    running: { bg: 'bg-[#FFB547]/20', text: 'text-[#FFB547]', label: '分析中' },
    failed: { bg: 'bg-[#E85A4F]/20', text: 'text-[#E85A4F]', label: '失败' },
    pending: { bg: 'bg-[#6B6B70]/20', text: 'text-[#6B6B70]', label: '待识别' },
  };

  const tabs: { key: TabType; label: string }[] = [
    { key: 'overview', label: '概览' },
    { key: 'metrics', label: '财务指标' },
    { key: 'risks', label: '风险分析' },
    { key: 'opportunities', label: '机会识别' },
    { key: 'insights', label: 'AI 洞察' },
  ];

  const formatDateTime = (tsSeconds: number) => {
    const d = new Date(tsSeconds * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  if (loading) {
    return (
      <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
        <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
          <p className="text-[#6B6B70] text-base">加载中...</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
        <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
          <p className="text-[#6B6B70] text-base">报告不存在</p>
          <button
            onClick={() => router.back()}
            className="mt-4 text-[#32D583]"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  const status = statusConfig[report.status as keyof typeof statusConfig] || statusConfig.pending;

  // 计算关键指标
  const latestMetrics = metrics.filter(m => m.period_end === report.period_end);
  const grossMargin = latestMetrics.find(m => m.metric_code === 'GROSS_MARGIN');
  const netMargin = latestMetrics.find(m => m.metric_code === 'NET_MARGIN');
  const roe = latestMetrics.find(m => m.metric_code === 'ROE');
  const roa = latestMetrics.find(m => m.metric_code === 'ROA');
  const currentRatio = latestMetrics.find(m => m.metric_code === 'CURRENT_RATIO');
  const debtRatio = latestMetrics.find(m => m.metric_code === 'DEBT_ASSET');
  const quickRatio = latestMetrics.find(m => m.metric_code === 'QUICK_RATIO');
  const assetTurnover = latestMetrics.find(m => m.metric_code === 'ASSET_TURNOVER');
  const inventoryTurnover = latestMetrics.find(m => m.metric_code === 'INVENTORY_TURNOVER');
  const receivableTurnover = latestMetrics.find(m => m.metric_code === 'RECEIVABLE_TURNOVER');

  // 风险指标
  const highRiskAlerts = alerts.filter(a => a.level === 'high');
  const mediumRiskAlerts = alerts.filter(a => a.level === 'medium');

  // 行业平均指标（示例数据，实际应从API获取）
  const industryAvg = {
    grossMargin: 35.0,
    netMargin: 10.0,
    roe: 15.0,
    roa: 8.0,
    currentRatio: 1.5,
    debtRatio: 50.0,
    assetTurnover: 0.8,
  };

  // 计算与行业平均的对比
  const compareToIndustry = (value: number | null | undefined, avg: number) => {
    if (value == null) return { diff: 0, status: 'neutral' as const };
    const diff = ((value - avg) / avg) * 100;
    return {
      diff,
      status: diff > 10 ? 'good' as const : diff < -10 ? 'bad' as const : 'neutral' as const,
    };
  };

  const metricValue = (m?: Metric | undefined) => (m?.value == null ? null : m.value);
  const fmtMetric = (v: number | null | undefined, digits = 2) => (v == null ? '-' : v.toFixed(digits));
  const diffBadge = (cmp: { diff: number; status: 'good' | 'bad' | 'neutral' }, betterWhen: 'higher' | 'lower' = 'higher') => {
    let status = cmp.status;
    if (betterWhen === 'lower') {
      status = cmp.status === 'good' ? 'bad' : (cmp.status === 'bad' ? 'good' : 'neutral');
    }
    const cls = status === 'good'
      ? 'bg-[#32D583]/20 text-[#32D583]'
      : status === 'bad'
        ? 'bg-[#E85A4F]/20 text-[#E85A4F]'
        : 'bg-[#6B6B70]/20 text-[#6B6B70]';
    const sign = cmp.diff > 0 ? '+' : '';
    return <span className={`text-xs px-2 py-1 rounded ${cls}`}>{sign}{cmp.diff.toFixed(1)}%</span>;
  };

  return (
    <div className="p-4 md:p-6 flex flex-col gap-4 max-w-2xl mx-auto pb-[calc(env(safe-area-inset-bottom,0px)+140px)]">
      {/* Header with Back Button */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="w-10 h-10 rounded-xl bg-[#16161A] border border-[#2A2A2E] flex items-center justify-center flex-shrink-0"
        >
          <ArrowLeft size={20} className="text-[#FAFAF9]" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-[#FAFAF9] text-lg font-semibold truncate">{report.report_name}</h1>
          <p className="text-[#6B6B70] text-sm">
            {report.source_type === 'market_fetch' ? '市场数据' : '文件上传'} · {formatDateTime(report.created_at)}
          </p>
        </div>
        <button
          onClick={handleExportPdf}
          disabled={exporting}
          className="h-10 px-4 rounded-xl bg-[#16161A] border border-[#2A2A2E] text-[#FAFAF9] text-sm font-semibold flex items-center gap-2 disabled:opacity-50"
        >
          <Download size={16} />
          {exporting ? '导出中...' : '导出 PDF'}
        </button>
      </div>

      {downloadTip && (
        <div className="bg-[#6366F1]/10 rounded-xl p-3 border border-[#6366F1]/30 text-[#FAFAF9] text-sm">
          {downloadTip}
        </div>
      )}

      {/* Status Card */}
      <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${status.bg} flex items-center justify-center`}>
              <FileText size={20} className={status.text} />
            </div>
            <div>
              <div className="text-[#FAFAF9] text-sm font-semibold">报告状态</div>
              <div className={`text-xs ${status.text}`}>{status.label}</div>
            </div>
          </div>
          <div className="text-right min-w-[80px]">
            <div className="text-[#6B6B70] text-xs">报告类型</div>
            <div className="text-[#FAFAF9] text-sm font-medium">{report.period_type === 'annual' ? '年度报告' : '季度报告'}</div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="bg-[#0B0B0E] rounded-xl p-3">
            <div className="text-[#6B6B70] text-xs">市场</div>
            <div className="text-[#FAFAF9] text-sm font-semibold mt-1">{report.market || '-'}</div>
          </div>
          <div className="bg-[#0B0B0E] rounded-xl p-3">
            <div className="text-[#6B6B70] text-xs">所属行业</div>
            <div className="text-[#FAFAF9] text-sm font-semibold mt-1">{report.industry_code || '-'}</div>
          </div>
        </div>

        {(report.status === 'running' || report.status === 'pending') && (
          <div className="mt-4 bg-[#FFB547]/10 border border-[#FFB547]/30 rounded-xl p-3">
            <div className="text-[#FAFAF9] text-sm font-semibold">分析进度</div>
            <div className="text-[#6B6B70] text-xs mt-1">
              {report.source_type === 'file_upload'
                ? '上传完成 → 文本提取 → 指标计算 → 风险/机会生成 → 入库'
                : '拉取财报 → 指标计算 → 风险/机会生成 → 入库'}
            </div>
            <div className="mt-2 h-2 w-full bg-[#0B0B0E] rounded-full overflow-hidden">
              <div className="h-full w-1/2 bg-[#FFB547] rounded-full animate-pulse" />
            </div>
            <div className="text-[#6B6B70] text-xs mt-2">页面将自动刷新状态与结果…</div>
          </div>
        )}

        {report.status === 'failed' && report.error_message && (
          <div className="mt-4 bg-[#E85A4F]/10 border border-[#E85A4F]/30 rounded-xl p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="text-[#E85A4F] mt-0.5 flex-shrink-0" />
              <div className="min-w-0">
                <div className="text-[#E85A4F] text-sm font-semibold">失败原因</div>
                <div className="text-[#E85A4F] text-xs mt-1 break-words">{report.error_message}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {report.source_type === 'market_fetch' && report.status !== 'done' && metrics.length === 0 && (
        <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
          <div className="text-[#FAFAF9] text-sm font-semibold">数据状态</div>
          <div className="text-[#6B6B70] text-sm mt-2">
            {report.status === 'running' || report.status === 'pending'
              ? '报告正在生成中，请稍等片刻后返回刷新。'
              : '当前报告没有生成可展示的指标数据。'}
          </div>
          <div className="text-[#6B6B70] text-xs mt-2">财报期末：{report.period_end}</div>
        </div>
      )}

      {report.source_type === 'file_upload' && metrics.length === 0 && report.status !== 'running' && (
        <button
          onClick={handleReanalyze}
          disabled={reanalyzing}
          className="w-full bg-[#6366F1] text-white rounded-2xl py-4 px-6 font-semibold text-base disabled:opacity-50"
        >
          {reanalyzing ? '重新分析中...' : '重新分析上传文件'}
        </button>
      )}

      {/* Tabs - 横向滚动 */}
      <div className="overflow-x-auto -mx-4 px-4">
        <div className="flex gap-2 min-w-max">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap ${
                activeTab === tab.key
                  ? 'bg-[#FAFAF9] text-[#0B0B0E]'
                  : 'bg-[#16161A] text-[#6B6B70] border border-[#2A2A2E]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content based on active tab */}
      {activeTab === 'overview' && (
        <div className="flex flex-col gap-4">
          {/* 盈利能力 - 含行业对比 */}
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[#FAFAF9] text-sm font-semibold">盈利能力</h3>
              <span className="text-[#6B6B70] text-xs">vs 行业平均</span>
            </div>
            <div className="space-y-3">
              {/* 毛利率 */}
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">毛利率</span>
                  <span className="text-[#6B6B70] text-xs">行业: {industryAvg.grossMargin}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#32D583] text-xl font-bold">{grossMargin?.value?.toFixed(2) || '-'}%</span>
                  {grossMargin?.value != null && (
                    <span className={`text-xs px-2 py-1 rounded ${
                      compareToIndustry(grossMargin.value, industryAvg.grossMargin).status === 'good' ? 'bg-[#32D583]/20 text-[#32D583]' :
                      compareToIndustry(grossMargin.value, industryAvg.grossMargin).status === 'bad' ? 'bg-[#E85A4F]/20 text-[#E85A4F]' :
                      'bg-[#6B6B70]/20 text-[#6B6B70]'
                    }`}>
                      {compareToIndustry(grossMargin.value, industryAvg.grossMargin).diff > 0 ? '+' : ''}{compareToIndustry(grossMargin.value, industryAvg.grossMargin).diff.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
              {/* 净利率 */}
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">净利率</span>
                  <span className="text-[#6B6B70] text-xs">行业: {industryAvg.netMargin}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#32D583] text-xl font-bold">{netMargin?.value?.toFixed(2) || '-'}%</span>
                  {netMargin?.value != null && (
                    <span className={`text-xs px-2 py-1 rounded ${
                      compareToIndustry(netMargin.value, industryAvg.netMargin).status === 'good' ? 'bg-[#32D583]/20 text-[#32D583]' :
                      compareToIndustry(netMargin.value, industryAvg.netMargin).status === 'bad' ? 'bg-[#E85A4F]/20 text-[#E85A4F]' :
                      'bg-[#6B6B70]/20 text-[#6B6B70]'
                    }`}>
                      {compareToIndustry(netMargin.value, industryAvg.netMargin).diff > 0 ? '+' : ''}{compareToIndustry(netMargin.value, industryAvg.netMargin).diff.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
              {/* ROE */}
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">ROE (净资产收益率)</span>
                  <span className="text-[#6B6B70] text-xs">行业: {industryAvg.roe}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#6366F1] text-xl font-bold">{roe?.value?.toFixed(2) || '-'}%</span>
                  {roe?.value != null && (
                    <span className={`text-xs px-2 py-1 rounded ${
                      compareToIndustry(roe.value, industryAvg.roe).status === 'good' ? 'bg-[#32D583]/20 text-[#32D583]' :
                      compareToIndustry(roe.value, industryAvg.roe).status === 'bad' ? 'bg-[#E85A4F]/20 text-[#E85A4F]' :
                      'bg-[#6B6B70]/20 text-[#6B6B70]'
                    }`}>
                      {compareToIndustry(roe.value, industryAvg.roe).diff > 0 ? '+' : ''}{compareToIndustry(roe.value, industryAvg.roe).diff.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
              {/* ROA */}
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">ROA (总资产收益率)</span>
                  <span className="text-[#6B6B70] text-xs">行业: {industryAvg.roa}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#6366F1] text-xl font-bold">{roa?.value?.toFixed(2) || '-'}%</span>
                  {roa?.value != null && (
                    <span className={`text-xs px-2 py-1 rounded ${
                      compareToIndustry(roa.value, industryAvg.roa).status === 'good' ? 'bg-[#32D583]/20 text-[#32D583]' :
                      compareToIndustry(roa.value, industryAvg.roa).status === 'bad' ? 'bg-[#E85A4F]/20 text-[#E85A4F]' :
                      'bg-[#6B6B70]/20 text-[#6B6B70]'
                    }`}>
                      {compareToIndustry(roa.value, industryAvg.roa).diff > 0 ? '+' : ''}{compareToIndustry(roa.value, industryAvg.roa).diff.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* 偿债能力 - 含行业对比 */}
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[#FAFAF9] text-sm font-semibold">偿债能力</h3>
              <span className="text-[#6B6B70] text-xs">vs 行业平均</span>
            </div>
            <div className="space-y-3">
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">流动比率</span>
                  <span className="text-[#6B6B70] text-xs">行业: {industryAvg.currentRatio}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#32D583] text-xl font-bold">{currentRatio?.value?.toFixed(2) || '-'}</span>
                  {currentRatio?.value != null && (
                    <span className={`text-xs px-2 py-1 rounded ${
                      compareToIndustry(currentRatio.value, industryAvg.currentRatio).status === 'good' ? 'bg-[#32D583]/20 text-[#32D583]' :
                      compareToIndustry(currentRatio.value, industryAvg.currentRatio).status === 'bad' ? 'bg-[#E85A4F]/20 text-[#E85A4F]' :
                      'bg-[#6B6B70]/20 text-[#6B6B70]'
                    }`}>
                      {compareToIndustry(currentRatio.value, industryAvg.currentRatio).diff > 0 ? '+' : ''}{compareToIndustry(currentRatio.value, industryAvg.currentRatio).diff.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">速动比率</span>
                  <span className="text-[#6B6B70] text-xs">行业: 1.0</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#32D583] text-xl font-bold">{latestMetrics.find(m => m.metric_code === 'QUICK_RATIO')?.value?.toFixed(2) || '-'}</span>
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#6B6B70] text-xs">资产负债率</span>
                  <span className="text-[#6B6B70] text-xs">行业: {industryAvg.debtRatio}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className={`text-xl font-bold ${(debtRatio?.value || 0) > 70 ? 'text-[#E85A4F]' : 'text-[#32D583]'}`}>{debtRatio?.value?.toFixed(2) || '-'}%</span>
                  {debtRatio?.value != null && (
                    <span className={`text-xs px-2 py-1 rounded ${
                      debtRatio.value < industryAvg.debtRatio ? 'bg-[#32D583]/20 text-[#32D583]' : 'bg-[#E85A4F]/20 text-[#E85A4F]'
                    }`}>
                      {debtRatio.value < industryAvg.debtRatio ? '低于行业' : '高于行业'}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* 运营效率 */}
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <h3 className="text-[#FAFAF9] text-sm font-semibold mb-3">运营效率</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between bg-[#0B0B0E] rounded-xl p-3">
                <span className="text-[#6B6B70] text-sm">总资产周转率</span>
                <span className="text-[#FFB547] text-lg font-bold">{latestMetrics.find(m => m.metric_code === 'ASSET_TURNOVER')?.value?.toFixed(2) || '-'}</span>
              </div>
              <div className="flex items-center justify-between bg-[#0B0B0E] rounded-xl p-3">
                <span className="text-[#6B6B70] text-sm">存货周转率</span>
                <span className="text-[#FFB547] text-lg font-bold">{latestMetrics.find(m => m.metric_code === 'INVENTORY_TURNOVER')?.value?.toFixed(2) || '-'}</span>
              </div>
              <div className="flex items-center justify-between bg-[#0B0B0E] rounded-xl p-3">
                <span className="text-[#6B6B70] text-sm">应收账款周转率</span>
                <span className="text-[#FFB547] text-lg font-bold">{latestMetrics.find(m => m.metric_code === 'RECEIVABLE_TURNOVER')?.value?.toFixed(2) || '-'}</span>
              </div>
            </div>
          </div>

        </div>
      )}

      {activeTab === 'metrics' && (
        <div className="flex flex-col gap-4">
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[#FAFAF9] text-sm font-semibold">核心指标（含行业对比）</div>
                <div className="text-[#6B6B70] text-xs mt-1">左右滑动查看更多列</div>
              </div>
              <div className="text-[#6B6B70] text-xs">期末：{report.period_end}</div>
            </div>

            <div className="overflow-x-auto -mx-4 px-4 mt-3">
              <table className="min-w-[720px] w-full border-separate border-spacing-y-2">
                <thead>
                  <tr className="text-left text-[#6B6B70] text-xs">
                    <th className="px-3">指标</th>
                    <th className="px-3">本期</th>
                    <th className="px-3">单位</th>
                    <th className="px-3">行业均值</th>
                    <th className="px-3">差异</th>
                    <th className="px-3">解读</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">毛利率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(grossMargin))}%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.grossMargin}%</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(grossMargin), industryAvg.grossMargin), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">产品/服务定价与成本控制能力</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">净利率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(netMargin))}%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.netMargin}%</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(netMargin), industryAvg.netMargin), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">费用结构与经营效率综合体现</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">ROE</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(roe))}%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.roe}%</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(roe), industryAvg.roe), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">股东资本回报能力（杜邦核心）</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">ROA</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(roa))}%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.roa}%</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(roa), industryAvg.roa), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">资产创造利润的效率</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">流动比率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(currentRatio))}</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">倍</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.currentRatio}</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(currentRatio), industryAvg.currentRatio), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">短期偿债安全边际</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">速动比率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(quickRatio))}</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">倍</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">1.0</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(quickRatio), 1.0), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">剔除存货后的短债覆盖</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">资产负债率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(debtRatio))}%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">%</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.debtRatio}%</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(debtRatio), industryAvg.debtRatio), 'lower')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">杠杆水平与财务弹性</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">总资产周转率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(assetTurnover))}</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">次</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">{industryAvg.assetTurnover}</td>
                    <td className="px-3 py-3">{diffBadge(compareToIndustry(metricValue(assetTurnover), industryAvg.assetTurnover), 'higher')}</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">资产利用效率与周转速度</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">存货周转率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(inventoryTurnover))}</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">次</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">-</td>
                    <td className="px-3 py-3">-</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">库存管理效率（缺行业数据）</td>
                  </tr>
                  <tr className="bg-[#0B0B0E]">
                    <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">应收周转率</td>
                    <td className="px-3 py-3 text-[#FAFAF9] text-sm">{fmtMetric(metricValue(receivableTurnover))}</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">次</td>
                    <td className="px-3 py-3 text-[#6B6B70] text-sm">-</td>
                    <td className="px-3 py-3">-</td>
                    <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">回款与信用政策效果（缺行业数据）</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <div className="text-[#FAFAF9] text-sm font-semibold">全部指标（按报告期）</div>
            <div className="text-[#6B6B70] text-xs mt-1">支持横向滚动查看较长字段</div>
            <div className="overflow-x-auto -mx-4 px-4 mt-3">
              <table className="min-w-[680px] w-full border-separate border-spacing-y-2">
                <thead>
                  <tr className="text-left text-[#6B6B70] text-xs">
                    <th className="px-3">指标</th>
                    <th className="px-3">值</th>
                    <th className="px-3">单位</th>
                    <th className="px-3">报告期</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.length > 0 ? metrics
                    .slice()
                    .sort((a, b) => (b.period_end || '').localeCompare(a.period_end || ''))
                    .map((m, idx) => (
                      <tr key={idx} className="bg-[#0B0B0E]">
                        <td className="px-3 py-3 rounded-l-xl text-[#FAFAF9] text-sm">{m.metric_name}</td>
                        <td className="px-3 py-3 text-[#FAFAF9] text-sm">{m.value == null ? '-' : m.value.toFixed(2)}</td>
                        <td className="px-3 py-3 text-[#6B6B70] text-sm">{m.unit || ''}</td>
                        <td className="px-3 py-3 rounded-r-xl text-[#6B6B70] text-sm">{m.period_end}</td>
                      </tr>
                    ))
                    : (
                      <tr className="bg-[#0B0B0E]">
                        <td className="px-3 py-3 rounded-xl text-[#6B6B70] text-sm" colSpan={4}>暂无财务指标数据</td>
                      </tr>
                    )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'risks' && (
        <div className="flex flex-col gap-3">
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <div className="text-[#FAFAF9] text-sm font-semibold">专业风险分析（基于指标）</div>
            <div className="text-[#6B6B70] text-xs mt-1">结合盈利、杠杆、偿债、效率与行业对比输出</div>
            <div className="mt-3 space-y-3">
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">盈利与费用结构风险</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(netMargin);
                    if (v == null) return '净利率数据缺失，建议补齐利润表相关字段以提高分析质量。';
                    if (v < industryAvg.netMargin) {
                      return `净利率 ${fmtMetric(v)}% 低于行业均值 ${industryAvg.netMargin}%，需关注费用率、一次性损益与价格竞争导致的利润挤压。`;
                    }
                    return `净利率 ${fmtMetric(v)}% 高于行业均值 ${industryAvg.netMargin}%，但仍需关注高利润是否来自阶段性红利（原材料、补贴、资产处置等）。`;
                  })()}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">杠杆与再融资风险</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(debtRatio);
                    if (v == null) return '资产负债率数据缺失，建议补齐资产负债表相关字段。';
                    if (v > 70) {
                      return `资产负债率 ${fmtMetric(v)}% 偏高，利率上行或现金流波动时可能带来再融资压力，需重点关注短期债务结构与融资成本。`;
                    }
                    return `资产负债率 ${fmtMetric(v)}% 处于可控区间，但仍建议关注表外负债与或有事项（担保/诉讼/回购条款）。`;
                  })()}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">短期偿债与流动性风险</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(currentRatio);
                    if (v == null) return '流动比率数据缺失，建议补齐流动资产/流动负债相关字段。';
                    if (v < 1) {
                      return `流动比率 ${fmtMetric(v)} 偏低，短期偿债安全边际不足；若同时出现应收回款变慢或存货积压，风险将放大。`;
                    }
                    return `流动比率 ${fmtMetric(v)} 尚可，仍建议结合速动比率与经营性现金流一起判断真实流动性。`;
                  })()}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">运营效率与周转风险</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(assetTurnover);
                    if (v == null) return '总资产周转率数据缺失，建议补齐收入/资产规模相关字段。';
                    if (v < industryAvg.assetTurnover) {
                      return `总资产周转率 ${fmtMetric(v)} 低于行业均值 ${industryAvg.assetTurnover}，可能存在产能利用率偏低或资本开支效率不高的问题。`;
                    }
                    return `总资产周转率 ${fmtMetric(v)} 不低于行业均值 ${industryAvg.assetTurnover}，运营效率相对稳健。`;
                  })()}
                </div>
              </div>
            </div>
          </div>

          {alerts.length > 0 ? (
            alerts.map((alert) => {
              const alertColors = {
                high: { bg: 'bg-[#E85A4F]/20', text: 'text-[#E85A4F]', label: '高风险' },
                medium: { bg: 'bg-[#FFB547]/20', text: 'text-[#FFB547]', label: '中风险' },
                low: { bg: 'bg-[#32D583]/20', text: 'text-[#32D583]', label: '低风险' },
              };
              const color = alertColors[alert.level] || alertColors.medium;
              return (
                <div key={alert.id} className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E]">
                  <div className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-lg ${color.bg} flex items-center justify-center flex-shrink-0`}>
                      <AlertTriangle size={16} className={color.text} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[#FAFAF9] text-sm font-medium">{alert.title}</span>
                        <span className={`text-xs px-2 py-0.5 rounded ${color.bg} ${color.text}`}>{color.label}</span>
                      </div>
                      <div className="text-[#6B6B70] text-xs">{alert.message}</div>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="bg-[#16161A] rounded-2xl p-8 border border-[#2A2A2E] text-center">
              <div className="w-16 h-16 rounded-full bg-[#32D583]/20 flex items-center justify-center mx-auto mb-4">
                <AlertTriangle size={32} className="text-[#32D583]" />
              </div>
              <p className="text-[#FAFAF9] text-base font-medium mb-2">暂无风险预警</p>
              <p className="text-[#6B6B70] text-sm">该公司财务状况良好</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'opportunities' && (
        <div className="flex flex-col gap-3">
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <div className="text-[#FAFAF9] text-sm font-semibold">机会识别（基于财务质量与行业对比）</div>
            <div className="text-[#6B6B70] text-xs mt-1">覆盖盈利弹性、资本效率、负债结构与经营效率</div>
            <div className="mt-3 space-y-3">
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">利润率与议价能力</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(grossMargin);
                    if (v == null) return '毛利率数据缺失，建议补齐成本/收入口径后再评估盈利弹性。';
                    if (v >= industryAvg.grossMargin) {
                      return `毛利率 ${fmtMetric(v)}% 不低于行业均值 ${industryAvg.grossMargin}%，若在竞争加剧环境下仍能维持，体现较强议价能力。`;
                    }
                    return `毛利率 ${fmtMetric(v)}% 低于行业均值 ${industryAvg.grossMargin}%，若未来通过产品结构升级/提价/降本改善，可能带来利润弹性。`;
                  })()}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">资本效率提升空间</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(roe);
                    if (v == null) return 'ROE 数据缺失，建议补齐净利润与净资产口径。';
                    if (v > industryAvg.roe) {
                      return `ROE ${fmtMetric(v)}% 高于行业均值 ${industryAvg.roe}%，若盈利可持续，具备长期复利潜力。`;
                    }
                    return `ROE ${fmtMetric(v)}% 低于行业均值 ${industryAvg.roe}%，通过改善利润率、周转率或优化资本结构存在提升空间。`;
                  })()}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">稳健的财务结构带来的抗风险优势</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(debtRatio);
                    if (v == null) return '资产负债率数据缺失，建议补齐资产负债表口径。';
                    if (v < industryAvg.debtRatio) {
                      return `资产负债率 ${fmtMetric(v)}% 低于行业均值 ${industryAvg.debtRatio}%，在周期波动或融资收紧时更具抗风险能力。`;
                    }
                    return `资产负债率 ${fmtMetric(v)}% 不低于行业均值 ${industryAvg.debtRatio}%，若公司具备稳定现金流，仍可能通过杠杆放大 ROE。`;
                  })()}
                </div>
              </div>
              <div className="bg-[#0B0B0E] rounded-xl p-3">
                <div className="text-[#FAFAF9] text-sm font-semibold">经营效率改善机会</div>
                <div className="text-[#6B6B70] text-xs mt-1">
                  {(() => {
                    const v = metricValue(assetTurnover);
                    if (v == null) return '总资产周转率数据缺失，建议补齐收入与资产规模。';
                    if (v < industryAvg.assetTurnover) {
                      return `总资产周转率 ${fmtMetric(v)} 低于行业均值 ${industryAvg.assetTurnover}，若通过渠道效率、产能利用率或库存周转改善，有望提升 ROA/ROE。`;
                    }
                    return `总资产周转率 ${fmtMetric(v)} 不低于行业均值 ${industryAvg.assetTurnover}，运营效率具备一定优势。`;
                  })()}
                </div>
              </div>
            </div>
          </div>

          {netMargin && netMargin.value !== null && netMargin.value > 15 && (
            <div className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E]">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-[#32D583]/20 flex items-center justify-center flex-shrink-0">
                  <Lightbulb size={16} className="text-[#32D583]" />
                </div>
                <div>
                  <div className="text-[#FAFAF9] text-sm font-medium mb-1">高盈利能力</div>
                  <div className="text-[#6B6B70] text-xs">净利率 {netMargin.value.toFixed(2)}% 高于行业平均水平，表明公司具有较强的盈利能力和定价权</div>
                </div>
              </div>
            </div>
          )}
          {roe && roe.value !== null && roe.value > 15 && (
            <div className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E]">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-[#6366F1]/20 flex items-center justify-center flex-shrink-0">
                  <TrendingUp size={16} className="text-[#6366F1]" />
                </div>
                <div>
                  <div className="text-[#FAFAF9] text-sm font-medium mb-1">优秀的股东回报</div>
                  <div className="text-[#6B6B70] text-xs">ROE {roe.value.toFixed(2)}% 表明公司能够有效利用股东资本创造价值</div>
                </div>
              </div>
            </div>
          )}
          {currentRatio && currentRatio.value !== null && currentRatio.value > 2 && (
            <div className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E]">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-[#FFB547]/20 flex items-center justify-center flex-shrink-0">
                  <BarChart3 size={16} className="text-[#FFB547]" />
                </div>
                <div>
                  <div className="text-[#FAFAF9] text-sm font-medium mb-1">充裕的流动性</div>
                  <div className="text-[#6B6B70] text-xs">流动比率 {currentRatio.value.toFixed(2)} 表明公司具有较强的短期偿债能力</div>
                </div>
              </div>
            </div>
          )}
          {(!netMargin || !netMargin.value || netMargin.value <= 15) && (!roe || !roe.value || roe.value <= 15) && (!currentRatio || !currentRatio.value || currentRatio.value <= 2) && (
            <div className="bg-[#16161A] rounded-2xl p-8 border border-[#2A2A2E] text-center">
              <div className="w-16 h-16 rounded-full bg-[#6B6B70]/20 flex items-center justify-center mx-auto mb-4">
                <Lightbulb size={32} className="text-[#6B6B70]" />
              </div>
              <p className="text-[#FAFAF9] text-base font-medium mb-2">暂无明显投资机会</p>
              <p className="text-[#6B6B70] text-sm">需要更多数据进行分析</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'insights' && (
        <div className="flex flex-col gap-3">
          <div className="bg-gradient-to-br from-[#6366F1]/20 to-[#16161A] rounded-2xl p-5 border border-[#6366F1]/30">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-[#6366F1]/20 flex items-center justify-center">
                <Brain size={20} className="text-[#6366F1]" />
              </div>
              <div>
                <div className="text-[#FAFAF9] text-base font-semibold">AI 分析洞察</div>
                <div className="text-[#6B6B70] text-xs">基于财务数据的智能分析</div>
              </div>
            </div>
            {metrics.length > 0 ? (
              <div className="space-y-3 text-sm text-[#FAFAF9]">
                <p>
                  📊 <strong>盈利能力分析：</strong>
                  {grossMargin?.value != null && netMargin?.value != null ? (
                    `毛利率 ${grossMargin.value.toFixed(1)}%，净利率 ${netMargin.value.toFixed(1)}%，${netMargin.value > 10 ? '盈利能力较强' : '盈利能力一般'}。`
                  ) : '数据不足，无法分析盈利能力。'}
                </p>
                <p>
                  💰 <strong>资本效率：</strong>
                  {roe?.value != null && roa?.value != null ? (
                    `ROE ${roe.value.toFixed(1)}%，ROA ${roa.value.toFixed(1)}%，${roe.value > 15 ? '资本运用效率优秀' : '资本运用效率一般'}。`
                  ) : '数据不足，无法分析资本效率。'}
                </p>
                <p>
                  🏦 <strong>财务健康：</strong>
                  {debtRatio?.value != null && currentRatio?.value != null ? (
                    `资产负债率 ${debtRatio.value.toFixed(1)}%，流动比率 ${currentRatio.value.toFixed(2)}，${debtRatio.value < 60 ? '财务结构稳健' : '需关注债务风险'}。`
                  ) : '数据不足，无法分析财务健康状况。'}
                </p>
              </div>
            ) : (
              <p className="text-[#6B6B70] text-sm">暂无足够数据生成AI洞察，请确保报告已完成分析。</p>
            )}
          </div>

          {/* AI 建议 */}
          {metrics.length > 0 && (
            <div className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E]">
              <h4 className="text-[#FAFAF9] text-sm font-semibold mb-3">💡 投资建议</h4>
              <div className="text-[#6B6B70] text-xs space-y-2">
                {roe?.value != null && roe.value > 20 && <p>• 高ROE表明公司具有竞争优势，可考虑长期持有</p>}
                {debtRatio?.value != null && debtRatio.value > 70 && <p>• 负债率偏高，需关注偿债风险和利率变化影响</p>}
                {netMargin?.value != null && netMargin.value > 20 && <p>• 净利率优秀，关注是否可持续及行业竞争态势</p>}
                {currentRatio?.value != null && currentRatio.value < 1 && <p>• 流动比率偏低，需关注短期偿债能力</p>}
                <p>• 建议结合行业对比和历史趋势进行综合判断</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
