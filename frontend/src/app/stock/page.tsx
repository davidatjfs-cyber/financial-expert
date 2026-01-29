'use client';

import { useState, useEffect } from 'react';
import { Search, Download, X } from 'lucide-react';
import { searchStocks, getStockPrice, getStockIndicators, fetchMarketReport, type StockSearchResult, type StockPrice, type StockIndicators } from '@/services/api';

export default function StockPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<StockSearchResult[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [stockPrice, setStockPrice] = useState<StockPrice | null>(null);
  const [stockIndicators, setStockIndicators] = useState<StockIndicators | null>(null);
  const [searching, setSearching] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [loadingPrice, setLoadingPrice] = useState(false);
  const [message, setMessage] = useState('');
  const [showDetail, setShowDetail] = useState(false);

  const fmt = (v: number | null | undefined, digits = 2) => (v == null ? '-' : v.toFixed(digits));

  const fmtBig = (v: number | null | undefined) => (v == null ? '-' : v.toLocaleString());

  const fmtMoney = (v: number | null | undefined) => {
    if (v == null) return '-';
    const abs = Math.abs(v);
    if (abs >= 1e8) return (v / 1e8).toFixed(2) + '亿';
    if (abs >= 1e4) return (v / 1e4).toFixed(2) + '万';
    return v.toFixed(0);
  };

  const fmtYi = (v: number | null | undefined) => (v == null ? '-' : (v / 1e8).toFixed(2) + '亿');

  const fmtNA = (v: number | null | undefined, digits = 2) => (v == null ? 'N/A' : v.toFixed(digits));

  // Fetch price when stock is selected
  useEffect(() => {
    if (selectedStock) {
      setLoadingPrice(true);
      getStockPrice(selectedStock.symbol, selectedStock.market)
        .then(price => setStockPrice(price))
        .catch(() => setStockPrice(null))
        .finally(() => setLoadingPrice(false));

      getStockIndicators(selectedStock.symbol, selectedStock.market)
        .then((v) => setStockIndicators(v))
        .catch(() => setStockIndicators(null));
    } else {
      setStockPrice(null);
      setStockIndicators(null);
    }
  }, [selectedStock]);

  const refreshQuote = async () => {
    if (!selectedStock) return;
    setLoadingPrice(true);
    try {
      const price = await getStockPrice(selectedStock.symbol, selectedStock.market);
      setStockPrice(price);
      const ind = await getStockIndicators(selectedStock.symbol, selectedStock.market);
      setStockIndicators(ind);
    } catch {
      setStockPrice(null);
      setStockIndicators(null);
    } finally {
      setLoadingPrice(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setMessage('');
    setSearchResults([]);
    try {
      console.log('Searching for:', searchQuery);
      const results = await searchStocks(searchQuery.trim());
      console.log('Search results:', results);
      setSearchResults(results);
      if (results.length === 0) {
        setMessage('未找到匹配的股票');
      } else {
        // Auto-select first result
        setSelectedStock(results[0]);
      }
    } catch (error) {
      console.error('Search error:', error);
      setMessage('搜索失败，请检查网络连接');
    } finally {
      setSearching(false);
    }
  };

  const handleFetchReport = async () => {
    if (!selectedStock) return;
    setFetching(true);
    setMessage('');
    try {
      await fetchMarketReport(selectedStock.symbol, selectedStock.market);
      setMessage('已开始获取财报数据，请在报告列表中查看');
    } catch (error) {
      setMessage('获取失败，请重试');
    } finally {
      setFetching(false);
    }
  };

  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto pb-56 md:pb-8">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">股票查询</h1>
        <p className="text-[#6B6B70] text-sm mt-1">搜索股票代码或公司名称，获取财务数据</p>
      </div>

      {/* Search Card */}
      <div className="fixed left-0 right-0 bottom-24 z-40 px-5 md:static md:px-0">
        <div className="max-w-2xl mx-auto bg-[#16161A] rounded-2xl p-6 border border-[#2A2A2E]">
          <div className="relative mb-6">
            <Search className="absolute left-6 top-1/2 -translate-y-1/2 text-[#6B6B70]" size={32} />
            <input
              type="text"
              placeholder="输入股票代码，如 600519"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full bg-[#1A1A1E] text-[#FAFAF9] rounded-2xl py-7 pl-16 pr-6 text-2xl border-2 border-[#2A2A2E] focus:border-[#32D583] focus:outline-none placeholder:text-[#6B6B70]"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="w-full bg-[#32D583] text-white rounded-2xl py-6 px-6 font-semibold text-2xl flex items-center justify-center gap-3 disabled:opacity-50 active:bg-[#28b870]"
          >
            <Search size={32} />
            {searching ? '搜索中...' : '搜索股票'}
          </button>
        </div>
      </div>

      {/* Selected Stock Detail - 更突出的卡片样式 */}
      {selectedStock && (
        <div className="bg-gradient-to-br from-[#1a2a1a] to-[#16161A] rounded-2xl p-5 border-2 border-[#32D583] shadow-lg shadow-[#32D583]/20">
          {/* 股票名称和代码 */}
          <div className="text-center mb-4">
            <div className="text-[#32D583] text-2xl font-bold mb-1">{selectedStock.name}</div>
            <div className="text-[#FAFAF9] text-lg">{selectedStock.symbol}</div>
            <div className="text-[#6B6B70] text-sm mt-1">{selectedStock.market} 市场</div>
          </div>

          <div className="flex justify-center mb-3">
            <button
              onClick={refreshQuote}
              className="bg-[#16161A] text-[#FAFAF9] rounded-xl px-4 py-2 text-sm border border-[#2A2A2E]"
            >
              刷新行情
            </button>
          </div>

          <button
            onClick={() => setShowDetail(true)}
            className="w-full bg-[#0B0B0E] text-[#FAFAF9] rounded-2xl py-4 px-6 font-bold text-base border border-[#2A2A2E] mb-3"
          >
            查看关键指标
          </button>

          {/* Action Button */}
          <button 
            onClick={handleFetchReport}
            disabled={fetching}
            className="w-full bg-[#6366F1] text-white rounded-2xl py-4 px-6 font-bold text-lg flex items-center justify-center gap-2 disabled:opacity-50 active:bg-[#5558DD]"
          >
            <Download size={24} />
            {fetching ? '获取中...' : '获取财报数据'}
          </button>
        </div>
      )}

      {selectedStock && showDetail && (
        <div className="fixed inset-0 z-[100] bg-black/60 flex items-center justify-center p-4">
          <div className="w-full md:max-w-lg bg-[#0B0B0E] rounded-3xl border border-[#2A2A2E] p-5 max-h-[calc(100dvh-32px)] overflow-y-auto overscroll-contain pb-[calc(env(safe-area-inset-bottom,0px)+160px)]">
            <div className="flex items-center justify-between mb-4">
              <div className="min-w-0">
                <div className="text-[#FAFAF9] text-lg font-semibold truncate">{selectedStock.name}</div>
                <div className="text-[#6B6B70] text-sm">{selectedStock.symbol} · {selectedStock.market} 市场</div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={refreshQuote}
                  className="h-10 rounded-xl bg-[#16161A] border border-[#2A2A2E] px-3 text-sm text-[#FAFAF9]"
                >
                  刷新
                </button>
                <button
                  onClick={() => setShowDetail(false)}
                  className="w-10 h-10 rounded-xl bg-[#16161A] border border-[#2A2A2E] flex items-center justify-center"
                >
                  <X size={18} className="text-[#FAFAF9]" />
                </button>
              </div>
            </div>

            <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E] mb-3">
              <div className="text-[#6B6B70] text-xs mb-2">关键指标</div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">市值</div>
                  <div className="text-[#FAFAF9] text-base font-bold mt-1">{fmtYi(stockIndicators?.market_cap ?? stockPrice?.market_cap)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">成交金额</div>
                  <div className="text-[#FAFAF9] text-base font-bold mt-1">{fmtYi(stockIndicators?.amount ?? stockPrice?.amount)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">52周最高</div>
                  <div className="text-[#E85A4F] text-base font-bold mt-1">{fmt(stockIndicators?.high_52w)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">52周最低</div>
                  <div className="text-[#32D583] text-base font-bold mt-1">{fmt(stockIndicators?.low_52w)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">MA5</div>
                  <div className="text-[#FAFAF9] text-base font-bold mt-1">{selectedStock.market === 'US' ? '$' : selectedStock.market === 'HK' ? 'HK$' : '¥'}{fmt(stockIndicators?.ma5)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">MA20</div>
                  <div className="text-[#FAFAF9] text-base font-bold mt-1">{selectedStock.market === 'US' ? '$' : selectedStock.market === 'HK' ? 'HK$' : '¥'}{fmt(stockIndicators?.ma20)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">RSI(14)</div>
                  <div className="text-[#FAFAF9] text-base font-bold mt-1">{fmt(stockIndicators?.rsi14)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">卖出价</div>
                  <div className="text-[#FAFAF9] text-base font-bold mt-1">
                    {stockIndicators?.sell_price == null
                      ? 'N/A'
                      : (selectedStock.market === 'US' ? '$' : selectedStock.market === 'HK' ? 'HK$' : '¥') + fmtNA(stockIndicators?.sell_price)}
                  </div>
                </div>
                <div className="col-span-2 bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-xs">买入价（激进/MA20 · 稳健/金叉）</div>
                  <div className="grid grid-cols-2 gap-3 mt-2">
                    <div>
                      <div className="text-[#6B6B70] text-[11px]">激进</div>
                      <div className="text-[#FAFAF9] text-base font-bold">
                        {stockIndicators?.buy_price_aggressive == null
                          ? 'N/A'
                          : (selectedStock.market === 'US' ? '$' : selectedStock.market === 'HK' ? 'HK$' : '¥') + fmtNA(stockIndicators?.buy_price_aggressive)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[#6B6B70] text-[11px]">稳健</div>
                      <div className="text-[#FAFAF9] text-base font-bold">
                        {stockIndicators?.buy_price_stable == null
                          ? 'N/A'
                          : (selectedStock.market === 'US' ? '$' : selectedStock.market === 'HK' ? 'HK$' : '¥') + fmtNA(stockIndicators?.buy_price_stable)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                setShowDetail(false);
                handleFetchReport();
              }}
              disabled={fetching}
              className="w-full bg-[#6366F1] text-white rounded-2xl py-4 px-6 font-bold text-base disabled:opacity-50"
            >
              {fetching ? '获取中...' : '获取财报数据'}
            </button>
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div className={`rounded-xl p-4 text-center ${
          message.includes('失败') ? 'bg-[#E85A4F]/20 text-[#E85A4F]' : 'bg-[#32D583]/20 text-[#32D583]'
        }`}>
          {message}
        </div>
      )}

      {/* Quick Search Suggestions */}
      <div>
        <h2 className="text-[#FAFAF9] text-lg font-semibold mb-4">热门股票</h2>
        <div className="flex flex-col gap-3">
          {[
            { name: '腾讯控股', symbol: '00700.HK', market: 'HK' },
            { name: '阿里巴巴', symbol: 'BABA', market: 'US' },
            { name: '贵州茅台', symbol: '600519.SH', market: 'CN' },
            { name: '苹果公司', symbol: 'AAPL', market: 'US' },
          ].map((stock) => (
            <div
              key={stock.symbol}
              onClick={() => {
                setSelectedStock(stock);
                setSearchResults([]);
              }}
              className="bg-[#16161A] rounded-xl p-5 border border-[#2A2A2E] flex items-center justify-between active:bg-[#1A1A1E] cursor-pointer"
            >
              <div>
                <span className="text-[#FAFAF9] text-base">{stock.name}</span>
                <span className="text-[#6B6B70] text-sm ml-2">{stock.symbol}</span>
              </div>
              <span className="text-[#6B6B70] text-sm">{stock.market}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
