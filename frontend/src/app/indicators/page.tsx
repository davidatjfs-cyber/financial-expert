'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { getReportMetrics, getReports, type Metric, type Report } from '@/services/api';

function IndicatorCard({ name, value, benchmark, trend }: { name: string; value: string; benchmark: string; trend: 'up' | 'down' | 'neutral' }) {
  return (
    <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
      <div className="flex items-start justify-between mb-2">
        <span className="text-[#FAFAF9] text-base font-medium">{name}</span>
        <span
          className={`text-sm font-semibold ${
            trend === 'up' ? 'text-[#32D583]' : trend === 'down' ? 'text-[#E85A4F]' : 'text-[#6B6B70]'
          }`}
        >
          {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
        </span>
      </div>
      <div className="text-[#FAFAF9] text-3xl font-bold mb-2">{value}</div>
      <div className="text-[#6B6B70] text-sm">{benchmark}</div>
    </div>
  );
}

export default function IndicatorsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string>('');
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loadingReports, setLoadingReports] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [message, setMessage] = useState('');
  const requestSeq = useRef(0);

  const selectedReport = useMemo(
    () => reports.find((r) => r.id === selectedReportId) || null,
    [reports, selectedReportId]
  );

  useEffect(() => {
    async function loadReports() {
      setLoadingReports(true);
      setMessage('');
      try {
        const list = await getReports(50);
        setReports(list);
        if (list.length > 0) {
          setSelectedReportId((prev) => (prev && list.some((r) => r.id === prev) ? prev : list[0].id));
        }
      } catch (e) {
        console.error(e);
        setMessage('加载报告列表失败');
      } finally {
        setLoadingReports(false);
      }
    }
    loadReports();
  }, []);

  useEffect(() => {
    async function loadMetrics(reportId: string) {
      const seq = ++requestSeq.current;
      setLoadingMetrics(true);
      setMessage('');
      try {
        const list = await getReportMetrics(reportId);
        if (seq !== requestSeq.current) return;
        setMetrics(list);
      } catch (e) {
        console.error(e);
        if (seq !== requestSeq.current) return;
        setMetrics([]);
        setMessage('加载财务指标失败');
      } finally {
        if (seq !== requestSeq.current) return;
        setLoadingMetrics(false);
      }
    }

    if (!selectedReportId) {
      setMetrics([]);
      return;
    }
    loadMetrics(selectedReportId);
  }, [selectedReportId]);

  const latestMetrics = useMemo(() => {
    if (!selectedReport?.period_end) return metrics;
    const list = metrics.filter((m) => m.period_end === selectedReport.period_end);
    return list.length > 0 ? list : metrics;
  }, [metrics, selectedReport?.period_end]);

  const getMetric = (code: string) => latestMetrics.find((m) => m.metric_code === code);

  const industryAvg = {
    grossMargin: 35.0,
    netMargin: 15.0,
    roe: 20.0,
    currentRatio: 1.5,
    quickRatio: 1.0,
    debtRatio: 60.0,
    assetTurnover: 0.8,
    inventoryTurnover: 15.0,
    receivableTurnover: 10.0,
  };

  const compare = (value: number | null | undefined, avg: number, higherIsBetter = true): 'up' | 'down' | 'neutral' => {
    if (value == null) return 'neutral';
    const good = higherIsBetter ? value >= avg : value <= avg;
    if (good) return 'up';
    return 'down';
  };

  const fmt = (value: number | null | undefined, digits = 2) => (value == null ? '-' : value.toFixed(digits));
  const pct = (value: number | null | undefined, digits = 2) => (value == null ? '-' : `${value.toFixed(digits)}%`);

  const cards = useMemo(() => {
    const grossMargin = getMetric('GROSS_MARGIN');
    const netMargin = getMetric('NET_MARGIN');
    const roe = getMetric('ROE');

    const currentRatio = getMetric('CURRENT_RATIO');
    const quickRatio = getMetric('QUICK_RATIO');
    const debtRatio = getMetric('DEBT_ASSET');

    const assetTurnover = getMetric('ASSET_TURNOVER');
    const inventoryTurnover = getMetric('INVENTORY_TURNOVER');
    const receivableTurnover = getMetric('RECEIVABLE_TURNOVER');

    return {
      profitability: [
        { name: '毛利率', value: pct(grossMargin?.value), benchmark: `行业均值 ${industryAvg.grossMargin}%`, trend: compare(grossMargin?.value, industryAvg.grossMargin, true) },
        { name: '净利率', value: pct(netMargin?.value), benchmark: `行业均值 ${industryAvg.netMargin}%`, trend: compare(netMargin?.value, industryAvg.netMargin, true) },
        { name: 'ROE', value: pct(roe?.value), benchmark: `行业均值 ${industryAvg.roe}%`, trend: compare(roe?.value, industryAvg.roe, true) },
      ],
      solvency: [
        { name: '流动比率', value: fmt(currentRatio?.value), benchmark: `健康值 > ${industryAvg.currentRatio}`, trend: compare(currentRatio?.value, industryAvg.currentRatio, true) },
        { name: '速动比率', value: fmt(quickRatio?.value), benchmark: `健康值 > ${industryAvg.quickRatio}`, trend: compare(quickRatio?.value, industryAvg.quickRatio, true) },
        { name: '资产负债率', value: pct(debtRatio?.value), benchmark: `健康值 < ${industryAvg.debtRatio}%`, trend: compare(debtRatio?.value, industryAvg.debtRatio, false) },
      ],
      operation: [
        { name: '总资产周转率', value: fmt(assetTurnover?.value), benchmark: `行业均值 ${industryAvg.assetTurnover}`, trend: compare(assetTurnover?.value, industryAvg.assetTurnover, true) },
        { name: '存货周转率', value: fmt(inventoryTurnover?.value), benchmark: `行业均值 ${industryAvg.inventoryTurnover}`, trend: compare(inventoryTurnover?.value, industryAvg.inventoryTurnover, true) },
        { name: '应收账款周转率', value: fmt(receivableTurnover?.value), benchmark: `行业均值 ${industryAvg.receivableTurnover}`, trend: compare(receivableTurnover?.value, industryAvg.receivableTurnover, true) },
      ],
    };
  }, [latestMetrics]);

  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto pb-24">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">财务指标</h1>
        <p className="text-[#6B6B70] text-sm mt-1">查看关键财务指标和行业对比</p>
      </div>

      {/* Report Selector */}
      <select
        value={selectedReportId}
        onChange={(e) => setSelectedReportId(e.target.value)}
        disabled={loadingReports || reports.length === 0}
        className="w-full bg-[#16161A] text-[#FAFAF9] rounded-xl py-4 px-5 text-base border border-[#2A2A2E] focus:border-[#32D583] focus:outline-none disabled:opacity-60"
      >
        {loadingReports ? (
          <option value="">加载中...</option>
        ) : reports.length === 0 ? (
          <option value="">暂无报告</option>
        ) : (
          reports.map((r) => (
            <option key={r.id} value={r.id}>
              {r.report_name} - {r.period_end}
            </option>
          ))
        )}
      </select>

      {(loadingMetrics || message) && (
        <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
          <div className="text-[#6B6B70] text-sm">
            {loadingMetrics ? '指标加载中...' : message}
          </div>
        </div>
      )}

      {/* Profitability */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">💰</span>
          <h2 className="text-[#FAFAF9] text-lg font-semibold">盈利能力</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {cards.profitability.map((item) => (
            <IndicatorCard key={item.name} {...item} />
          ))}
        </div>
      </div>

      {/* Solvency */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">🏦</span>
          <h2 className="text-[#FAFAF9] text-lg font-semibold">偿债能力</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {cards.solvency.map((item) => (
            <IndicatorCard key={item.name} {...item} />
          ))}
        </div>
      </div>

      {/* Operation */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">⚙️</span>
          <h2 className="text-[#FAFAF9] text-lg font-semibold">营运能力</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {cards.operation.map((item) => (
            <IndicatorCard key={item.name} {...item} />
          ))}
        </div>
      </div>

      {/* Industry Benchmark */}
      <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
        <h3 className="text-[#FAFAF9] text-lg font-semibold mb-2">📊 行业基准参考</h3>
        <p className="text-[#6B6B70] text-sm mb-4">与同行业公司的关键指标对比</p>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">流动比率</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 {industryAvg.currentRatio}</div>
          </div>
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">速动比率</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 {industryAvg.quickRatio}</div>
          </div>
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">资产负债率</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 {industryAvg.debtRatio}%</div>
          </div>
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">ROE</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 {industryAvg.roe}%</div>
          </div>
        </div>
      </div>
    </div>
  );
}
