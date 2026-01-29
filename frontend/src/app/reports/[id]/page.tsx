'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, FileText, TrendingUp, AlertTriangle, Lightbulb, Brain, BarChart3 } from 'lucide-react';
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

  return (
    <div className="p-4 md:p-6 flex flex-col gap-4 max-w-2xl mx-auto pb-24">
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
          <p className="text-[#6B6B70] text-sm">{report.source_type === 'market_fetch' ? '市场数据' : '文件上传'} · {report.period_end}</p>
        </div>
      </div>

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
      </div>

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

          {/* 风险概览 */}
          <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
            <h3 className="text-[#FAFAF9] text-sm font-semibold mb-3">风险概览</h3>
            <div className="flex gap-2">
              <div className="flex-1 bg-[#E85A4F]/10 rounded-xl p-3 text-center">
                <div className="text-[#E85A4F] text-xl font-bold">{highRiskAlerts.length}</div>
                <div className="text-[#6B6B70] text-xs">高风险</div>
              </div>
              <div className="flex-1 bg-[#FFB547]/10 rounded-xl p-3 text-center">
                <div className="text-[#FFB547] text-xl font-bold">{mediumRiskAlerts.length}</div>
                <div className="text-[#6B6B70] text-xs">中风险</div>
              </div>
              <div className="flex-1 bg-[#32D583]/10 rounded-xl p-3 text-center">
                <div className="text-[#32D583] text-xl font-bold">{metrics.length}</div>
                <div className="text-[#6B6B70] text-xs">指标数</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'metrics' && (
        <div className="flex flex-col gap-3">
          {metrics.length > 0 ? (
            metrics.slice(0, 30).map((metric, index) => (
              <div
                key={index}
                className="bg-[#16161A] rounded-xl p-4 border border-[#2A2A2E] flex items-center justify-between"
              >
                <div>
                  <div className="text-[#FAFAF9] text-sm font-medium">{metric.metric_name}</div>
                  <div className="text-[#6B6B70] text-xs">{metric.period_end}</div>
                </div>
                <div className="text-right">
                  <div className="text-[#32D583] text-lg font-bold">
                    {metric.value !== null ? metric.value.toFixed(2) : '-'}
                  </div>
                  <div className="text-[#6B6B70] text-xs">{metric.unit || ''}</div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-[#16161A] rounded-2xl p-8 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70] text-sm">暂无财务指标数据</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'risks' && (
        <div className="flex flex-col gap-3">
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
          {/* 机会识别 - 基于指标生成 */}
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
