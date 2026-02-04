'use client';

import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Search, Download, X } from 'lucide-react';
import { searchStocks, getStockPrice, getStockIndicators, fetchMarketReport, type StockSearchResult, type StockPrice, type StockIndicators } from '@/services/api';

function StockPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
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

  const fmtCompact = (v: number | null | undefined, digits = 2) => {
    if (v == null) return '-';
    const abs = Math.abs(v);
    if (abs >= 1e12) return (v / 1e12).toFixed(digits) + 'T';
    if (abs >= 1e9) return (v / 1e9).toFixed(digits) + 'B';
    if (abs >= 1e6) return (v / 1e6).toFixed(digits) + 'M';
    if (abs >= 1e3) return (v / 1e3).toFixed(digits) + 'K';
    return v.toFixed(0);
  };

  const fmtBigByMarket = (v: number | null | undefined, market?: string) => {
    return currencyPrefix(market) + fmtYi(v);
  };

  const fmtVolumeByMarket = (v: number | null | undefined, market?: string) => {
    if (v == null) return '-';
    if (market === 'US') return fmtCompact(v, 2) + '股';
    return fmtBig(v) + '股';
  };

  const fmtNA = (v: number | null | undefined, digits = 2) => (v == null ? 'N/A' : v.toFixed(digits));

  const currencyPrefix = (market?: string) => {
    if (market === 'US') return '$';
    if (market === 'HK') return 'HK$';
    return '¥';
  };

  const fmtSigned = (v: number | null | undefined, digits = 2) => {
    if (v == null) return '-';
    const s = v.toFixed(digits);
    return v > 0 ? `+${s}` : s;
  };

  const trendLabel = (trend?: string | null) => {
    const t = (trend || '').trim();
    if (!t) return '-';
    return t;
  };

  const trendColorClass = (trend?: string | null) => {
    const t = (trend || '').trim();
    if (t === '上涨') return 'text-[#E85A4F]';
    if (t === '下跌') return 'text-[#32D583]';
    return 'text-[#FAFAF9]';
  };

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

  useEffect(() => {
    const symbol = searchParams.get('symbol');
    const market = searchParams.get('market');
    const name = searchParams.get('name');
    if (symbol && market) {
      setSelectedStock({ symbol, market, name: name || symbol });
    }
  }, [searchParams]);

  useEffect(() => {
    if (!selectedStock) return;
    try {
      const item = { symbol: selectedStock.symbol, market: selectedStock.market, name: selectedStock.name };
      const raw = localStorage.getItem('recent_stocks');
      const prev = raw ? (JSON.parse(raw) as any[]) : [];
      const next = [item, ...(Array.isArray(prev) ? prev : [])]
        .filter((v, idx, arr) => v && arr.findIndex((x) => x.symbol === v.symbol && x.market === v.market) === idx)
        .slice(0, 10);
      localStorage.setItem('recent_stocks', JSON.stringify(next));
    } catch {
      // ignore
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
      const resp = await fetchMarketReport(
        selectedStock.symbol,
        selectedStock.market,
        'annual',
        '2024-12-31',
        selectedStock.name
      );
      setMessage(resp.message || '已开始获取财报数据');
      if (resp?.report_id) {
        router.push(`/reports/${resp.report_id}`);
      }
    } catch (error) {
      setMessage('获取失败，请重试');
    } finally {
      setFetching(false);
    }
  };

  return (
    <div className="p-4 md:p-10 flex flex-col gap-6 md:gap-7 max-w-3xl mx-auto pb-24 md:pb-10">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-2xl md:text-3xl font-semibold">股票查询</h1>
        <p className="text-[#6B6B70] text-base mt-2">搜索股票代码或公司名称，获取财务数据</p>
      </div>

      {/* Search Card */}
      <div className="hidden md:block">
        <div className="max-w-3xl mx-auto bg-[#16161A] rounded-3xl p-4 md:p-7 border border-[#2A2A2E]">
          <div className="relative mb-4 md:mb-6">
            <Search className="absolute left-4 md:left-6 top-1/2 -translate-y-1/2 text-[#6B6B70]" size={22} />
            <input
              type="text"
              placeholder="输入股票代码，如 600519"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full bg-[#1A1A1E] text-[#FAFAF9] rounded-2xl md:rounded-3xl py-4 md:py-7 pl-12 md:pl-16 pr-4 md:pr-6 text-base md:text-3xl border-2 border-[#2A2A2E] focus:border-[#32D583] focus:outline-none placeholder:text-[#6B6B70]"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="w-full bg-[#32D583] text-white rounded-2xl py-4 md:py-6 px-5 md:px-6 font-semibold text-base md:text-2xl flex items-center justify-center gap-2 md:gap-3 disabled:opacity-50 active:bg-[#28b870]"
          >
            <Search size={32} />
            {searching ? '搜索中...' : '搜索股票'}
          </button>
        </div>
      </div>

      <div className="md:hidden fixed left-0 right-0 bottom-16 z-50 px-4 pb-[calc(env(safe-area-inset-bottom,0px)+12px)]">
        <div className="bg-[#16161A] rounded-3xl p-4 border border-[#2A2A2E] shadow-lg shadow-black/40">
          <div className="relative mb-3">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[#6B6B70]" size={22} />
            <input
              type="text"
              placeholder="输入股票代码，如 600519"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full bg-[#0B0B0E] text-[#FAFAF9] rounded-2xl py-4 pl-12 pr-4 text-2xl border-2 border-[#2A2A2E] focus:border-[#32D583] focus:outline-none placeholder:text-[#6B6B70]"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="w-full bg-[#32D583] text-white rounded-2xl py-4 font-bold text-xl flex items-center justify-center gap-2 disabled:opacity-50 active:bg-[#28b870]"
          >
            <Search size={22} />
            {searching ? '搜索中...' : '搜索股票'}
          </button>
        </div>
      </div>

      <div className="md:hidden h-[200px]" />

      {/* Selected Stock Detail - 更突出的卡片样式 */}
      {selectedStock && (
        <div className="bg-gradient-to-br from-[#1a2a1a] to-[#16161A] rounded-3xl p-6 border-2 border-[#32D583] shadow-lg shadow-[#32D583]/20">
          {/* 股票名称和代码 */}
          <div className="text-center mb-4">
            <div className="text-[#32D583] text-2xl font-bold mb-1">{selectedStock.name}</div>
            <div className="text-[#FAFAF9] text-lg md:text-xl">{selectedStock.symbol}</div>
            <div className="text-[#6B6B70] text-base mt-2">{selectedStock.market} 市场</div>
          </div>

          {/* Real-time price */}
          <div className="bg-[#0B0B0E]/70 rounded-2xl p-4 border border-[#2A2A2E] mb-4">
            <div className="flex items-center justify-between">
              <div className="text-[#6B6B70] text-sm">实时价格</div>
              <div className="text-[#6B6B70] text-sm">{loadingPrice ? '更新中...' : '已更新'}</div>
            </div>
            <div className="mt-2 flex items-end justify-between gap-4">
              <div className="min-w-0">
                <div className="text-[#FAFAF9] text-3xl md:text-4xl font-bold truncate">
                  {currencyPrefix(selectedStock.market)}{fmt(stockPrice?.price)}
                </div>
                <div className={`mt-2 text-base md:text-lg font-semibold ${
                  (stockPrice?.change ?? 0) > 0
                    ? 'text-[#32D583]'
                    : (stockPrice?.change ?? 0) < 0
                      ? 'text-[#E85A4F]'
                      : 'text-[#FAFAF9]'
                }`}>
                  {fmtSigned(stockPrice?.change)} ({fmtSigned(stockPrice?.change_pct)}%)
                </div>
              </div>
              <button
                onClick={refreshQuote}
                className="bg-[#16161A] text-[#FAFAF9] rounded-xl px-4 py-3 text-base border border-[#2A2A2E] active:bg-[#1A1A1E]"
              >
                刷新
              </button>
            </div>
          </div>

          <button
            onClick={() => setShowDetail(true)}
            className="w-full bg-[#0B0B0E] text-[#FAFAF9] rounded-2xl py-5 px-6 font-bold text-lg border border-[#2A2A2E] mb-4"
          >
            查看关键指标
          </button>

          {/* Action Button */}
          <button 
            onClick={handleFetchReport}
            disabled={fetching}
            className="w-full bg-[#6366F1] text-white rounded-2xl py-5 px-6 font-bold text-xl flex items-center justify-center gap-2 disabled:opacity-50 active:bg-[#5558DD]"
          >
            <Download size={24} />
            {fetching ? '获取中...' : '获取财报数据'}
          </button>
        </div>
      )}

      {selectedStock && showDetail && (
        <div className="fixed inset-0 z-[100] bg-black/60 flex items-center justify-center p-4">
          <div className="w-full md:max-w-xl bg-[#0B0B0E] rounded-3xl border border-[#2A2A2E] p-6 max-h-[calc(100dvh-32px)] overflow-y-auto overscroll-contain pb-[calc(env(safe-area-inset-bottom,0px)+160px)]">
            <div className="flex items-center justify-between mb-4">
              <div className="min-w-0">
                <div className="text-[#FAFAF9] text-xl font-semibold truncate">{selectedStock.name}</div>
                <div className="text-[#6B6B70] text-base">{selectedStock.symbol} · {selectedStock.market} 市场</div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={refreshQuote}
                  className="h-11 rounded-xl bg-[#16161A] border border-[#2A2A2E] px-4 text-base text-[#FAFAF9]"
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
              <div className="flex items-center justify-between">
                <div className="text-[#6B6B70] text-sm">实时价格</div>
                <div className="text-[#6B6B70] text-sm">{loadingPrice ? '更新中...' : '已更新'}</div>
              </div>
              <div className="mt-2 flex items-end justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-[#FAFAF9] text-3xl font-bold truncate">
                    {currencyPrefix(selectedStock.market)}{fmt(stockPrice?.price)}
                  </div>
                  <div className={`mt-2 text-base font-semibold ${
                    (stockPrice?.change ?? 0) > 0
                      ? 'text-[#32D583]'
                      : (stockPrice?.change ?? 0) < 0
                        ? 'text-[#E85A4F]'
                        : 'text-[#FAFAF9]'
                  }`}>
                    {fmtSigned(stockPrice?.change)} ({fmtSigned(stockPrice?.change_pct)}%)
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E] mb-3">
              <div className="text-[#6B6B70] text-sm mb-3">关键指标</div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">市值</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{fmtBigByMarket(stockIndicators?.market_cap ?? stockPrice?.market_cap, selectedStock.market)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">成交金额</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{fmtBigByMarket(stockIndicators?.amount ?? stockPrice?.amount, selectedStock.market)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">52周最高</div>
                  <div className="text-[#E85A4F] text-lg font-bold mt-1">{fmt(stockIndicators?.high_52w)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">52周最低</div>
                  <div className="text-[#32D583] text-lg font-bold mt-1">{fmt(stockIndicators?.low_52w)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">趋势</div>
                  <div className={`${trendColorClass(stockIndicators?.trend)} text-lg font-bold mt-1`}>{trendLabel(stockIndicators?.trend)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">Slope 率</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{stockIndicators?.slope_pct == null ? '-' : `${fmt(stockIndicators?.slope_pct, 3)}%/天`}</div>
                  <div className="text-[#6B6B70] text-xs mt-1">{stockIndicators?.slope_advice || '-'}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">MA5</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{currencyPrefix(selectedStock.market)}{fmt(stockIndicators?.ma5)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">MA20</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{currencyPrefix(selectedStock.market)}{fmt(stockIndicators?.ma20)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">MA60</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{currencyPrefix(selectedStock.market)}{fmt(stockIndicators?.ma60)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">RSI(14)</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{fmt(stockIndicators?.rsi14)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">市盈率</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{fmt(stockIndicators?.pe_ratio, 2)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">ATR(14)</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">{fmt(stockIndicators?.atr14, 3)}</div>
                </div>
                <div className="bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">卖出价</div>
                  <div className="text-[#FAFAF9] text-lg font-bold mt-1">
                    {(stockIndicators?.sell_price_ok === true && stockIndicators?.sell_price != null)
                      ? (currencyPrefix(selectedStock.market) + fmtNA(stockIndicators?.sell_price))
                      : 'N/A'}
                  </div>
                  <div className="text-[#6B6B70] text-xs mt-1">
                    {(stockIndicators?.sell_price_ok === true) ? '确认' : (stockIndicators?.sell_price_ok === false ? '等待' : '-')}
                  </div>
                  <div className="text-[#6B6B70] text-xs mt-1">
                    {stockIndicators?.sell_reason || '-'}
                  </div>
                </div>
                <div className="col-span-2 bg-[#0B0B0E] rounded-xl p-3">
                  <div className="text-[#6B6B70] text-sm">买入价位（满足：买入{'>'}MA60、MA60趋势向上、买入≈MA20、RSI Rebound）</div>
                  <div className="mt-2">
                    <div className="text-[#FAFAF9] text-lg font-bold">
                      {(stockIndicators?.buy_price_aggressive_ok === true && stockIndicators?.buy_price_aggressive != null)
                        ? (currencyPrefix(selectedStock.market) + fmtNA(stockIndicators?.buy_price_aggressive))
                        : 'N/A'}
                    </div>
                    <div className="text-[#6B6B70] text-xs mt-1">
                      {(stockIndicators?.buy_price_aggressive_ok === true) ? '确认' : (stockIndicators?.buy_price_aggressive_ok === false ? '等待' : '-')}
                    </div>
                    <div className="text-[#6B6B70] text-xs mt-1">
                      {stockIndicators?.buy_reason || '-'}
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
              className="w-full bg-[#6366F1] text-white rounded-2xl py-5 px-6 font-bold text-lg disabled:opacity-50"
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
        <h2 className="text-[#FAFAF9] text-xl font-semibold mb-4">热门股票</h2>
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
              className="bg-[#16161A] rounded-2xl p-6 border border-[#2A2A2E] flex items-center justify-between active:bg-[#1A1A1E] cursor-pointer"
            >
              <div>
                <span className="text-[#FAFAF9] text-lg">{stock.name}</span>
                <span className="text-[#6B6B70] text-base ml-2">{stock.symbol}</span>
              </div>
              <span className="text-[#6B6B70] text-base">{stock.market}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function StockPage() {
  return (
    <Suspense
      fallback={
        <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
          <div className="bg-[#16161A] rounded-2xl p-10 border border-[#2A2A2E] text-center">
            <p className="text-[#6B6B70] text-base">加载中...</p>
          </div>
        </div>
      }
    >
      <StockPageInner />
    </Suspense>
  );
}
