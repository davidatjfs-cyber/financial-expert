/**
 * API service for connecting to the FastAPI backend
 */

// Dynamically determine API URL based on current host
function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  const normalize = (u: string) => u.replace(/\/+$/, '');

  if (typeof window === 'undefined') {
    return normalize(envUrl || 'http://localhost:8000');
  }

  if (envUrl) {
    return normalize(envUrl);
  }

  // Use same host as frontend but port 8000
  const host = window.location.hostname;
  return `http://${host}:8000`;
}

// ============ Types ============

export interface Stats {
  total: number;
  done: number;
  risks: number;
  rate: number;
}

export interface Report {
  id: string;
  report_name: string;
  source_type: string;
  period_type: string;
  period_end: string;
  status: 'done' | 'running' | 'failed' | 'pending';
  created_at: number;
  updated_at: number;
}

export interface ReportDetail extends Report {
  error_message?: string;
  created_at: number;
  company_id?: string;
  market?: string;
}

export interface Metric {
  metric_code: string;
  metric_name: string;
  value: number | null;
  unit?: string;
  period_end: string;
}

export interface Alert {
  id: string;
  alert_code: string;
  level: 'high' | 'medium' | 'low';
  title: string;
  message: string;
  period_end: string;
}

export interface AlertsSummary {
  high: number;
  medium: number;
  low: number;
}

export interface StockSearchResult {
  symbol: string;
  name: string;
  market: string;
}

export interface StockPrice {
  symbol: string;
  name: string;
  market: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  high: number | null;
  low: number | null;
  amount?: number | null;
  open?: number | null;
  prev_close?: number | null;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
  amplitude?: number | null;
  bid?: number | null;
  ask?: number | null;
}

export interface StockIndicators {
  symbol: string;
  name?: string | null;
  market: string;
  currency?: string | null;
  as_of?: string | null;

  market_cap?: number | null;
  amount?: number | null;
  high_52w?: number | null;
  low_52w?: number | null;
  ma5?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  rsi14?: number | null;
  macd_dif?: number | null;
  macd_dea?: number | null;
  macd_hist?: number | null;

  buy_price_aggressive?: number | null;
  buy_price_stable?: number | null;
  sell_price?: number | null;

  signal_golden_cross?: boolean | null;
  signal_death_cross?: boolean | null;
  signal_macd_bullish?: boolean | null;
  signal_rsi_overbought?: boolean | null;
  signal_vol_gt_ma5?: boolean | null;
  signal_vol_gt_ma10?: boolean | null;
}

// ============ API Functions ============

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get dashboard statistics
 */
export async function getStats(): Promise<Stats> {
  return fetchAPI<Stats>('/api/stats');
}

/**
 * Get list of reports
 */
export async function getReports(limit = 50, status?: string): Promise<Report[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.append('status', status);
  return fetchAPI<Report[]>(`/api/reports?${params}`);
}

/**
 * Get report details
 */
export async function getReportDetail(reportId: string): Promise<ReportDetail> {
  return fetchAPI<ReportDetail>(`/api/reports/${reportId}`);
}

/**
 * Get computed metrics for a report
 */
export async function getReportMetrics(reportId: string): Promise<Metric[]> {
  return fetchAPI<Metric[]>(`/api/reports/${reportId}/metrics`);
}

/**
 * Get alerts for a report
 */
export async function getReportAlerts(reportId: string): Promise<Alert[]> {
  return fetchAPI<Alert[]>(`/api/reports/${reportId}/alerts`);
}

export async function reanalyzeReport(reportId: string): Promise<{ report_id: string; status: string; message: string }> {
  return fetchAPI<{ report_id: string; status: string; message: string }>(`/api/reports/${reportId}/reanalyze`, {
    method: 'POST',
  });
}

/**
 * Get all alerts
 */
export async function getAllAlerts(level?: string, limit = 50): Promise<Alert[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) params.append('level', level);
  return fetchAPI<Alert[]>(`/api/alerts?${params}`);
}

/**
 * Get alerts summary
 */
export async function getAlertsSummary(): Promise<AlertsSummary> {
  return fetchAPI<AlertsSummary>('/api/alerts/summary');
}

/**
 * Search for stocks
 */
export async function searchStocks(query: string, market = 'CN'): Promise<StockSearchResult[]> {
  const params = new URLSearchParams({ q: query, market });
  return fetchAPI<StockSearchResult[]>(`/api/stock/search?${params}`);
}

/**
 * Get stock price
 */
export async function getStockPrice(symbol: string, market: string = 'CN') {
  return fetchAPI<StockPrice | null>(`/api/stock/price?symbol=${encodeURIComponent(symbol)}&market=${market}`);
}

/**
 * Get stock indicators
 */
export async function getStockIndicators(symbol: string, market: string = 'CN') {
  return fetchAPI<StockIndicators | null>(`/api/stock/indicators?symbol=${encodeURIComponent(symbol)}&market=${market}`);
}

/**
 * Upload a financial report file
 */
export async function uploadReport(
  file: File,
  companyName: string,
  periodType: string,
  periodEnd: string
): Promise<{ report_id: string; message: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('company_name', companyName);
  formData.append('period_type', periodType);
  formData.append('period_end', periodEnd);

  const response = await fetch(`${getApiBaseUrl()}/api/reports/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch market report for a stock
 */
export async function fetchMarketReport(
  symbol: string,
  market = 'CN',
  periodType = 'annual',
  periodEnd = '2024-12-31'
): Promise<{ report_id: string; message: string }> {
  const params = new URLSearchParams({
    symbol,
    market,
    period_type: periodType,
    period_end: periodEnd,
  });

  return fetchAPI(`/api/reports/fetch?${params}`, { method: 'POST' });
}
