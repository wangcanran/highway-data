"""
统一智能Agent - 支持API推荐和LangGraph工作流自动调用
整合原有API推荐Agent和工作流编排Agent的能力
"""
import json
from typing import Dict, Any, List
from openai import OpenAI
import config
from langgraph_workflows import workflow_executor


class EnhancedAgent:
    """统一智能Agent - API推荐 + 工作流编排"""
    
    def __init__(self):
        """初始化统一Agent"""
        self.openai_client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_API_BASE
        )
        self.model_name = config.FIXED_MODEL_NAME
        self.request_timeout = config.REQUEST_TIMEOUT
        
        # 货车分析API标签知识库
        self.api_tags = self._init_api_knowledge()
    
    def _init_api_knowledge(self) -> List[Dict[str, Any]]:
        """初始化货车分析API知识库"""
        return [
            {
                'tag': 'hourly-flow',
                'name': '小时流量',
                'endpoint': '/api/analytics/truck/hourly-flow',
                'description': '统计每个路段每小时通过的货车数量',
                'keywords': ['流量', '小时', '趋势', '高峰', '监测']
            },
            {
                'tag': 'avg-travel-time',
                'name': '平均通行时间',
                'endpoint': '/api/analytics/truck/avg-travel-time',
                'description': '统计货车的平均通行时间（分钟）',
                'keywords': ['时间', '效率', '拥堵', '时效', '速度']
            },
            {
                'tag': 'avg-toll-fee',
                'name': '平均通行费',
                'endpoint': '/api/analytics/truck/avg-toll-fee',
                'description': '统计货车的平均通行费用（元）',
                'keywords': ['费用', '成本', '收费', '价格', '通行费']
            },
            {
                'tag': 'congestion-index',
                'name': '拥堵指数',
                'endpoint': '/api/analytics/truck/congestion-index',
                'description': '通过货车流量与车道数比值评估拥堵程度',
                'keywords': ['拥堵', '路况', '交通', '堵塞', '指数']
            },
            {
                'tag': 'overweight-rate',
                'name': '超载比例',
                'endpoint': '/api/analytics/truck/overweight-rate',
                'description': '统计超载货车的比例（数据脱敏）',
                'keywords': ['超载', '超重', '合规', '违规', '监管']
            },
            {
                'tag': 'discount-rate',
                'name': '优惠比例',
                'endpoint': '/api/analytics/truck/discount-rate',
                'description': '统计享受通行费优惠的货车比例',
                'keywords': ['优惠', '折扣', '减免', '政策']
            },
            {
                'tag': 'peak-hours',
                'name': '高峰时段',
                'endpoint': '/api/analytics/truck/peak-hours',
                'description': '识别货车流量最高的小时区间',
                'keywords': ['高峰', '繁忙', '时段', '高流量']
            },
            {
                'tag': 'avg-axle-count',
                'name': '平均轴数',
                'endpoint': '/api/analytics/truck/avg-axle-count',
                'description': '统计货车的平均轴数',
                'keywords': ['轴数', '车型', '类型', '结构']
            },
            {
                'tag': 'lane-utilization',
                'name': '车道利用率',
                'endpoint': '/api/analytics/truck/lane-utilization',
                'description': '统计货车流量与车道数的比值',
                'keywords': ['车道', '利用率', '容量', '资源']
            },
            {
                'tag': 'exit-hourly-flow',
                'name': '出口小时流量',
                'endpoint': '/api/analytics/truck/exit-hourly-flow',
                'description': '统计每个路段每小时出口的货车数量',
                'keywords': ['出口', '流量', '出站']
            },
            {
                'tag': 'exit-hourly-flow-k-anonymized',
                'name': '出口数据k匿名',
                'endpoint': '/api/analytics/truck/exit-hourly-flow-k-anonymized',
                'description': '基于KACA算法的k-匿名隐私保护出口数据',
                'keywords': ['k匿名', '隐私', '脱敏', 'KACA', '匿名化']
            }
        ]
    
    def process_query(self, user_query: str, base_url: str = "http://localhost:5000") -> Dict[str, Any]:
        """
        处理用户查询，自动决策是直接调用API还是使用LangGraph工作流
        
        Args:
            user_query: 用户的自然语言查询
            base_url: API基础URL
            
        Returns:
            包含处理结果的字典
        """
        # Step 1: 使用LLM分析用户需求
        analysis = self._analyze_query(user_query)
        
        if not analysis['success']:
            return {
                'success': False,
                'error': analysis['error'],
                'query': user_query
            }
        
        query_type = analysis['query_type']
        scenario = analysis.get('scenario')
        
        # Step 2: 根据查询类型决策
        if query_type == 'workflow' and scenario:
            # 需要使用LangGraph工作流
            return self._execute_workflow(scenario, analysis.get('params', {}), user_query)
        elif query_type == 'api':
            # API推荐模式
            return self._recommend_api(user_query, analysis, base_url)
        else:
            # 无法识别的查询类型
            return {
                'success': False,
                'query': user_query,
                'execution_type': 'unknown',
                'error': '无法识别查询意图',
                'reason': analysis.get('reason', ''),
                'suggestion': '请更明确地描述您的需求，例如："分析货车流量"或"核算通行费"'
            }
    
    def _analyze_query(self, user_query: str) -> Dict[str, Any]:
        """使用LLM分析用户查询意图"""
        
        system_prompt = """你是一个高速公路数据服务的智能分析助手。

你的任务是分析用户查询，判断需要：
1. API推荐（query_type: "api"）- 货车数据分析查询（流量、费用、拥堵等单一维度分析）
2. 工作流编排（query_type: "workflow"）- 需要多步骤、跨主体的复杂业务场景（核算、稽核、全网分析）

=== 货车分析API（11个）===
- 小时流量：统计每小时货车通行量
- 平均通行时间：评估通行效率
- 平均通行费：分析费用水平
- 拥堵指数：评估拥堵程度
- 超载比例：合规监管（数据脱敏）
- 优惠比例：政策效果分析
- 高峰时段：识别繁忙时段
- 平均轴数：车型分布分析
- 车道利用率：资源利用评估
- 出口小时流量：出口流量统计
- k匿名数据：隐私保护版本

关键词：流量、拥堵、费用、时间、超载、优惠、高峰、轴数、车道、k匿名、隐私

=== 工作流场景（3个）===

【场景1: 跨路段通行费核算】scenario1
- 业务目标: 计算车辆跨路段通行的费用，进行结算和对账
- 涉及主体: 入口收费站、出口收费站、结算中心
- 执行步骤: 查询入口交易 → 查询出口交易 → 计算费用差异和优惠
- 用户需求示例: 
  * "帮我核算通行费"
  * "计算收费金额"
  * "费用结算"
  * "通行费用统计"
  * "收费对账"
- 关键词: 核算、通行费、费用、结算、对账、收费、计算金额

【场景2: 异常交易稽核】scenario2
- 业务目标: 检测异常交易，识别费用异常、时间异常等问题
- 涉及主体: 监管部门、收费站、统计分析中心
- 执行步骤: 获取交易数据 → 获取货车统计数据 → 基于统计方法检测异常
- 用户需求示例:
  * "检测异常交易"
  * "稽核交易记录"
  * "查找异常"
  * "监测问题交易"
  * "审查交易数据"
- 关键词: 异常、稽核、检测、监测、审查、问题、异常值

【场景3: 全网流量分析】scenario3
- 业务目标: 统计整个路网的交通流量，识别繁忙路段，进行宏观分析
- 涉及主体: 路网运营中心、各路段管理处、调度中心
- 执行步骤: 获取所有路段 → 逐路段统计流量 → 聚合分析排名
- 用户需求示例:
  * "分析全网流量"
  * "统计所有路段的车流量"
  * "整体交通分析"
  * "查看各路段流量情况"
  * "全路网统计"
- 关键词: 全网、整体、所有路段、路网、全路段、流量分析、车流量统计

=== 匹配规则 ===
1. 优先匹配工作流场景（核算、稽核、全网分析）
2. 如果是货车数据分析（流量、拥堵、费用等），匹配API推荐
3. API推荐适用于单一维度的统计分析
4. 工作流适用于多步骤、跨主体的业务流程

示例：
- "分析货车流量" → api（单一维度统计）
- "查看拥堵情况" → api（单一维度统计）
- "核算通行费" → workflow + scenario1（多步骤计算）
- "检测异常交易" → workflow + scenario2（多步骤检测）
- "分析全网流量" → workflow + scenario3（跨路段聚合）

请以JSON格式返回：
{
    "success": true,
    "query_type": "api" | "workflow",
    "scenario": "scenario1" | "scenario2" | "scenario3" | null,
    "recommended_apis": ["api_tag1", "api_tag2"],
    "params": {
        "start_date": "YYYY-MM-DD格式，从用户查询中提取，如'2023-11-15'",
        "end_date": "YYYY-MM-DD格式，如果用户提到结束日期（可选）",
        "section_id": "路段ID，如'G5615530120'（可选）",
        "section_name": "路段名称，如'麻文高速'（可选）",
        "limit": "数字，如果用户提到查询数量（可选）"
    },
    "reason": "匹配原因"
}

参数提取规则（重要）：
1. 日期识别与转换：
   - 识别具体日期："2023年1月3号"、"1月3日" → "2023-01-03"
   - 识别月份："2023年1月"、"1月份" → start_date="2023-01-01", end_date="2023-02-01"（整月）
   - 识别日期范围："1月3号到10号"、"1月3日至1月10日" → start_date="2023-01-03", end_date="2023-01-10"
   - 识别周/天数："最近7天"、"上周" → 计算对应的日期范围
   
2. 默认值设置：
   - 如果没有指定任何日期，scenario1/2使用"2023-01-03"，scenario3使用"2023-01-03"到"2023-01-10"
   - 如果只有开始日期没有结束日期，工作流会默认查询单天
   
3. 路段识别：
   - 识别路段名称："麻文高速"、"麻文路段" → section_name="麻文高速", section_id="G5615530120"
   - 识别路段ID："G5615530120" → section_id="G5615530120"
   - 支持的路段映射：
     * 麻文高速 → G5615530120（数据日期：2023-01-03）
     * 都香高速 → G7611530010（数据日期：2023-02-01）
     * 彝良至昭通高速 → S0010530010（数据日期：2023-02-20~21）
     * 彝良至镇雄高速公路 → S0010530020（数据日期：2023-03-08~09）
     * 宜宾至毕节高速威信至镇雄段 → S0014530010（数据日期：2023-03-15~16）
     * 青龙咎至水田新区高速 → S0014530020（数据日期：2023-03-22~23）
     * 大关至永善高速 → S0014530030（数据日期：2023-12-22~23）
     * 昭阳西环高速公路 → S0071530020（数据日期：2023-02-08~09）

4. 其他参数：
   - 提取数量相关的参数到limit字段（如"查询100条"、"检测50笔交易"）

示例：
- "核算1月的通行费" → start_date="2023-01-01", end_date="2023-02-01"
- "核算麻文高速1月3号的通行费" → section_name="麻文高速", section_id="G5615530120", start_date="2023-01-03"
- "检测彝良至昭通高速的异常" → section_name="彝良至昭通高速", section_id="S0010530010", start_date="2023-02-20", end_date="2023-02-21"
- "分析麻文路段" → section_name="麻文高速", section_id="G5615530120", start_date="2023-01-03"（使用该路段的数据日期）
"""
        
        user_message = f"用户查询：{user_query}"
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                timeout=self.request_timeout
            )
            
            content = response.choices[0].message.content.strip()
            
            # 提取JSON
            json_match = json.loads(content) if content.startswith('{') else json.loads(
                content[content.find('{'):content.rfind('}')+1]
            )
            
            return json_match
            
        except Exception as e:
            return {
                'success': False,
                'error': f'LLM分析失败: {str(e)}',
                'query_type': 'simple'
            }
    
    def _recommend_api(self, user_query: str, analysis: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        """推荐合适的API"""
        recommended_tags = analysis.get('recommended_apis', [])
        params = analysis.get('params', {})
        
        # 如果LLM没有推荐API，基于关键词匹配
        if not recommended_tags:
            recommended_tags = self._match_apis_by_keywords(user_query)
        
        # 构建推荐结果
        recommendations = []
        for tag in recommended_tags[:3]:  # 最多推荐3个API
            api_info = next((api for api in self.api_tags if api['tag'] == tag), None)
            if api_info:
                # 构建完整URL
                url_params = []
                if params.get('section_id'):
                    url_params.append(f"section_id={params['section_id']}")
                if params.get('start_date'):
                    url_params.append(f"start_date={params['start_date']}")
                if params.get('end_date'):
                    url_params.append(f"end_date={params['end_date']}")
                
                param_str = '&'.join(url_params) if url_params else ''
                full_url = f"{base_url}{api_info['endpoint']}"
                if param_str:
                    full_url += f"?{param_str}"
                
                recommendations.append({
                    'tag': api_info['tag'],
                    'name': api_info['name'],
                    'endpoint': api_info['endpoint'],
                    'description': api_info['description'],
                    'full_url': full_url,
                    'method': 'GET'
                })
        
        return {
            'success': True,
            'query': user_query,
            'execution_type': 'api',
            'recommendations': recommendations,
            'params': params,
            'reason': analysis.get('reason', ''),
            'count': len(recommendations)
        }
    
    def _match_apis_by_keywords(self, query: str) -> List[str]:
        """基于关键词匹配API"""
        query_lower = query.lower()
        matched = []
        
        for api in self.api_tags:
            # 检查关键词匹配
            if any(keyword in query_lower for keyword in api['keywords']):
                matched.append(api['tag'])
        
        # 如果没有匹配，返回最常用的几个
        if not matched:
            matched = ['hourly-flow', 'avg-travel-time', 'congestion-index']
        
        return matched
    
    def _execute_workflow(self, scenario: str, params: dict, user_query: str) -> Dict[str, Any]:
        """执行LangGraph工作流"""
        
        # 获取场景信息
        scenario_info = workflow_executor.get_scenario_info(scenario)
        
        # 打印调试信息
        print(f"[DEBUG] 执行工作流: scenario={scenario}")
        print(f"[DEBUG] 提取的参数: {params}")
        
        # 执行工作流
        result = workflow_executor.execute(scenario, params)
        
        return {
            'success': result['success'],
            'query': user_query,
            'execution_type': 'workflow',
            'scenario_name': scenario_info.get('name', scenario),
            'scenario_description': scenario_info.get('description', ''),
            'result': result.get('result', {}),
            'execution_logs': result.get('logs', []),
            'error': result.get('error', '')
        }
    
# 全局实例
enhanced_agent = EnhancedAgent()


if __name__ == '__main__':
    # 测试用例
    test_queries = [
        "帮我核算一下2023年1月3号的通行费用",
        "检测一下最近的异常交易",
        "分析全网的流量情况",
        "查询路段信息"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")
        print(f"{'='*60}")
        
        result = enhanced_agent.process_query(query)
        print(json.dumps(result, indent=2, ensure_ascii=False))
