'use client';

import { ChevronRight } from 'lucide-react';

const timelineItems = [
  { id: 1, day: '17', title: '苹果', source: 'market_fetch', date: '2025-12-31 00:00:00' },
  { id: 2, day: '28', title: '腾讯控股', source: 'pdf_upload', date: '2025-12-28 14:30:00' },
  { id: 3, day: '27', title: '阿里巴巴', source: 'market_fetch', date: '2025-12-27 09:15:00' },
  { id: 4, day: '25', title: '美团', source: 'pdf_upload', date: '2025-12-25 16:45:00' },
];

export default function TrendsPage() {
  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">趋势分析</h1>
        <p className="text-[#6B6B70] text-sm mt-1">追踪财务指标的变化趋势，洞察企业发展方向</p>
      </div>

      {/* Charts Grid */}
      <div className="flex gap-4">
        {/* Profitability Chart */}
        <div className="flex-1 bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
          <h3 className="text-[#FAFAF9] text-base font-semibold mb-1">盈利能力趋势</h3>
          <p className="text-[#6B6B70] text-sm mb-4">毛利率与净利率变化</p>
          <div className="h-24 flex items-end justify-around gap-1 mb-4">
            {[40, 65, 45, 80, 55].map((h, i) => (
              <div key={i} className="flex gap-1">
                <div className="w-4 rounded-t bg-[#6366F1]" style={{ height: `${h * 0.8}%` }} />
                <div className="w-4 rounded-t bg-[#32D583]" style={{ height: `${h}%` }} />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#6366F1]" />
              <span className="text-[#6B6B70]">毛利率</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#32D583]" />
              <span className="text-[#6B6B70]">净利率</span>
            </div>
          </div>
        </div>

        {/* Solvency Chart */}
        <div className="flex-1 bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
          <h3 className="text-[#FAFAF9] text-base font-semibold mb-1">偿债能力趋势</h3>
          <p className="text-[#6B6B70] text-sm mb-4">流动比率变化</p>
          <div className="h-24 flex items-end justify-around gap-1 mb-4">
            {[60, 45, 70, 50, 65].map((h, i) => (
              <div key={i} className="flex gap-1">
                <div className="w-4 rounded-t bg-[#6366F1]" style={{ height: `${h * 0.9}%` }} />
                <div className="w-4 rounded-t bg-[#E85A4F]" style={{ height: `${h}%` }} />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#6366F1]" />
              <span className="text-[#6B6B70]">流动比率</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#E85A4F]" />
              <span className="text-[#6B6B70]">负债率</span>
            </div>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div>
        <h2 className="text-[#FAFAF9] text-lg font-semibold mb-2">报表时间线</h2>
        <p className="text-[#6B6B70] text-sm mb-4">已分析的财务报表按时间排列</p>
        
        <div className="flex flex-col gap-3">
          {timelineItems.map((item) => (
            <div
              key={item.id}
              className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] flex items-center gap-4 active:bg-[#1A1A1E]"
            >
              <div className="w-12 h-12 rounded-xl bg-[#1A3A5C] flex items-center justify-center flex-shrink-0">
                <span className="text-[#60A5FA] text-base font-bold">{item.day}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[#FAFAF9] text-base font-semibold truncate">{item.title}</div>
                <div className="text-[#6B6B70] text-sm">{item.source} · {item.date}</div>
              </div>
              <ChevronRight size={24} className="text-[#6B6B70] flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
