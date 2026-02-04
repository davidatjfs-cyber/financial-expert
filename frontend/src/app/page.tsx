'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import ReportItem from '@/components/ReportItem';
import {
  createPortfolioPosition,
  createPortfolioTrade,
  deletePortfolioPosition,
  getPortfolioAlerts,
  getPortfolioPositions,
  getReports,
  updatePortfolioPosition,
  type PortfolioAlert,
  type PortfolioPosition,
  type Report,
} from '@/services/api';

type RecentStock = { symbol: string; market: string; name: string };

export default function Dashboard() {
  const router = useRouter();
  const [reports, setReports] = useState<Report[]>([]);
  const [recentStocks, setRecentStocks] = useState<RecentStock[]>([]);
  const [loading, setLoading] = useState(true);

  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [alerts, setAlerts] = useState<PortfolioAlert[]>([]);
  const [notifyEnabled, setNotifyEnabled] = useState(false);
  const [notifText, setNotifText] = useState<string | null>(null);

  const [showPortfolio, setShowPortfolio] = useState(false);

  const [newSymbol, setNewSymbol] = useState('');
  const [newMarket, setNewMarket] = useState<'CN' | 'HK' | 'US'>('CN');
  const [newName, setNewName] = useState('');

  const formatDateTime = (tsSeconds: number) => {
    const d = new Date(tsSeconds * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  useEffect(() => {
    async function fetchData() {
      try {
        const reportsData = await getReports(10);
        setReports(reportsData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  useEffect(() => {
    async function loadPositions() {
      try {
        const data = await getPortfolioPositions();
        setPositions(data);
      } catch (e) {
        console.error('Failed to load portfolio positions:', e);
      }
    }
    loadPositions();
  }, []);

  useEffect(() => {
    let timer: any;
    async function poll() {
      try {
        const [ps, al] = await Promise.all([getPortfolioPositions(), getPortfolioAlerts()]);
        setPositions(ps);
        setAlerts(al);

        if (al.length > 0) {
          const top = al[0];
          const msg = `${top.name || top.symbol}：${top.message}`;
          setNotifText(msg);
          if (notifyEnabled && typeof window !== 'undefined' && 'Notification' in window) {
            if (Notification.permission === 'granted') {
              try {
                new Notification('我的股票提醒', { body: msg });
              } catch {
                // ignore
              }
            }
          }
        }
      } catch (e) {
        // ignore polling errors
      }
    }
    poll();
    timer = setInterval(poll, 15_000);
    return () => clearInterval(timer);
  }, [notifyEnabled]);

  const requestBrowserNotify = async () => {
    if (typeof window === 'undefined') return;
    if (typeof window !== 'undefined' && window.location && window.location.protocol !== 'https:') {
      setNotifText('系统通知通常需要 HTTPS 才能在手机浏览器正常工作（建议用 HTTPS 或在浏览器中打开）');
    }
    if (!('Notification' in window)) {
      setNotifText('当前浏览器不支持系统通知（可继续使用站内提醒）');
      return;
    }
    try {
      const p = await Notification.requestPermission();
      setNotifyEnabled(p === 'granted');
      if (p !== 'granted') {
        setNotifText('通知权限未开启：请在浏览器设置中允许通知（也可继续使用站内提醒）');
      } else {
        setNotifText('已开启通知（若手机未弹出，请确认浏览器支持且已授予权限）');
      }
    } catch {
      setNotifyEnabled(false);
      setNotifText('开启通知失败：当前环境可能不支持系统通知（可继续使用站内提醒）');
    }
  };

  const normalizeInputSymbol = (market: 'CN' | 'HK' | 'US', raw: string) => {
    const s = raw.trim().toUpperCase();
    if (!s) return '';
    if (market === 'HK') {
      const base = s.replace(/\.HK$/i, '');
      if (/^\d{1,5}$/.test(base)) return base.padStart(5, '0') + '.HK';
      return s;
    }
    if (market === 'CN') {
      const base = s.replace(/\.(SH|SZ|BJ)$/i, '');
      if (/^\d{6}$/.test(base)) return base;
      return s;
    }
    return s;
  };

  const handleAddPosition = async () => {
    const symbol = normalizeInputSymbol(newMarket, newSymbol);
    if (!symbol) return;
    try {
      await createPortfolioPosition({
        market: newMarket,
        symbol,
        name: newName.trim() || undefined,
      });
      setNewSymbol('');
      setNewName('');
      const ps = await getPortfolioPositions();
      setPositions(ps);
      setNotifText(`已添加：${symbol}`);
    } catch (e) {
      console.error('create position failed', e);
      setNotifText('添加失败：请检查代码/市场是否正确，或稍后重试');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deletePortfolioPosition(id);
      const ps = await getPortfolioPositions();
      setPositions(ps);
    } catch (e) {
      console.error('delete position failed', e);
    }
  };

  const handleTrade = async (positionId: string, side: 'BUY' | 'SELL', qty: number) => {
    if (!qty || qty <= 0) return;
    try {
      await createPortfolioTrade({ position_id: positionId, side, quantity: qty });
      const ps = await getPortfolioPositions();
      setPositions(ps);
    } catch (e) {
      console.error('trade failed', e);
    }
  };

  const handleUpdateTargets = async (p: PortfolioPosition, buy?: number | null, sell?: number | null) => {
    try {
      await updatePortfolioPosition(p.id, {
        target_buy_price: buy == null ? null : buy,
        target_sell_price: sell == null ? null : sell,
      });
      const ps = await getPortfolioPositions();
      setPositions(ps);
    } catch (e) {
      console.error('update targets failed', e);
    }
  };

  useEffect(() => {
    try {
      const raw = localStorage.getItem('recent_stocks');
      const parsed = raw ? (JSON.parse(raw) as RecentStock[]) : [];
      if (Array.isArray(parsed)) setRecentStocks(parsed);
    } catch {
      setRecentStocks([]);
    }
  }, []);

  return (
    <div className="px-4 py-4 md:px-10 md:py-8 flex flex-col gap-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">财务分析专家</h1>
          <p className="text-[#6B6B70] text-sm mt-1">智能财务决策助手</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full bg-[#16161A] border border-[#2A2A2E] flex items-center justify-center">
            <span className="text-lg">🔔</span>
          </div>
          <div className="w-11 h-11 rounded-full bg-[#16161A] border border-[#2A2A2E] flex items-center justify-center">
            <span className="text-lg">👤</span>
          </div>
        </div>
      </div>

      {/* My Portfolio */}
      <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[#FAFAF9] text-lg font-semibold">我的股票</h3>
            <p className="text-[#6B6B70] text-sm mt-1">模拟账户：记录买卖并计算盈亏，自动提醒买入/卖出信号</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={requestBrowserNotify}
              className="h-11 px-4 rounded-xl bg-[#0B0B0E] border border-[#2A2A2E] text-[#FAFAF9] text-sm font-semibold"
            >
              {notifyEnabled ? '已开启通知' : '开启通知'}
            </button>
            <button
              onClick={() => setShowPortfolio(true)}
              className="h-11 px-4 rounded-xl bg-[#6366F1] text-white text-sm font-semibold"
            >
              管理
            </button>
          </div>
        </div>

        {notifText && (
          <div className="mt-3 bg-[#FFB547]/10 border border-[#FFB547]/30 rounded-xl p-3 flex items-center justify-between gap-3">
            <div className="text-[#FAFAF9] text-sm font-semibold truncate">{notifText}</div>
            <button
              onClick={() => setNotifText(null)}
              className="text-[#FFB547] text-sm font-semibold"
            >
              关闭
            </button>
          </div>
        )}

        {alerts.length > 0 && (
          <div className="mt-3 text-[#6B6B70] text-xs">
            当前提醒：{alerts.length} 条（每 15 秒刷新）
          </div>
        )}

        <div className="mt-4 bg-[#0B0B0E] rounded-2xl p-4 border border-[#2A2A2E]">
          <div className="flex items-center justify-between">
            <div className="text-[#FAFAF9] text-base font-semibold">持仓 {positions.length} 只</div>
            <button
              onClick={() => setShowPortfolio(true)}
              className="h-11 px-4 rounded-xl bg-[#16161A] border border-[#2A2A2E] text-[#FAFAF9] text-sm font-semibold"
            >
              打开弹窗
            </button>
          </div>
          {positions.slice(0, 2).map((p) => (
            <div key={p.id} className="mt-3 bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
              <div className="text-[#FAFAF9] text-base font-semibold truncate">{p.name || p.symbol}</div>
              <div className="text-[#6B6B70] text-sm truncate mt-1">现价 {p.current_price == null ? '-' : p.current_price.toFixed(2)} · 策略买入 {p.strategy_buy_price == null ? '-' : p.strategy_buy_price.toFixed(2)} · 策略卖出 {p.strategy_sell_price == null ? '-' : p.strategy_sell_price.toFixed(2)}</div>
            </div>
          ))}
        </div>
      </div>

      {showPortfolio && (
        <div className="fixed inset-0 z-[120] bg-black/60 flex items-center justify-center p-4">
          <div className="w-full md:max-w-2xl bg-[#0B0B0E] rounded-3xl border border-[#2A2A2E] p-5 max-h-[calc(100dvh-32px)] overflow-y-auto overscroll-contain pb-[calc(env(safe-area-inset-bottom,0px)+120px)]">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[#FAFAF9] text-xl font-semibold">我的股票</div>
                <div className="text-[#6B6B70] text-sm mt-1">大按钮 + 可滚动，方便手机操作</div>
              </div>
              <button
                onClick={() => setShowPortfolio(false)}
                className="h-11 px-4 rounded-xl bg-[#16161A] border border-[#2A2A2E] text-[#FAFAF9] text-sm font-semibold"
              >
                关闭
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
                <div className="text-[#6B6B70] text-sm">市场</div>
                <select
                  value={newMarket}
                  onChange={(e) => setNewMarket(e.target.value as any)}
                  className="mt-2 w-full bg-[#0B0B0E] border border-[#2A2A2E] rounded-xl px-4 py-3 text-[#FAFAF9] text-base"
                >
                  <option value="CN">CN</option>
                  <option value="HK">HK</option>
                  <option value="US">US</option>
                </select>
              </div>
              <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
                <div className="text-[#6B6B70] text-sm">股票代码</div>
                <input
                  value={newSymbol}
                  onChange={(e) => setNewSymbol(e.target.value)}
                  placeholder="例如 600519 / 00700 / AAPL"
                  className="mt-2 w-full bg-[#0B0B0E] border border-[#2A2A2E] rounded-xl px-4 py-3 text-[#FAFAF9] text-base"
                />
              </div>
              <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E]">
                <div className="text-[#6B6B70] text-sm">名称（可选）</div>
                <div className="flex gap-2 mt-2">
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="例如 腾讯控股"
                    className="flex-1 bg-[#0B0B0E] border border-[#2A2A2E] rounded-xl px-4 py-3 text-[#FAFAF9] text-base"
                  />
                  <button
                    onClick={handleAddPosition}
                    className="px-5 rounded-xl bg-[#6366F1] text-white text-base font-semibold"
                  >
                    添加
                  </button>
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              {positions.length > 0 ? (
                positions.map((p) => (
                  <div key={p.id} className="bg-[#16161A] rounded-3xl p-5 border border-[#2A2A2E]">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[#FAFAF9] text-lg font-semibold truncate">{p.name || p.symbol}</div>
                        <div className="text-[#6B6B70] text-sm truncate mt-1">{p.symbol} · {p.market}</div>
                      </div>
                      <button
                        onClick={() => handleDelete(p.id)}
                        className="h-11 px-4 rounded-xl bg-[#0B0B0E] border border-[#2A2A2E] text-[#E85A4F] text-base font-semibold"
                      >
                        删除
                      </button>
                    </div>

                    <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="bg-[#0B0B0E] rounded-2xl p-4">
                        <div className="text-[#6B6B70] text-sm">现价</div>
                        <div className="text-[#FAFAF9] text-lg font-bold mt-1">{p.current_price == null ? '-' : p.current_price.toFixed(2)}</div>
                      </div>
                      <div className="bg-[#0B0B0E] rounded-2xl p-4">
                        <div className="text-[#6B6B70] text-sm">策略买入价</div>
                        <div className="text-[#32D583] text-lg font-bold mt-1">{p.strategy_buy_price == null ? '-' : p.strategy_buy_price.toFixed(2)}</div>
                        <div className="text-[#6B6B70] text-xs mt-1">{p.strategy_buy_ok === true ? '确认' : (p.strategy_buy_ok === false ? '等待' : '-')}</div>
                      </div>
                      <div className="bg-[#0B0B0E] rounded-2xl p-4">
                        <div className="text-[#6B6B70] text-sm">策略卖出价</div>
                        <div className="text-[#E85A4F] text-lg font-bold mt-1">{p.strategy_sell_price == null ? '-' : p.strategy_sell_price.toFixed(2)}</div>
                        <div className="text-[#6B6B70] text-xs mt-1">{p.strategy_sell_ok === true ? '确认' : (p.strategy_sell_ok === false ? '等待' : '-')}</div>
                      </div>
                      <div className="bg-[#0B0B0E] rounded-2xl p-4">
                        <div className="text-[#6B6B70] text-sm">浮动盈亏</div>
                        <div className={`text-lg font-bold mt-1 ${(p.unrealized_pnl || 0) >= 0 ? 'text-[#32D583]' : 'text-[#E85A4F]'}`}>
                          {p.unrealized_pnl == null ? '-' : p.unrealized_pnl.toFixed(2)}
                          {p.unrealized_pnl_pct == null ? '' : ` (${p.unrealized_pnl_pct.toFixed(1)}%)`}
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 text-[#6B6B70] text-xs">
                      {p.strategy_buy_reason || p.strategy_sell_reason || ''}
                    </div>

                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="bg-[#0B0B0E] rounded-2xl p-4">
                        <div className="text-[#6B6B70] text-sm">目标买入价（你自定义）</div>
                        <input
                          defaultValue={p.target_buy_price == null ? '' : String(p.target_buy_price)}
                          onBlur={(e) => {
                            const v = e.target.value.trim();
                            handleUpdateTargets(p, v ? Number(v) : null, p.target_sell_price ?? null);
                          }}
                          placeholder="例如 280"
                          className="mt-2 w-full bg-[#16161A] border border-[#2A2A2E] rounded-xl px-4 py-3 text-[#FAFAF9] text-base"
                        />
                      </div>
                      <div className="bg-[#0B0B0E] rounded-2xl p-4">
                        <div className="text-[#6B6B70] text-sm">目标卖出价（你自定义）</div>
                        <input
                          defaultValue={p.target_sell_price == null ? '' : String(p.target_sell_price)}
                          onBlur={(e) => {
                            const v = e.target.value.trim();
                            handleUpdateTargets(p, p.target_buy_price ?? null, v ? Number(v) : null);
                          }}
                          placeholder="例如 350"
                          className="mt-2 w-full bg-[#16161A] border border-[#2A2A2E] rounded-xl px-4 py-3 text-[#FAFAF9] text-base"
                        />
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                      <button
                        onClick={() => {
                          const q = Number(prompt('买入数量（按最新价成交）', '10'));
                          if (!Number.isFinite(q) || q <= 0) return;
                          handleTrade(p.id, 'BUY', q);
                        }}
                        className="bg-[#32D583] text-[#0B0B0E] rounded-2xl py-4 font-bold text-lg"
                      >
                        买入（最新价）
                      </button>
                      <button
                        onClick={() => {
                          const q = Number(prompt('卖出数量（按最新价成交）', '10'));
                          if (!Number.isFinite(q) || q <= 0) return;
                          handleTrade(p.id, 'SELL', q);
                        }}
                        className="bg-[#E85A4F] text-white rounded-2xl py-4 font-bold text-lg"
                      >
                        卖出（最新价）
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="bg-[#16161A] rounded-2xl p-8 border border-[#2A2A2E] text-center">
                  <p className="text-[#6B6B70]">暂无持仓，先添加一只股票</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Multi-Company Comparison */}
      <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
        <h3 className="text-[#FAFAF9] text-lg font-semibold mb-2">多公司财务对比</h3>
        <p className="text-[#6B6B70] text-sm mb-4">选择公司进行横向财务指标对比分析</p>
        <div className="flex gap-3 mb-4">
          <div className="flex-1 bg-[#1A1A1E] rounded-xl py-4 px-4 text-[#FAFAF9] text-base border border-[#2A2A2E]">
            腾讯控股
          </div>
          <div className="flex-1 bg-[#1A1A1E] rounded-xl py-4 px-4 text-[#FAFAF9] text-base border border-[#2A2A2E]">
            阿里巴巴
          </div>
        </div>
        <Link
          href="/compare"
          className="block bg-[#6366F1] text-white rounded-xl py-4 px-4 text-center font-semibold text-base"
        >
          🔍 开始对比分析
        </Link>
      </div>

      {/* Recent Stock Searches */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[#FAFAF9] text-lg font-semibold">最近查询股票</h3>
          <Link href="/stock" className="text-[#32D583] text-sm font-medium">查看全部 →</Link>
        </div>
        <div className="flex flex-col gap-3">
          {recentStocks.length > 0 ? (
            recentStocks.slice(0, 10).map((s) => (
              <div
                key={`${s.market}:${s.symbol}`}
                onClick={() => router.push(`/stock?symbol=${encodeURIComponent(s.symbol)}&market=${encodeURIComponent(s.market)}&name=${encodeURIComponent(s.name)}`)}
                className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] flex items-center justify-between cursor-pointer active:bg-[#1A1A1E]"
              >
                <div className="min-w-0">
                  <div className="text-[#FAFAF9] text-base font-semibold truncate">{s.name}</div>
                  <div className="text-[#6B6B70] text-sm truncate">{s.symbol} · {s.market}</div>
                </div>
                <span className="text-[#6B6B70]">→</span>
              </div>
            ))
          ) : (
            <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70]">暂无记录，去“查询”搜索一只股票</p>
            </div>
          )}
        </div>
      </div>

      {/* Recent Analysis */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[#FAFAF9] text-lg font-semibold">最近分析</h3>
          <Link href="/reports" className="text-[#32D583] text-sm font-medium">
            查看全部 →
          </Link>
        </div>
        <div className="flex flex-col gap-3">
          {loading ? (
            <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70]">加载中...</p>
            </div>
          ) : reports.length > 0 ? (
            reports.map((report) => (
              <ReportItem
                key={report.id}
                title={report.report_name}
                source={report.source_type === 'market_fetch' ? '市场数据' : '文件上传'}
                date={formatDateTime(report.created_at)}
                status={report.status}
                onClick={() => router.push(`/reports/${report.id}`)}
              />
            ))
          ) : (
            <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] text-center">
              <p className="text-[#6B6B70]">暂无报告，点击上传开始分析</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
