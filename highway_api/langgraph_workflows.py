"""
LangGraph服务编排 - 跨主体业务场景实现
支持3个核心业务场景的服务融合
"""
import requests
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import json
from datetime import datetime

# API基础配置
API_BASE_URL = "http://localhost:5000"


class WorkflowState(TypedDict):
    """工作流状态定义"""
    messages: Sequence[BaseMessage]
    input_params: dict
    api_results: dict
    final_result: dict
    error: str


# ==================== 场景1: 跨路段通行费核算 ====================

def scenario1_get_entrance(state: WorkflowState) -> WorkflowState:
    """节点1: 获取入口交易记录"""
    params = state['input_params']
    vehicle_id = params.get('vehicle_id', '')
    start_date = params.get('start_date', '2023-01-03')
    end_date = params.get('end_date')
    section_id = params.get('section_id')
    section_name = params.get('section_name')
    
    # 如果没有指定结束日期，默认为开始日期第二天（查询单天）
    from datetime import datetime, timedelta
    if not end_date:
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[场景1-入口] 参数: start_date={start_date}, end_date={end_date}, section_id={section_id}, section_name={section_name}")
    
    try:
        api_params = {
            'start_date': start_date,
            'end_date': end_date
        }
        if section_id:
            api_params['section_id'] = section_id
        
        response = requests.get(
            f"{API_BASE_URL}/api/transactions/entrance",
            params=api_params,
            timeout=30  # 增加超时时间，因为可能返回大量数据
        )
        data = response.json()
        
        # 详细日志
        print(f"[场景1-入口] API返回: success={data.get('success')}, count={data.get('count', 0)}")
        if data.get('count', 0) > 0:
            print(f"[场景1-入口] 第一条数据: {data.get('data', [])[0] if data.get('data') else 'None'}")
        
        state['api_results']['entrance'] = data
        state['messages'].append(AIMessage(
            content=f"✓ 获取入口交易记录成功: {data.get('count', 0)}条"
        ))
    except Exception as e:
        state['error'] = f"入口交易查询失败: {str(e)}"
        state['messages'].append(AIMessage(content=f"✗ {state['error']}"))
    
    return state


def scenario1_get_exit(state: WorkflowState) -> WorkflowState:
    """节点2: 获取出口交易记录"""
    params = state['input_params']
    start_date = params.get('start_date', '2023-01-03')
    end_date = params.get('end_date')
    section_id = params.get('section_id')
    
    # 如果没有指定结束日期，默认为开始日期第二天（查询单天）
    from datetime import datetime, timedelta
    if not end_date:
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[场景1-出口] 参数: start_date={start_date}, end_date={end_date}, section_id={section_id}")
    
    try:
        api_params = {
            'start_date': start_date,
            'end_date': end_date
        }
        if section_id:
            api_params['section_id'] = section_id
        
        response = requests.get(
            f"{API_BASE_URL}/api/transactions/exit",
            params=api_params,
            timeout=30  # 增加超时时间，因为可能返回大量数据
        )
        data = response.json()
        
        # 详细日志
        print(f"[场景1-出口] API返回: success={data.get('success')}, count={data.get('count', 0)}")
        if data.get('count', 0) > 0:
            first_item = data.get('data', [])[0] if data.get('data') else {}
            print(f"[场景1-出口] 第一条数据金额: toll_money={first_item.get('toll_money')}, real_money={first_item.get('real_money')}")
        else:
            print(f"[场景1-出口] ⚠️ 数据库中该日期没有数据！")
        
        state['api_results']['exit'] = data
        state['messages'].append(AIMessage(
            content=f"✓ 获取出口交易记录成功: {data.get('count', 0)}条"
        ))
    except Exception as e:
        state['error'] = f"出口交易查询失败: {str(e)}"
        state['messages'].append(AIMessage(content=f"✗ {state['error']}"))
    
    return state


def scenario1_get_gantry(state: WorkflowState) -> WorkflowState:
    """节点3: 获取门架交易记录"""
    params = state['input_params']
    start_date = params.get('start_date', '2023-01-03')
    end_date = params.get('end_date')
    section_id = params.get('section_id')
    
    # 如果没有指定结束日期，默认为开始日期第二天（查询单天）
    from datetime import datetime, timedelta
    if not end_date:
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[场景1-门架] 参数: start_date={start_date}, end_date={end_date}, section_id={section_id}")
    
    try:
        api_params = {
            'start_date': start_date,
            'end_date': end_date
        }
        if section_id:
            api_params['section_id'] = section_id
        
        response = requests.get(
            f"{API_BASE_URL}/api/transactions/gantry",
            params=api_params,
            timeout=30
        )
        data = response.json()
        
        # 详细日志
        print(f"[场景1-门架] API返回: success={data.get('success')}, count={data.get('count', 0)}")
        if data.get('count', 0) > 0:
            first_item = data.get('data', [])[0] if data.get('data') else {}
            print(f"[场景1-门架] 第一条数据金额: pay_fee={first_item.get('pay_fee')}, fee={first_item.get('fee')}")
        else:
            print(f"[场景1-门架] ⚠️ 数据库中该日期没有门架数据")
        
        state['api_results']['gantry'] = data
        state['messages'].append(AIMessage(
            content=f"✓ 获取门架交易记录成功: {data.get('count', 0)}条"
        ))
    except Exception as e:
        state['error'] = f"门架交易查询失败: {str(e)}"
        state['messages'].append(AIMessage(content=f"✗ {state['error']}"))
    
    return state


def scenario1_calculate_fee(state: WorkflowState) -> WorkflowState:
    """节点4: 计算费用并核算（包含门架费用）"""
    entrance_data = state['api_results'].get('entrance', {}).get('data', [])
    exit_data = state['api_results'].get('exit', {}).get('data', [])
    gantry_data = state['api_results'].get('gantry', {}).get('data', [])
    
    print(f"[场景1-计算] 入口数据: {len(entrance_data)}条, 出口数据: {len(exit_data)}条, 门架数据: {len(gantry_data)}条")
    
    # 出口费用统计
    exit_toll = sum(float(item.get('toll_money', 0) or 0) for item in exit_data)
    exit_real = sum(float(item.get('real_money', 0) or 0) for item in exit_data)
    
    # 门架费用统计（门架交易使用pay_fee字段，单位是分，需要转换为元）
    gantry_toll = sum(float(item.get('pay_fee', 0) or 0) / 100 for item in gantry_data)
    
    # 总费用 = 出口费用 + 门架费用
    total_toll = exit_toll + gantry_toll
    total_real = exit_real  # 实收只看出口（门架是分段计费）
    total_transactions = len(exit_data) + len(gantry_data)
    
    print(f"[场景1-计算] 出口应收: {exit_toll}元, 门架应收: {gantry_toll}元")
    print(f"[场景1-计算] 总应收: {total_toll}元, 总实收: {total_real}元")
    
    result = {
        'scenario': '跨路段通行费核算',
        'entrance_count': len(entrance_data),
        'exit_count': len(exit_data),
        'gantry_count': len(gantry_data),
        'total_toll_money': round(total_toll, 2),
        'total_real_money': round(total_real, 2),
        'exit_toll_money': round(exit_toll, 2),
        'gantry_toll_money': round(gantry_toll, 2),
        'discount_amount': round(total_toll - total_real, 2),
        'average_fee': round(total_real / len(exit_data), 2) if len(exit_data) > 0 else 0,
        'total_transactions': total_transactions,
        'timestamp': datetime.now().isoformat()
    }
    
    state['final_result'] = result
    state['messages'].append(AIMessage(
        content=f"✓ 费用核算完成: 总计{total_transactions}笔交易（出口{len(exit_data)}+门架{len(gantry_data)}），总应收{result['total_toll_money']}元，实收{result['total_real_money']}元"
    ))
    
    return state


def build_scenario1_workflow():
    """构建场景1工作流（包含门架数据）"""
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("get_entrance", scenario1_get_entrance)
    workflow.add_node("get_exit", scenario1_get_exit)
    workflow.add_node("get_gantry", scenario1_get_gantry)
    workflow.add_node("calculate_fee", scenario1_calculate_fee)
    
    workflow.set_entry_point("get_entrance")
    workflow.add_edge("get_entrance", "get_exit")
    workflow.add_edge("get_exit", "get_gantry")
    workflow.add_edge("get_gantry", "calculate_fee")
    workflow.add_edge("calculate_fee", END)
    
    return workflow.compile()


# ==================== 场景2: 异常交易稽核 ====================

def scenario2_get_real_transactions(state: WorkflowState) -> WorkflowState:
    """节点1: 获取真实交易数据"""
    params = state['input_params']
    start_date = params.get('start_date', '2023-01-03')
    end_date = params.get('end_date')
    limit = params.get('limit', 20)
    
    # 如果没有指定结束日期，默认为开始日期第二天（查询单天）
    from datetime import datetime, timedelta
    if not end_date:
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[场景2-交易] 使用日期参数: start_date={start_date}, end_date={end_date}, limit={limit}")
    
    try:
        api_params = {
            'start_date': start_date,
            'end_date': end_date
        }
        if limit:
            api_params['limit'] = limit
            
        response = requests.get(
            f"{API_BASE_URL}/api/transactions/exit",
            params=api_params,
            timeout=30
        )
        data = response.json()
        
        state['api_results']['real_transactions'] = data
        state['messages'].append(AIMessage(
            content=f"✓ 获取真实交易数据: {data.get('count', 0)}条"
        ))
    except Exception as e:
        state['error'] = f"真实交易查询失败: {str(e)}"
        state['messages'].append(AIMessage(content=f"✗ {state['error']}"))
    
    return state


def scenario2_get_truck_stats(state: WorkflowState) -> WorkflowState:
    """节点2: 获取货车统计数据用于对比"""
    params = state['input_params']
    start_date = params.get('start_date', '2023-01-03')
    end_date = params.get('end_date')
    
    # 如果没有指定结束日期，默认为开始日期第二天（查询单天）
    from datetime import datetime, timedelta
    if not end_date:
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[场景2-统计] 使用日期参数: start_date={start_date}, end_date={end_date}")
    
    try:
        # 调用货车平均通行时间API
        response = requests.get(
            f"{API_BASE_URL}/api/analytics/truck/avg-travel-time",
            params={'start_date': start_date, 'end_date': end_date},
            timeout=30
        )
        travel_time_data = response.json()
        
        # 调用货车平均通行费API
        response2 = requests.get(
            f"{API_BASE_URL}/api/analytics/truck/avg-toll-fee",
            params={'start_date': start_date, 'end_date': end_date},
            timeout=30
        )
        toll_fee_data = response2.json()
        
        state['api_results']['truck_stats'] = {
            'travel_time': travel_time_data.get('data', []),
            'toll_fee': toll_fee_data.get('data', [])
        }
        state['messages'].append(AIMessage(
            content=f"✓ 获取货车统计数据成功"
        ))
    except Exception as e:
        state['error'] = f"货车统计数据查询失败: {str(e)}"
        state['messages'].append(AIMessage(content=f"⚠ {state['error']}"))
    
    return state


def scenario2_detect_anomalies(state: WorkflowState) -> WorkflowState:
    """节点3: 检测异常交易"""
    real_data = state['api_results'].get('real_transactions', {}).get('data', [])
    
    # 简单的异常检测逻辑（基于费用统计）
    if not real_data:
        state['final_result'] = {
            'scenario': '异常交易稽核',
            'anomalies': [],
            'total_checked': 0,
            'anomaly_rate': 0
        }
        return state
    
    fees = [float(item.get('real_money', 0) or 0) for item in real_data]
    avg_fee = sum(fees) / len(fees)
    std_fee = (sum((f - avg_fee) ** 2 for f in fees) / len(fees)) ** 0.5
    
    # 检测超过2个标准差的交易
    anomalies = []
    for item in real_data:
        fee = float(item.get('real_money', 0) or 0)
        if abs(fee - avg_fee) > 2 * std_fee:
            anomalies.append({
                'transaction_id': item.get('exit_transaction_id', ''),
                'fee': fee,
                'deviation': abs(fee - avg_fee),
                'reason': '费用异常'
            })
    
    result = {
        'scenario': '异常交易稽核',
        'total_checked': len(real_data),
        'anomaly_count': len(anomalies),
        'anomaly_rate': round(len(anomalies) / len(real_data) * 100, 2),
        'anomalies': anomalies[:5],  # 只返回前5条
        'statistics': {
            'avg_fee': round(avg_fee, 2),
            'std_fee': round(std_fee, 2),
            'threshold': round(2 * std_fee, 2)
        },
        'timestamp': datetime.now().isoformat()
    }
    
    state['final_result'] = result
    state['messages'].append(AIMessage(
        content=f"✓ 异常检测完成: 检查{result['total_checked']}笔，发现{result['anomaly_count']}笔异常"
    ))
    
    return state


def build_scenario2_workflow():
    """构建场景2工作流"""
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("get_real_transactions", scenario2_get_real_transactions)
    workflow.add_node("get_truck_stats", scenario2_get_truck_stats)
    workflow.add_node("detect_anomalies", scenario2_detect_anomalies)
    
    workflow.set_entry_point("get_real_transactions")
    workflow.add_edge("get_real_transactions", "get_truck_stats")
    workflow.add_edge("get_truck_stats", "detect_anomalies")
    workflow.add_edge("detect_anomalies", END)
    
    return workflow.compile()


# ==================== 场景3: 全网流量分析 ====================

def scenario3_get_sections(state: WorkflowState) -> WorkflowState:
    """节点1: 获取所有路段"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/sections",
            timeout=10
        )
        data = response.json()
        
        state['api_results']['sections'] = data
        state['messages'].append(AIMessage(
            content=f"✓ 获取路段信息: {data.get('count', 0)}个路段"
        ))
    except Exception as e:
        state['error'] = f"路段查询失败: {str(e)}"
        state['messages'].append(AIMessage(content=f"✗ {state['error']}"))
    
    return state


def scenario3_get_traffic_stats(state: WorkflowState) -> WorkflowState:
    """节点2: 获取各路段流量统计"""
    params = state['input_params']
    start_date = params.get('start_date', '2023-01-03')
    end_date = params.get('end_date', '2023-01-10')
    
    sections = state['api_results'].get('sections', {}).get('data', [])
    
    traffic_stats = []
    # 优先查询有数据的路段
    priority_sections = [s for s in sections if s.get('section_id') == 'G5615530120']
    other_sections = [s for s in sections if s.get('section_id') != 'G5615530120']
    query_sections = (priority_sections + other_sections)[:3]
    
    for section in query_sections:
        section_id = section.get('section_id')
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/statistics/traffic-flow",
                params={
                    'section_id': section_id,
                    'start_date': start_date,
                    'end_date': end_date
                },
                timeout=10
            )
            data = response.json()
            traffic_stats.append({
                'section_id': section_id,
                'section_name': section.get('section_name', ''),
                'data': data.get('data', [])
            })
        except Exception as e:
            state['messages'].append(AIMessage(
                content=f"⚠ 路段{section_id}流量查询失败: {str(e)}"
            ))
    
    state['api_results']['traffic_stats'] = traffic_stats
    state['messages'].append(AIMessage(
        content=f"✓ 获取流量统计: {len(traffic_stats)}个路段"
    ))
    
    return state


def scenario3_analyze_traffic(state: WorkflowState) -> WorkflowState:
    """节点3: 分析流量数据"""
    traffic_stats = state['api_results'].get('traffic_stats', [])
    
    # 聚合分析
    total_flow = 0
    section_summary = []
    
    for section_stat in traffic_stats:
        section_id = section_stat['section_id']
        section_name = section_stat['section_name']
        data = section_stat['data']
        
        section_total = sum(item.get('count', 0) for item in data)
        total_flow += section_total
        
        section_summary.append({
            'section_id': section_id,
            'section_name': section_name,
            'total_flow': section_total,
            'daily_avg': round(section_total / len(data), 2) if data else 0
        })
    
    # 排序
    section_summary.sort(key=lambda x: x['total_flow'], reverse=True)
    
    result = {
        'scenario': '全网流量分析',
        'total_sections': len(traffic_stats),
        'total_flow': total_flow,
        'busiest_section': section_summary[0] if section_summary else None,
        'section_summary': section_summary,
        'timestamp': datetime.now().isoformat()
    }
    
    state['final_result'] = result
    state['messages'].append(AIMessage(
        content=f"✓ 流量分析完成: 总流量{total_flow}次，最繁忙路段{result['busiest_section']['section_name'] if result['busiest_section'] else 'N/A'}"
    ))
    
    return state


def build_scenario3_workflow():
    """构建场景3工作流"""
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("get_sections", scenario3_get_sections)
    workflow.add_node("get_traffic_stats", scenario3_get_traffic_stats)
    workflow.add_node("analyze_traffic", scenario3_analyze_traffic)
    
    workflow.set_entry_point("get_sections")
    workflow.add_edge("get_sections", "get_traffic_stats")
    workflow.add_edge("get_traffic_stats", "analyze_traffic")
    workflow.add_edge("analyze_traffic", END)
    
    return workflow.compile()


# ==================== 工作流执行器 ====================

class WorkflowExecutor:
    """工作流执行器"""
    
    def __init__(self):
        self.workflows = {
            'scenario1': build_scenario1_workflow(),
            'scenario2': build_scenario2_workflow(),
            'scenario3': build_scenario3_workflow()
        }
    
    def execute(self, scenario: str, input_params: dict) -> dict:
        """执行指定场景的工作流"""
        if scenario not in self.workflows:
            return {
                'success': False,
                'error': f'未知场景: {scenario}，可用场景: {list(self.workflows.keys())}'
            }
        
        workflow = self.workflows[scenario]
        
        # 初始化状态
        initial_state = {
            'messages': [HumanMessage(content=f"开始执行场景: {scenario}")],
            'input_params': input_params,
            'api_results': {},
            'final_result': {},
            'error': ''
        }
        
        try:
            # 执行工作流
            final_state = workflow.invoke(initial_state)
            
            # 构建响应
            return {
                'success': True,
                'scenario': scenario,
                'result': final_state['final_result'],
                'logs': [msg.content for msg in final_state['messages']],
                'error': final_state.get('error', '')
            }
        except Exception as e:
            return {
                'success': False,
                'scenario': scenario,
                'error': f'工作流执行失败: {str(e)}'
            }
    
    def get_scenario_info(self, scenario: str) -> dict:
        """获取场景信息"""
        scenario_descriptions = {
            'scenario1': {
                'name': '跨路段通行费核算',
                'description': '查询入口和出口交易记录，计算通行费用并进行核算',
                'apis': [
                    'GET /api/transactions/entrance',
                    'GET /api/transactions/exit'
                ],
                'params': {
                    'start_date': '开始日期 (YYYY-MM-DD)',
                    'vehicle_id': '车牌号 (可选)'
                }
            },
            'scenario2': {
                'name': '异常交易稽核',
                'description': '获取真实交易数据，结合货车统计信息，检测异常交易',
                'apis': [
                    'GET /api/transactions/exit',
                    'GET /api/analytics/truck/avg-travel-time',
                    'GET /api/analytics/truck/avg-toll-fee'
                ],
                'params': {
                    'limit': '查询数量',
                    'start_date': '开始日期 (YYYY-MM-DD)'
                }
            },
            'scenario3': {
                'name': '全网流量分析',
                'description': '获取所有路段信息，统计各路段流量，进行聚合分析',
                'apis': [
                    'GET /api/sections',
                    'GET /api/statistics/traffic-flow'
                ],
                'params': {
                    'start_date': '开始日期 (YYYY-MM-DD)',
                    'end_date': '结束日期 (YYYY-MM-DD)'
                }
            }
        }
        
        return scenario_descriptions.get(scenario, {})


# 创建全局执行器实例
workflow_executor = WorkflowExecutor()


if __name__ == '__main__':
    # 测试场景1
    print("测试场景1: 跨路段通行费核算")
    result1 = workflow_executor.execute('scenario1', {
        'start_date': '2023-01-03'
    })
    print(json.dumps(result1, indent=2, ensure_ascii=False))
    
    print("\n" + "="*50 + "\n")
    
    # 测试场景2
    print("测试场景2: 异常交易稽核")
    result2 = workflow_executor.execute('scenario2', {
        'start_date': '2023-01-03',
        'limit': 20,
        'synthetic_count': 10
    })
    print(json.dumps(result2, indent=2, ensure_ascii=False))
    
    print("\n" + "="*50 + "\n")
    
    # 测试场景3
    print("测试场景3: 全网流量分析")
    result3 = workflow_executor.execute('scenario3', {
        'start_date': '2023-01-03',
        'end_date': '2023-01-10'
    })
    print(json.dumps(result3, indent=2, ensure_ascii=False))
