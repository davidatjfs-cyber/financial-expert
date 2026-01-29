'use client';

import { useEffect, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { getAlertsSummary, getAllAlerts, type Alert, type AlertsSummary } from '@/services/api';

export default function RiskPage() {
  const [summary, setSummary] = useState<AlertsSummary>({ high: 0, medium: 0, low: 0 });
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [summaryData, alertsData] = await Promise.all([
          getAlertsSummary(),
          getAllAlerts(undefined, 20),
        ]);
        setSummary(summaryData);
        setAlerts(alertsData);
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">风险预警</h1>
        <p className="text-[#6B6B70] text-sm mt-1">监控财务风险指标，及时发现潜在问题</p>
      </div>

      {/* Risk Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
          <div className="text-[#6B6B70] text-sm mb-2">严重风险</div>
          <div className="text-[#E85A4F] text-4xl font-bold">{loading ? '-' : summary.high}</div>
          <div className="text-[#6B6B70] text-sm mt-2">个预警</div>
        </div>
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
          <div className="text-[#6B6B70] text-sm mb-2">中等风险</div>
          <div className="text-[#FFB547] text-4xl font-bold">{loading ? '-' : summary.medium}</div>
          <div className="text-[#6B6B70] text-sm mt-2">个预警</div>
        </div>
        <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
          <div className="text-[#6B6B70] text-sm mb-2">低风险</div>
          <div className="text-[#32D583] text-4xl font-bold">{loading ? '-' : summary.low}</div>
          <div className="text-[#6B6B70] text-sm mt-2">个预警</div>
        </div>
      </div>

      {/* Alerts List */}
      <div>
        <h2 className="text-[#FAFAF9] text-lg font-semibold mb-2">风险预警列表</h2>
        <p className="text-[#6B6B70] text-sm mb-4">点击查看详细风险分析</p>
        
        <div className="flex flex-col gap-3">
          {loading ? (
            <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70] text-base">加载中...</p>
            </div>
          ) : alerts.length > 0 ? (
            alerts.map((alert) => {
              const riskColors = {
                high: { bg: 'bg-[#E85A4F]/20', text: 'text-[#E85A4F]', label: '高风险' },
                medium: { bg: 'bg-[#FFB547]/20', text: 'text-[#FFB547]', label: '中风险' },
                low: { bg: 'bg-[#32D583]/20', text: 'text-[#32D583]', label: '低风险' },
              };
              const risk = riskColors[alert.level];

              return (
                <div
                  key={alert.id}
                  className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] flex items-center gap-4 active:bg-[#1A1A1E]"
                >
                  <div className={`w-12 h-12 rounded-xl ${risk.bg} flex items-center justify-center flex-shrink-0`}>
                    <span className={`text-xl ${risk.text}`}>⚠️</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[#FAFAF9] text-base font-semibold truncate">{alert.title}</span>
                      <span className={`px-2 py-1 rounded-md text-sm font-semibold ${risk.bg} ${risk.text}`}>
                        {risk.label}
                      </span>
                    </div>
                    <div className="text-[#6B6B70] text-sm truncate">
                      {alert.message}
                    </div>
                  </div>
                  <ChevronRight size={24} className="text-[#6B6B70] flex-shrink-0" />
                </div>
              );
            })
          ) : (
            <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70] text-base">暂无风险预警</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
