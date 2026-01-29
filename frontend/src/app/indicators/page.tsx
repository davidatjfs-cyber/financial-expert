'use client';

const indicators = {
  profitability: [
    { name: '毛利率', value: '46.91%', benchmark: '行业均值 35%', trend: 'up' },
    { name: '净利率', value: '26.92%', benchmark: '行业均值 15%', trend: 'up' },
    { name: 'ROE', value: '171.42%', benchmark: '行业均值 20%', trend: 'up' },
  ],
  solvency: [
    { name: '流动比率', value: '0.89', benchmark: '健康值 > 1.5', trend: 'down' },
    { name: '速动比率', value: '0.86', benchmark: '健康值 > 1.0', trend: 'down' },
    { name: '资产负债率', value: '79.48%', benchmark: '健康值 < 60%', trend: 'down' },
  ],
  operation: [
    { name: '总资产周转率', value: '1.16', benchmark: '行业均值 0.8', trend: 'up' },
    { name: '存货周转率', value: '32.5', benchmark: '行业均值 15', trend: 'up' },
    { name: '应收账款周转率', value: '18.2', benchmark: '行业均值 10', trend: 'up' },
  ],
};

function IndicatorCard({ name, value, benchmark, trend }: { name: string; value: string; benchmark: string; trend: string }) {
  return (
    <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
      <div className="flex items-start justify-between mb-2">
        <span className="text-[#FAFAF9] text-base font-medium">{name}</span>
        <span className={`text-sm font-semibold ${trend === 'up' ? 'text-[#32D583]' : 'text-[#E85A4F]'}`}>
          {trend === 'up' ? '↑' : '↓'}
        </span>
      </div>
      <div className="text-[#FAFAF9] text-3xl font-bold mb-2">{value}</div>
      <div className="text-[#6B6B70] text-sm">{benchmark}</div>
    </div>
  );
}

export default function IndicatorsPage() {
  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">财务指标</h1>
        <p className="text-[#6B6B70] text-sm mt-1">查看关键财务指标和行业对比</p>
      </div>

      {/* Report Selector */}
      <select className="w-full bg-[#16161A] text-[#FAFAF9] rounded-xl py-4 px-5 text-base border border-[#2A2A2E] focus:border-[#32D583] focus:outline-none">
        <option>苹果公司 - 2025年年报</option>
        <option>腾讯控股 - 2025年三季报</option>
        <option>阿里巴巴 - 2025年年报</option>
      </select>

      {/* Profitability */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">💰</span>
          <h2 className="text-[#FAFAF9] text-lg font-semibold">盈利能力</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {indicators.profitability.map((item) => (
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
          {indicators.solvency.map((item) => (
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
          {indicators.operation.map((item) => (
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
            <div className="text-[#FAFAF9] text-base font-semibold">行业 1.5</div>
          </div>
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">速动比率</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 1.0</div>
          </div>
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">资产负债率</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 50%</div>
          </div>
          <div className="bg-[#1A1A1E] rounded-xl p-4 text-center">
            <div className="text-[#6B6B70] text-sm mb-1">ROE</div>
            <div className="text-[#FAFAF9] text-base font-semibold">行业 15%</div>
          </div>
        </div>
      </div>
    </div>
  );
}
