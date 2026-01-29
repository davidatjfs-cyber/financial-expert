from __future__ import annotations

import os
import json
import re
import httpx
from typing import Optional
from dataclasses import asdict


QWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"


def get_api_key() -> str:
    """获取阿里云 API Key"""
    return os.environ.get("DASHSCOPE_API_KEY", "")


def test_qwen_connection(api_key: Optional[str] = None) -> tuple[bool, str]:
    key = api_key or get_api_key()
    if not key:
        return False, "missing_api_key"

    try:
        resp = httpx.post(
            QWEN_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen-turbo",
                "input": {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "ping"},
                    ]
                },
                "parameters": {"temperature": 0.0, "max_tokens": 16},
            },
            timeout=15.0,
        )
        if resp.status_code >= 400:
            return False, f"http_{resp.status_code}:{resp.text[:500]}"
        data = resp.json()
        if (data or {}).get("output"):
            return True, "ok"
        return False, f"unexpected_response:{str(data)[:500]}"
    except Exception as e:
        return False, f"exception:{e}"


def extract_financials_with_ai(pdf_text: str, api_key: Optional[str] = None, raise_on_error: bool = False) -> dict:
    """使用 AI 从 PDF 文本中提取财务数据"""
    key = api_key or get_api_key()
    if not key:
        if raise_on_error:
            raise RuntimeError("missing_api_key")
        return {}
    
    # 限制文本长度
    max_len = 15000
    if len(pdf_text) > max_len:
        pdf_text = pdf_text[:max_len] + "\n...(文本已截断)"
    
    prompt = """请从以下财务报表文本中提取关键财务数据。严格按照 JSON 格式返回，不要添加任何其他文字。

需要提取的字段（如果找不到则填 null）：
{
    "report_period": "报告期，格式：YYYY-MM-DD",
    "report_year": "报告年份，如 2024",
    "revenue": "营业收入/营业总收入（数字，单位：百万元）",
    "net_profit": "净利润/归属于股东的净利润（数字，单位：百万元）",
    "total_assets": "资产总额/总资产（数字，单位：百万元）",
    "total_liabilities": "负债总额/总负债（数字，单位：百万元）",
    "total_equity": "股东权益/所有者权益（数字，单位：百万元）",
    "gross_profit": "毛利润（数字，单位：百万元）",
    "gross_margin": "毛利率（百分比数字，如 32.5）",
    "net_margin": "净利率（百分比数字）",
    "roe": "净资产收益率/ROE（百分比数字）",
    "roa": "总资产收益率/ROA（百分比数字）",
    "current_ratio": "流动比率（数字）",
    "quick_ratio": "速动比率（数字）",
    "debt_ratio": "资产负债率（百分比数字）",
    "current_assets": "流动资产（数字，单位：百万元）",
    "current_liabilities": "流动负债（数字，单位：百万元）"
}

注意：
1. 数字不要包含逗号，直接返回数值
2. 如果是亿元单位，请转换为百万元（乘以100）
3. 如果是万元单位，请转换为百万元（除以100）
4. 百分比只返回数字部分，不要包含%符号

财务报表文本：
""" + pdf_text + """

请直接返回 JSON，不要有任何前缀或后缀文字："""

    try:
        response = httpx.post(
            QWEN_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen-plus",  # 使用更强的模型提取数据
                "input": {
                    "messages": [
                        {"role": "system", "content": "你是一个财务数据提取专家。你只返回 JSON 格式的数据，不添加任何解释文字。"},
                        {"role": "user", "content": prompt},
                    ]
                },
                "parameters": {
                    "temperature": 0.1,  # 低温度确保准确性
                    "max_tokens": 1500,
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        # 提取返回的文本
        text = ""
        if "output" in data and "text" in data["output"]:
            text = data["output"]["text"]
        elif "output" in data and "choices" in data["output"]:
            text = data["output"]["choices"][0]["message"]["content"]
        
        if not text:
            return {}
        
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        # 容错：截取最外层 JSON
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]

        result = json.loads(text)
        return result

    except httpx.HTTPStatusError as e:
        resp = e.response
        try:
            body = resp.text
        except Exception:
            body = ""
        print(f"AI extraction HTTP error: {resp.status_code}, body: {body[:500]}")
        if raise_on_error:
            raise RuntimeError(f"qwen_http_{resp.status_code}:{body[:300]}")
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}, text: {text[:200] if text else 'empty'}")
        if raise_on_error:
            raise RuntimeError(f"qwen_json_parse_error:{e}")
        return {}
    except Exception as e:
        print(f"AI extraction error: {e}")
        if raise_on_error:
            raise RuntimeError(f"qwen_exception:{e}")
        return {}


def merge_ai_extracted_data(extracted: dict, ai_data: dict):
    """将 AI 提取的数据合并到已提取的数据中"""
    from core.pdf_analyzer import ExtractedFinancials
    
    # 映射关系
    field_map = {
        "report_period": "report_period",
        "report_year": "report_year",
        "revenue": "revenue",
        "net_profit": "net_profit",
        "total_assets": "total_assets",
        "total_liabilities": "total_liabilities",
        "total_equity": "total_equity",
        "gross_profit": "gross_profit",
        "current_assets": "current_assets",
        "current_liabilities": "current_liabilities",
        "gross_margin": "gross_margin_direct",
        "net_margin": "net_margin_direct",
        "roe": "roe_direct",
        "roa": "roa_direct",
        "current_ratio": "current_ratio_direct",
        "debt_ratio": "debt_ratio_direct",
    }
    
    def _to_float(v):
        try:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            sv = str(v).strip()
            if sv in ("", "null", "None", "nan", "NaN", "--"):
                return None
            return float(sv)
        except Exception:
            return None

    def _should_override(cur: float | None, ai: float | None, is_pct: bool) -> bool:
        if ai is None:
            return False
        if cur is None:
            return True
        if cur == 0.0:
            return True

        # 百分比字段：通常 0~100；明显越界就用 AI
        if is_pct:
            if not (0.0 <= cur <= 100.0) and (0.0 <= ai <= 100.0):
                return True
            return False

        # 金额字段：允许 AI 纠错数量级错误（>=10x）
        if cur != 0 and ai != 0:
            ratio = abs(ai / cur)
            if ratio >= 10 or ratio <= 0.1:
                return True
        return False

    overridden = []
    for ai_field, extracted_field in field_map.items():
        ai_value = _to_float(ai_data.get(ai_field))
        cur_value = _to_float(getattr(extracted, extracted_field, None))
        is_pct = ai_field in {
            "gross_margin",
            "net_margin",
            "roe",
            "roa",
            "debt_ratio",
        }
        if _should_override(cur_value, ai_value, is_pct=is_pct):
            try:
                setattr(extracted, extracted_field, ai_value)
                overridden.append(ai_field)
            except Exception:
                pass

    if overridden:
        try:
            setattr(extracted, "_ai_overrode", overridden)
        except Exception:
            pass


def analyze_financials_with_qwen(
    company_name: str,
    metrics: dict[str, float],
    api_key: Optional[str] = None,
) -> str:
    """使用千问分析财务数据"""
    key = api_key or get_api_key()
    if not key:
        return _generate_fallback_analysis(company_name, metrics)

    # 构建提示词
    metrics_text = "\n".join([f"- {k}: {v:.4f}" for k, v in metrics.items() if v is not None])

    prompt = f"""你是一位卖方研究员 + 买方投研经理，擅长把财务指标转化为可执行的投资建议。

请基于下列财务指标，为【{company_name}】生成一份“专业财务与投资建议报告”（中文）。

【输入财务指标】
{metrics_text}

【输出要求】
1) 输出必须结构化，使用清晰的小标题与条目。
2) 必须覆盖以下章节（缺失信息允许说明“数据不足/无法判断”）：
   - 一、投资结论摘要（3-6条要点）
   - 二、财务质量诊断（盈利能力/偿债能力/营运效率/资本结构）
   - 三、关键指标解读（对 ROE/ROA/毛利率/净利率/资产负债率/流动比率/速动比率/周转率 等进行解释，并给出判断区间）
   - 四、风险清单（至少5条：经营/财务/行业/政策/市场/治理等维度）
   - 五、情景分析（基准/乐观/悲观：分别给出关注点与可能触发条件）
   - 六、投资建议与策略（适合的投资者类型、建议仓位区间、关注的关键指标/事件、止损/风控框架）
   - 七、免责声明（明确非投资建议）
3) 语气专业、审慎，避免夸张承诺。
4) 控制在 800-1200 中文字左右。
5) 若某些指标含义不明确（如单位/口径），请先说明假设口径再给出结论。
"""

    try:
        response = httpx.post(
            QWEN_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen-turbo",
                "input": {
                    "messages": [
                        {"role": "system", "content": "你是一位专业的财务分析师，擅长分析企业财务报表和财务指标。"},
                        {"role": "user", "content": prompt},
                    ]
                },
                "parameters": {
                    "temperature": 0.3,
                    "max_tokens": 1800,
                },
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        if "output" in data and "text" in data["output"]:
            return data["output"]["text"]
        elif "output" in data and "choices" in data["output"]:
            return data["output"]["choices"][0]["message"]["content"]
        else:
            return _generate_fallback_analysis(company_name, metrics)

    except httpx.HTTPStatusError as e:
        resp = e.response
        try:
            body = resp.text
        except Exception:
            body = ""
        print(f"Qwen API HTTP error: {resp.status_code}, body: {body[:500]}")
        return _generate_fallback_analysis(company_name, metrics)
    except Exception as e:
        print(f"Qwen API error: {e}")
        return _generate_fallback_analysis(company_name, metrics)


def _generate_fallback_analysis(company_name: str, metrics: dict[str, float]) -> str:
    """生成备用分析（当 API 不可用时）"""
    analysis_parts = []

    # 盈利能力
    gross_margin = metrics.get("GROSS_MARGIN")
    net_margin = metrics.get("NET_MARGIN")
    roe = metrics.get("ROE")

    if gross_margin is not None or net_margin is not None:
        if gross_margin and gross_margin > 40:
            analysis_parts.append(f"**盈利能力**：毛利率达到 {gross_margin:.2f}%，表现出色，产品具有较强的市场竞争力和定价能力。")
        elif gross_margin and gross_margin > 25:
            analysis_parts.append(f"**盈利能力**：毛利率为 {gross_margin:.2f}%，处于行业中等水平，盈利能力稳健。")
        elif gross_margin:
            analysis_parts.append(f"**盈利能力**：毛利率为 {gross_margin:.2f}%，相对较低，建议关注成本控制和产品结构优化。")

    # 偿债能力
    debt_asset = metrics.get("DEBT_ASSET")
    current_ratio = metrics.get("CURRENT_RATIO")

    if debt_asset is not None:
        if debt_asset < 40:
            analysis_parts.append(f"**偿债能力**：资产负债率仅 {debt_asset:.2f}%，财务结构非常稳健，偿债压力小。")
        elif debt_asset < 60:
            analysis_parts.append(f"**偿债能力**：资产负债率 {debt_asset:.2f}%，处于合理区间，财务风险可控。")
        else:
            analysis_parts.append(f"**偿债能力**：资产负债率达到 {debt_asset:.2f}%，财务杠杆较高，需关注偿债风险。")

    # 综合评分
    score = _calculate_health_score(metrics)
    if score >= 80:
        rating = "优秀"
    elif score >= 60:
        rating = "良好"
    elif score >= 40:
        rating = "一般"
    else:
        rating = "较差"

    analysis_parts.append(f"**综合评分**：财务健康度评分 **{score}分**（{rating}）。")

    # 投资建议
    if score >= 70:
        analysis_parts.append("**投资建议**：公司财务状况良好，具备一定的投资价值，建议持续关注业绩增长情况。")
    elif score >= 50:
        analysis_parts.append("**投资建议**：公司财务状况一般，建议谨慎投资，重点关注风险指标的变化趋势。")
    else:
        analysis_parts.append("**投资建议**：公司财务状况存在一定风险，建议暂时观望，等待基本面改善。")

    return "\n\n".join(analysis_parts)


def _calculate_health_score(metrics: dict[str, float]) -> int:
    """计算财务健康度评分"""
    score = 50  # 基础分

    gross_margin = metrics.get("GROSS_MARGIN")
    if gross_margin:
        if gross_margin > 40:
            score += 15
        elif gross_margin > 25:
            score += 10
        elif gross_margin > 15:
            score += 5

    net_margin = metrics.get("NET_MARGIN")
    if net_margin:
        if net_margin > 15:
            score += 15
        elif net_margin > 8:
            score += 10
        elif net_margin > 3:
            score += 5
        elif net_margin < 0:
            score -= 10

    roe = metrics.get("ROE")
    if roe:
        if roe > 20:
            score += 10
        elif roe > 12:
            score += 5
        elif roe < 5:
            score -= 5

    debt_asset = metrics.get("DEBT_ASSET")
    if debt_asset:
        if debt_asset < 40:
            score += 10
        elif debt_asset < 55:
            score += 5
        elif debt_asset > 70:
            score -= 10

    current_ratio = metrics.get("CURRENT_RATIO")
    if current_ratio:
        if current_ratio > 2:
            score += 5
        elif current_ratio < 1:
            score -= 10

    return max(0, min(100, score))
