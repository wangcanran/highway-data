"""
多智能体协作系统 - 基于LangGraph实现自主规划和API调用
包含三个专业Agent：
- Planner（规划器）：理解需求、分解任务、制定执行计划
- DataFetcher（数据获取）：调用API获取所需数据
- Analyzer（分析器）：综合数据、生成洞察、输出结果
"""
import os
import requests
import json
from typing import TypedDict, Annotated, Sequence, Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta
import config
import uuid

# 注意：审计功能已移至app.py全局中间件，此处不再需要AuditLog
from models import db

# API基础配置
API_BASE_URL = "http://localhost:5000"

# 初始化LLM（使用config配置）
llm = ChatOpenAI(
    model=config.FIXED_MODEL_NAME,
    temperature=0.3,
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_API_BASE
)


# ==================== 状态定义 ====================

class MultiAgentState(TypedDict):
    """多智能体协作状态"""
    messages: Sequence[BaseMessage]
    user_query: str
    plan: Dict[str, Any]  # Planner生成的执行计划
    api_calls: List[Dict[str, Any]]  # DataFetcher执行的API调用记录
    data_collected: Dict[str, Any]  # 收集到的数据
    analysis_result: Dict[str, Any]  # Analyzer生成的分析结果
    execution_logs: List[str]  # 执行日志
    error: str
    next_agent: str  # 下一个执行的agent
    parent_trace_id: str  # 父级追踪ID，用于审计


# ==================== API工具定义 ====================

API_TOOLS = {
    "get_entrance_transactions": {
        "name": "get_entrance_transactions",
        "description": "【整体车辆】获取入口交易记录，用于查询车辆入站信息",
        "endpoint": "/api/transactions/entrance",
        "method": "GET",
        "data_scope": "all_vehicles",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD", "required": False},
            "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD", "required": False},
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "入口交易记录列表，包含：section_id(路段ID), entrance_time(入口时间), vehicle_class(车辆类型), vehicle_plate_color_id(车牌颜色)"
    },
    "get_exit_transactions": {
        "name": "get_exit_transactions",
        "description": "【整体车辆】获取出口交易记录，用于查询车辆出站和费用信息",
        "endpoint": "/api/transactions/exit",
        "method": "GET",
        "data_scope": "all_vehicles",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD", "required": False},
            "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD", "required": False},
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "出口交易记录列表，包含：section_id(路段ID), exit_time(出口时间), toll_money(通行费), real_money(实际费用), vehicle_class(车辆类型), axis_count(轴数), total_weight(总重)"
    },
    "get_gantry_transactions": {
        "name": "get_gantry_transactions",
        "description": "【整体车辆】获取门架交易记录，用于查询门架通行数据和费用明细",
        "endpoint": "/api/transactions/gantry",
        "method": "GET",
        "data_scope": "all_vehicles",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD", "required": False},
            "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD", "required": False},
            "gantry_id": {"type": "string", "description": "门架ID", "required": False},
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "门架交易记录列表，包含：gantry_id(门架ID), section_id(路段ID), transaction_time(交易时间), pay_fee(支付费用), fee(费用明细), vehicle_type(车辆类型), axle_count(轴数), total_weight(总重)"
    },
    "get_all_transactions": {
        "name": "get_all_transactions",
        "description": "【整体车辆】获取所有交易记录（入口+出口），用于全面分析",
        "endpoint": "/api/transactions/all",
        "method": "GET",
        "data_scope": "all_vehicles",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD", "required": False},
            "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD", "required": False}
        },
        "returns": "完整交易记录列表，包含：入口信息(entrance_time, entrance_station)和出口信息(exit_time, exit_station, toll_money, real_money)"
    },
    "get_sections": {
        "name": "get_sections",
        "description": "获取所有路段信息",
        "endpoint": "/api/sections",
        "method": "GET",
        "parameters": {},
        "returns": "路段信息列表，包含：section_id(路段ID), section_name(路段名称), start_station(起点), end_station(终点), length(长度), lane_count(车道数)"
    },
    "get_hourly_flow": {
        "name": "get_hourly_flow",
        "description": "【货车专项】获取路段小时流量数据",
        "endpoint": "/api/analytics/truck/hourly-flow",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False},
            "start_date": {"type": "string", "description": "开始日期", "required": False},
            "end_date": {"type": "string", "description": "结束日期", "required": False}
        },
        "returns": "小时流量数据，包含：section_id(路段ID), hour(小时), truck_count(货车数量)"
    },
    "get_avg_travel_time": {
        "name": "get_avg_travel_time",
        "description": "【货车专项】获取路段平均通行时间",
        "endpoint": "/api/analytics/truck/avg-travel-time",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "平均通行时间统计，包含：section_id(路段ID), avg_travel_time_minutes(平均通行时间-分钟), sample_count(样本数量)"
    },
    "get_avg_toll_fee": {
        "name": "get_avg_toll_fee",
        "description": "【货车专项】获取路段平均通行费",
        "endpoint": "/api/analytics/truck/avg-toll-fee",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "平均通行费统计，包含：section_id(路段ID), avg_toll_fee(平均通行费-元), transaction_count(交易数量)"
    },
    "get_congestion_index": {
        "name": "get_congestion_index",
        "description": "【货车专项】获取路段拥堵指数",
        "endpoint": "/api/analytics/truck/congestion-index",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "拥堵指数数据，包含：section_id(路段ID), truck_count(货车数量), avg_lanes(平均车道数), congestion_index(拥堵指数=车流量/车道数)"
    },
    "get_overweight_rate": {
        "name": "get_overweight_rate",
        "description": "【货车专项】获取路段超载比例（数据脱敏）",
        "endpoint": "/api/analytics/truck/overweight-rate",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "超载比例统计，包含：section_id(路段ID-已脱敏), total_count(总车辆数), overweight_count(超载车辆数), overweight_rate(超载比例), overweight_percentage(超载百分比)"
    },
    "get_toll_stations": {
        "name": "get_toll_stations",
        "description": "获取收费站信息，支持按路段筛选",
        "endpoint": "/api/toll-stations",
        "method": "GET",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False},
            "station_type": {"type": "string", "description": "收费站类型", "required": False}
        },
        "returns": "收费站信息列表，包含：station_id(收费站ID), station_name(收费站名称), section_id(路段ID), station_type(类型), location(位置)"
    },
    "get_gantries": {
        "name": "get_gantries",
        "description": "获取门架信息，支持按路段筛选",
        "endpoint": "/api/gantries",
        "method": "GET",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "门架信息列表，包含：gantry_id(门架ID), gantry_name(门架名称), section_id(路段ID), location(位置), gantry_type(类型)"
    },
    "get_traffic_flow_statistics": {
        "name": "get_traffic_flow_statistics",
        "description": "获取交通流量统计数据",
        "endpoint": "/api/statistics/traffic-flow",
        "method": "GET",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期", "required": False},
            "end_date": {"type": "string", "description": "结束日期", "required": False},
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "交通流量统计，包含：total_vehicles(总车辆数), avg_daily_flow(日均流量), peak_flow(峰值流量), flow_by_hour(按小时流量分布)"
    },
    "get_revenue_statistics": {
        "name": "get_revenue_statistics",
        "description": "获取收费统计数据",
        "endpoint": "/api/statistics/revenue",
        "method": "GET",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期", "required": False},
            "end_date": {"type": "string", "description": "结束日期", "required": False},
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "收费统计，包含：total_revenue(总收入), avg_daily_revenue(日均收入), avg_toll_fee(平均通行费), revenue_by_vehicle_class(按车型收入)"
    },
    "get_vehicle_distribution": {
        "name": "get_vehicle_distribution",
        "description": "获取车型分布统计",
        "endpoint": "/api/statistics/vehicle-distribution",
        "method": "GET",
        "parameters": {
            "start_date": {"type": "string", "description": "开始日期", "required": False},
            "end_date": {"type": "string", "description": "结束日期", "required": False},
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "车型分布统计，包含：vehicle_class(车型), count(数量), percentage(百分比), avg_toll(平均通行费)"
    },
    "get_exit_hourly_flow": {
        "name": "get_exit_hourly_flow",
        "description": "【货车专项】获取路段出口小时流量数据",
        "endpoint": "/api/analytics/truck/exit-hourly-flow",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False},
            "start_date": {"type": "string", "description": "开始日期", "required": False},
            "end_date": {"type": "string", "description": "结束日期", "required": False}
        },
        "returns": "出口小时流量数据，包含：section_id(路段ID), hour(小时), truck_count(货车数量), exit_time(出口时间)"
    },
    "get_discount_rate": {
        "name": "get_discount_rate",
        "description": "【货车专项】获取路段通行费优惠比例",
        "endpoint": "/api/analytics/truck/discount-rate",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "优惠比例统计，包含：section_id(路段ID), total_count(总数), discount_count(优惠数), discount_rate(优惠比例), avg_discount_amount(平均优惠金额)"
    },
    "get_peak_hours": {
        "name": "get_peak_hours",
        "description": "【货车专项】获取路段高峰时段，识别流量最高的小时区间",
        "endpoint": "/api/analytics/truck/peak-hours",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "高峰时段数据，包含：section_id(路段ID), peak_hour(高峰小时), truck_count(货车数量), ranking(排名)"
    },
    "get_avg_axle_count": {
        "name": "get_avg_axle_count",
        "description": "【货车专项】获取路段货车平均轴数，反映货车类型分布",
        "endpoint": "/api/analytics/truck/avg-axle-count",
        "method": "GET",
        "data_scope": "truck_only",
        "parameters": {
            "section_id": {"type": "string", "description": "路段ID", "required": False}
        },
        "returns": "平均轴数统计，包含：section_id(路段ID), avg_axle_count(平均轴数), truck_count(货车数量), axle_distribution(轴数分布)"
    }
}


def execute_api_call(tool_name: str, params: Dict[str, Any], parent_trace_id: str = None, client_info: Dict[str, str] = None) -> Dict[str, Any]:
    """执行API调用（简化版，审计由全局中间件处理）
    
    Args:
        tool_name: API工具名称
        params: 调用参数
        parent_trace_id: 父级追踪ID（传递给HTTP请求头，供全局中间件关联）
        client_info: 客户端信息（可选，用于日志）
    """
    if tool_name not in API_TOOLS:
        return {"success": False, "error": f"未知的API工具: {tool_name}"}
    
    tool = API_TOOLS[tool_name]
    endpoint = tool["endpoint"]
    method = tool["method"]
    
    # 执行API调用
    start_time = datetime.now()
    try:
        url = f"{API_BASE_URL}{endpoint}"
        print(f"[API调用] {method} {url} params={params}")
        
        # 传递parent_trace_id到HTTP请求头，供全局中间件关联调用链
        headers = {}
        if parent_trace_id:
            headers['X-Parent-Trace-ID'] = parent_trace_id
        
        if method == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=30)
        else:
            response = requests.post(url, json=params, headers=headers, timeout=30)
        
        end_time = datetime.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        data = response.json()
        success = data.get('success', response.status_code == 200)
        print(f"[API返回] success={success}, count={data.get('count', len(data.get('data', [])))} records, time={response_time_ms}ms")
        
        return data
        
    except Exception as e:
        print(f"[API错误] {tool_name}: {e}")
        return {"success": False, "error": str(e)}


def _resolve_param_dependencies(params: Dict[str, Any], data_collected: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析参数中的依赖关系，从前面步骤的结果中提取实际值
    
    示例：
    - "麻文高速对应的section_id" → 从步骤1的路段列表中查找麻文高速的section_id
    - "步骤1返回的路段ID" → 从步骤1的结果中提取section_id
    """
    resolved_params = {}
    
    for key, value in params.items():
        if not isinstance(value, str):
            resolved_params[key] = value
            continue
        
        # 检查是否为占位符文本（包含中文描述的参数值）
        if any(keyword in value for keyword in ['对应的', '返回的', '步骤', '中的', '查找到的']):
            print(f"[DEBUG] 检测到占位符参数: {key}={value}")
            
            # 尝试从已收集的数据中提取实际值
            actual_value = _extract_value_from_collected_data(value, data_collected)
            
            if actual_value:
                print(f"[DEBUG] 替换为实际值: {key}={actual_value}")
                resolved_params[key] = actual_value
            else:
                print(f"[WARN] 无法解析占位符参数: {key}={value}，保持原值")
                resolved_params[key] = value
        else:
            resolved_params[key] = value
    
    return resolved_params


def _extract_value_from_collected_data(placeholder: str, data_collected: Dict[str, Any]) -> str:
    """从已收集的数据中提取占位符对应的实际值"""
    
    # 查找路段ID（最常见的依赖）
    if 'section_id' in placeholder or '路段' in placeholder:
        # 提取路段名称
        section_name = None
        for keyword in ['麻文高速', '都香高速', '彝良至昭通高速', '彝良至镇雄高速', 
                        '宜宾至毕节高速', '青龙咎至水田新区高速', '大关至永善高速', '昭阳西环高速']:
            if keyword in placeholder:
                section_name = keyword
                break
        
        if section_name:
            # 从所有步骤的结果中查找该路段
            for step_key, step_data in data_collected.items():
                if isinstance(step_data, dict) and 'sample' in step_data:
                    records = step_data.get('sample', [])
                    for record in records:
                        if isinstance(record, dict) and record.get('section_name') == section_name:
                            return record.get('section_id', '')
                    
                    # 如果sample中没找到，尝试从summary中查找
                    summary = step_data.get('summary', {})
                    if isinstance(summary, dict) and 'section_names' in summary:
                        section_names = summary.get('section_names', [])
                        if section_name in section_names:
                            # 找到索引，尝试从原始数据或其他地方获取ID
                            # 这里简化处理，根据已知映射返回
                            section_mapping = {
                                '麻文高速': 'G5615530120',
                                '都香高速': 'G7611530010',
                                '彝良至昭通高速': 'S0010530010',
                                '彝良至镇雄高速公路': 'S0010530020',
                                '宜宾至毕节高速威信至镇雄段': 'S0014530010',
                                '青龙咎至水田新区高速': 'S0014530020',
                                '大关至永善高速': 'S0014530030',
                                '昭阳西环高速公路': 'S0071530020'
                            }
                            return section_mapping.get(section_name, '')
    
    # 其他类型的依赖关系可以在这里扩展
    
    return ''


def _preprocess_data(raw_data: List[Dict], tool_name: str) -> Dict[str, Any]:
    """预处理数据，生成统计摘要而不是传递全部原始数据"""
    if not raw_data:
        return {}
    
    summary = {
        'count': len(raw_data),
        'tool': tool_name
    }
    
    # 根据不同的API类型进行针对性统计
    if 'transaction' in tool_name:
        # 交易类数据：统计费用
        if 'toll_money' in raw_data[0]:
            total_toll = sum(float(item.get('toll_money', 0)) for item in raw_data)
            avg_toll = total_toll / len(raw_data) if raw_data else 0
            summary['total_toll_fee'] = round(total_toll, 2)
            summary['average_toll_fee'] = round(avg_toll, 2)
        
        if 'real_money' in raw_data[0]:
            total_real = sum(float(item.get('real_money', 0)) for item in raw_data)
            summary['total_real_money'] = round(total_real, 2)
        
        # 统计路段分布
        if 'section_id' in raw_data[0]:
            sections = set(item.get('section_id') for item in raw_data if item.get('section_id'))
            summary['unique_sections'] = len(sections)
            summary['sections'] = list(sections)[:10]  # 最多列举10个
    
    elif 'flow' in tool_name:
        # 流量类数据：统计车流量
        if 'truck_count' in raw_data[0]:
            total_trucks = sum(int(item.get('truck_count', 0)) for item in raw_data)
            summary['total_truck_count'] = total_trucks
            summary['average_truck_count'] = round(total_trucks / len(raw_data), 2) if raw_data else 0
    
    elif 'section' in tool_name:
        # 路段数据：统计路段数量
        summary['total_sections'] = len(raw_data)
        if 'section_name' in raw_data[0]:
            summary['section_names'] = [item.get('section_name') for item in raw_data[:10]]
    
    return summary


# ==================== Agent 1: Planner（规划器）====================

def planner_agent(state: MultiAgentState) -> MultiAgentState:
    """
    规划器Agent：理解用户需求，分解任务，制定执行计划
    """
    user_query = state['user_query']
    
    # 构建工具描述（包含返回字段信息）
    tools_description = "\n".join([
        f"- {name}: {tool['description']}\n  返回字段: {tool.get('returns', '无说明')}" 
        for name, tool in API_TOOLS.items()
    ])
    
    system_prompt = f"""你是一个高速公路数据分析规划助手。

**重要原则**：
1. 你只负责规划API数据获取步骤
2. 所有计算、汇总、分析由Analyzer Agent自动完成
3. 不要将"计算"、"汇总"、"统计"作为API步骤
4. 每个步骤必须是一个具体的API调用

**核心方法 - 字段驱动选择**：
1. 仔细阅读用户需求，提取关键数据需求（如：收入、费用、流量、时间等）
2. 查看每个API的"返回字段"说明
3. **根据返回字段与需求的匹配度**选择API，而不是仅凭API名称猜测
4. 如果需求涉及多个数据维度，规划多个API调用

**⚠️ 数据口径一致性警告（极其重要）**：
API分为两类，**严禁混用**：
- 【整体车辆】：所有车型的数据（get_entrance_transactions, get_exit_transactions, get_gantry_transactions, get_all_transactions）
- 【货车专项】：仅货车数据（get_hourly_flow, get_avg_toll_fee, get_congestion_index等所有/api/analytics/truck/*）

**禁止行为示例**：
❌ 错误：同时调用get_exit_transactions（整体）+ get_hourly_flow（货车）
✓ 正确：只用货车专项API，或只用整体车辆API

**如何选择**：
- 用户明确提到"货车"、"卡车" → 只使用【货车专项】API
- 用户未指定车型或提到"车辆"、"收入" → 优先使用【整体车辆】API
- 如果两类API都无法满足，选择更接近用户需求的一类，但绝不混用

可用的API工具（每个步骤的tool必须从这里选择，并且你要仔细阅读其中的字段并理解）：
{tools_description}

**重要示例**：
用户需求："核算收入"
分析过程：
- 关键数据：收入、费用
- 查看返回字段：
  * get_exit_transactions → toll_money(通行费), real_money(实际费用) ✓ 包含费用字段
  * get_gantry_transactions → pay_fee(支付费用), fee(费用明细) ✓ 包含费用字段
  * get_revenue_statistics → total_revenue(总收入) ✓ 直接统计收入
- 决策：需要调用**get_exit_transactions + get_gantry_transactions**（或get_revenue_statistics如果只需总量）

你的任务是：
1. 理解用户的业务需求，提取数据关键词
2. 仔细查看下方API的"返回字段"
3. 选择返回字段与需求匹配的API
4. 生成结构化的执行计划

可用的API工具（每个步骤的tool必须从这里选择）：
{tools_description}

**重要：参数命名规范**
- 日期参数必须使用：start_date 和 end_date（格式：YYYY-MM-DD）
- 不要使用 date、time 等其他名称
- section_id：路段ID参数

**关键：日期范围处理**
- 如果用户提到"某一天"（如"1月3号"），end_date应该是**第二天**
- 正确示例：用户说"2023年1月3号" → start_date="2023-01-03", end_date="2023-01-04"
- 错误示例：start_date="2023-01-03", end_date="2023-01-03" ❌（查不到数据）
- 原因：数据库时间戳包含时分秒，需要包含整天的范围

输出格式（必须是有效的JSON）：
{{
    "task_understanding": "对用户需求的理解",
    "steps": [
        {{
            "step_number": 1,
            "description": "步骤描述",
            "tool": "API工具名称（必须从上面列表中选择）",
            "params": {{"参数名": "参数值"}},
            "purpose": "获取这个数据的目的"
        }}
    ],
    "expected_outcome": "Analyzer将基于获取的数据生成的结果"
}}

示例：
用户："核算2023-01-03的通行费"
正确：
- 步骤1: tool="get_exit_transactions", purpose="获取当天出口交易数据"
（Analyzer会自动计算总费用）

错误：
- 步骤1: 获取数据
- 步骤2: tool="计算总费用" ❌（不存在这个API）

用户需求: {user_query}

请生成执行计划（只规划API数据获取步骤）："""

    try:
        response = llm.invoke([SystemMessage(content=system_prompt)])
        content = response.content.strip()
        print(f"[DEBUG Planner] LLM返回内容:\n{content}\n")
        
        # 提取JSON
        if content.startswith('{'):
            plan = json.loads(content)
        else:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start < 0 or end <= start:
                raise ValueError(f"无法从LLM响应中提取JSON: {content[:200]}")
            json_str = content[start:end]
            print(f"[DEBUG Planner] 提取的JSON:\n{json_str}\n")
            plan = json.loads(json_str)
        
        if not plan.get('steps'):
            raise ValueError("LLM返回的计划中没有steps字段")
        
        state['plan'] = plan
        state['execution_logs'].append(f"[Planner] 生成执行计划: {plan.get('task_understanding', '')}")
        state['execution_logs'].append(f"[Planner] 计划包含 {len(plan.get('steps', []))} 个步骤")
        state['messages'].append(AIMessage(content=f"✓ 规划完成，共{len(plan.get('steps', []))}步"))
        state['next_agent'] = 'data_fetcher'
        
    except json.JSONDecodeError as je:
        error_msg = f"JSON解析失败: {str(je)}, 内容: {content[:200]}"
        print(f"[ERROR Planner] {error_msg}")
        state['error'] = error_msg
        state['execution_logs'].append(f"[Planner] {error_msg}")
        state['next_agent'] = 'end'
    except Exception as e:
        error_msg = f"规划失败: {type(e).__name__}: {str(e)}"
        print(f"[ERROR Planner] {error_msg}")
        state['error'] = error_msg
        state['execution_logs'].append(f"[Planner] {error_msg}")
        state['next_agent'] = 'end'
    
    return state


# ==================== Agent 2: DataFetcher（数据获取）====================

def data_fetcher_agent(state: MultiAgentState) -> MultiAgentState:
    """
    数据获取Agent：根据计划执行API调用，收集所需数据
    """
    plan = state.get('plan', {})
    steps = plan.get('steps', [])
    
    if not steps:
        state['error'] = "没有可执行的步骤"
        state['next_agent'] = 'end'
        return state
    
    state['execution_logs'].append(f"[DataFetcher] 开始执行 {len(steps)} 个API调用")
    
    for step in steps:
        step_num = step.get('step_number', 0)
        tool_name = step.get('tool', '')
        params = step.get('params', {}).copy()  # 复制参数以避免修改原始计划
        purpose = step.get('purpose', '')
        
        state['execution_logs'].append(f"[DataFetcher] 步骤{step_num}: {purpose}")
        
        # 解析参数中的依赖关系
        params = _resolve_param_dependencies(params, state['data_collected'])
        
        # 执行API调用（传递parent_trace_id用于审计）
        parent_trace_id = state.get('parent_trace_id')
        result = execute_api_call(tool_name, params, parent_trace_id=parent_trace_id)
        
        # 记录调用
        state['api_calls'].append({
            'step': step_num,
            'tool': tool_name,
            'params': params,
            'result': result,
            'success': result.get('success', False)
        })
        
        # 保存数据并进行预处理统计
        if result.get('success'):
            raw_data = result.get('data', [])
            count = len(raw_data)
            
            # 预处理：生成统计摘要，避免传递海量原始数据
            data_summary = _preprocess_data(raw_data, tool_name)
            
            state['data_collected'][f"step_{step_num}"] = {
                'count': count,
                'summary': data_summary,
                'sample': raw_data[:5] if raw_data else []  # 只保留5条样本
            }
            state['execution_logs'].append(f"[DataFetcher] ✓ 获取 {count} 条记录，已预处理")
        else:
            error_msg = result.get('error', '未知错误')
            state['execution_logs'].append(f"[DataFetcher] ✗ 失败: {error_msg}")
    
    state['messages'].append(AIMessage(content=f"✓ 数据获取完成，执行了{len(steps)}个API调用"))
    state['next_agent'] = 'analyzer'
    
    return state


# ==================== Agent 3: Analyzer（分析器）====================

def analyzer_agent(state: MultiAgentState) -> MultiAgentState:
    """
    分析器Agent：综合数据，生成洞察和最终结果
    """
    user_query = state['user_query']
    plan = state.get('plan', {})
    data_collected = state.get('data_collected', {})
    api_calls = state.get('api_calls', [])
    
    print(f"[DEBUG Analyzer] data_collected类型: {type(data_collected)}")
    print(f"[DEBUG Analyzer] data_collected keys: {list(data_collected.keys())}")
    
    # 构建数据摘要（适配新的数据结构）
    data_summary = {}
    for key, data_info in data_collected.items():
        if isinstance(data_info, dict):
            # 新格式：{'count': ..., 'summary': ..., 'sample': ...}
            data_summary[key] = {
                'count': data_info.get('count', 0),
                'statistics': data_info.get('summary', {}),
                'sample': data_info.get('sample', [])[:2]  # 只取2条样本
            }
        else:
            # 旧格式兼容
            data_summary[key] = {
                'count': len(data_info) if isinstance(data_info, list) else 0,
                'sample': data_info[0] if data_info else None
            }
    
    print(f"[DEBUG Analyzer] data_summary:\n{json.dumps(data_summary, indent=2, ensure_ascii=False)}\n")
    
    system_prompt = f"""你是一个高速公路数据分析专家。

用户需求: {user_query}

执行计划: {plan.get('task_understanding', '')}

收集到的数据摘要:
{json.dumps(data_summary, indent=2, ensure_ascii=False)}

请分析数据并生成最终结果。输出格式（必须是有效的JSON）：
{{
    "summary": "整体摘要",
    "key_findings": ["关键发现1", "关键发现2", ...],
    "statistics": {{"统计指标名": 值}},
    "recommendations": ["建议1", "建议2", ...]
}}

请生成分析结果："""

    try:
        response = llm.invoke([SystemMessage(content=system_prompt)])
        content = response.content.strip()
        print(f"[DEBUG Analyzer] LLM返回:\n{content}\n")
        
        # 提取JSON
        if content.startswith('{'):
            analysis = json.loads(content)
        else:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start < 0 or end <= start:
                raise ValueError(f"无法提取JSON: {content[:200]}")
            analysis = json.loads(content[start:end])
        
        # 收集详细数据记录
        detailed_data = {}
        for key, data_info in data_collected.items():
            if isinstance(data_info, dict) and 'sample' in data_info:
                detailed_data[key] = {
                    'count': data_info.get('count', 0),
                    'records': data_info.get('sample', [])  # 包含具体记录
                }
        
        state['analysis_result'] = {
            'summary': analysis.get('summary', ''),
            'key_findings': analysis.get('key_findings', []),
            'statistics': analysis.get('statistics', {}),
            'recommendations': analysis.get('recommendations', []),
            'data_summary': data_summary,
            'detailed_data': detailed_data,  # 添加详细数据
            'api_calls': api_calls
        }
        
        state['execution_logs'].append(f"[Analyzer] 分析完成: {analysis.get('summary', '')}")
        state['messages'].append(AIMessage(content=f"✓ 分析完成，生成了{len(analysis.get('key_findings', []))}个关键发现"))
        state['next_agent'] = 'end'
        
    except Exception as e:
        error_msg = f"分析失败: {type(e).__name__}: {str(e)}"
        print(f"[ERROR Analyzer] {error_msg}")
        state['error'] = error_msg
        state['execution_logs'].append(f"[Analyzer] {error_msg}")
        state['next_agent'] = 'end'
    
    return state


# ==================== 路由决策 ====================

def should_continue(state: MultiAgentState) -> str:
    """决定下一个执行的节点"""
    next_agent = state.get('next_agent', 'end')
    
    if state.get('error'):
        return 'end'
    
    return next_agent


# ==================== 构建LangGraph ====================

def build_multi_agent_graph():
    """构建多智能体协作图"""
    workflow = StateGraph(MultiAgentState)
    
    # 添加三个Agent节点
    workflow.add_node("planner", planner_agent)
    workflow.add_node("data_fetcher", data_fetcher_agent)
    workflow.add_node("analyzer", analyzer_agent)
    
    # 设置入口
    workflow.set_entry_point("planner")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "planner",
        should_continue,
        {
            "data_fetcher": "data_fetcher",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "data_fetcher",
        should_continue,
        {
            "analyzer": "analyzer",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "analyzer",
        should_continue,
        {
            "end": END
        }
    )
    
    return workflow.compile()


# ==================== 多智能体执行器 ====================

class MultiAgentExecutor:
    """多智能体协作执行器"""
    
    def __init__(self):
        self.graph = build_multi_agent_graph()
    
    def execute(self, user_query: str, parent_trace_id: str = None) -> Dict[str, Any]:
        """执行多智能体协作任务
        
        Args:
            user_query: 用户查询
            parent_trace_id: 父级追踪ID，用于关联调用链
        """
        
        # 初始化状态
        initial_state = {
            'messages': [HumanMessage(content=user_query)],
            'user_query': user_query,
            'plan': {},
            'api_calls': [],
            'data_collected': {},
            'analysis_result': {},
            'execution_logs': [],
            'error': '',
            'next_agent': 'planner',
            'parent_trace_id': parent_trace_id  # 传递追踪ID
        }
        
        print(f"\n{'='*60}")
        print(f"[多智能体系统] 开始处理: {user_query}")
        print(f"{'='*60}\n")
        
        try:
            # 执行协作流程
            final_state = self.graph.invoke(initial_state)
            
            # 构建返回结果
            return {
                'success': not final_state.get('error'),
                'query': user_query,
                'plan': final_state.get('plan', {}),
                'result': final_state.get('analysis_result', {}),
                'execution_logs': final_state.get('execution_logs', []),
                'api_calls': final_state.get('api_calls', []),
                'error': final_state.get('error', '')
            }
        
        except Exception as e:
            return {
                'success': False,
                'query': user_query,
                'error': f'多智能体执行失败: {str(e)}',
                'execution_logs': [f'系统错误: {str(e)}']
            }


# 全局实例
multi_agent_executor = MultiAgentExecutor()


if __name__ == '__main__':
    # 测试用例
    test_queries = [
        "帮我核算2023年1月3号的通行费用",
        "检测最近的异常交易",
        "分析全网的流量情况",
        "统计各个路段的拥堵情况"
    ]
    
    for query in test_queries:
        result = multi_agent_executor.execute(query)
        print(f"\n查询: {query}")
        print(f"成功: {result['success']}")
        print(f"执行日志: {json.dumps(result['execution_logs'], indent=2, ensure_ascii=False)}")
        if result.get('result'):
            print(f"分析结果: {json.dumps(result['result']['summary'], indent=2, ensure_ascii=False)}")
        print("\n" + "="*60 + "\n")