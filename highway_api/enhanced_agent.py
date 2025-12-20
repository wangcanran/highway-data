"""
统一智能Agent - 支持API推荐和多智能体协作
整合原有API推荐Agent和多智能体自主规划能力
"""
import json
from typing import Dict, Any, List
from openai import OpenAI
import config
from multi_agent_system import multi_agent_executor


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
        """初始化货车分析API知识库（完整版）"""
        common_params = [
            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
        ]
        
        return [
            {
                'tag': 'hourly-flow',
                'tag_name': '小时流量',
                'name': '路段货车小时流量',
                'endpoint': '/api/analytics/truck/hourly-flow',
                'method': 'GET',
                'description': '统计每个路段每小时通过的货车数量',
                'keywords': ['流量', '小时', '趋势', '高峰', '监测'],
                'use_cases': ['流量监测', '趋势分析', '高峰识别'],
                'parameters': common_params
            },
            {
                'tag': 'avg-travel-time',
                'tag_name': '平均通行时间',
                'name': '路段平均通行时间',
                'endpoint': '/api/analytics/truck/avg-travel-time',
                'method': 'GET',
                'description': '统计货车的平均通行时间（分钟）',
                'keywords': ['时间', '效率', '拥堵', '时效', '速度'],
                'use_cases': ['效率评估', '拥堵分析', '时效监控'],
                'parameters': common_params
            },
            {
                'tag': 'avg-toll-fee',
                'tag_name': '平均通行费',
                'name': '路段平均通行费',
                'endpoint': '/api/analytics/truck/avg-toll-fee',
                'method': 'GET',
                'description': '统计货车的平均通行费用（元）',
                'keywords': ['费用', '成本', '收费', '价格', '通行费'],
                'use_cases': ['成本分析', '收费统计', '定价参考'],
                'parameters': common_params
            },
            {
                'tag': 'congestion-index',
                'tag_name': '拥堵指数',
                'name': '路段拥堵指数',
                'endpoint': '/api/analytics/truck/congestion-index',
                'method': 'GET',
                'description': '通过货车流量与车道数比值评估拥堵程度',
                'keywords': ['拥堵', '路况', '交通', '堵塞', '指数'],
                'use_cases': ['拥堵监测', '路况评估', '交通预警'],
                'parameters': common_params
            },
            {
                'tag': 'overweight-rate',
                'tag_name': '超载比例',
                'name': '路段超载货车比例',
                'endpoint': '/api/analytics/truck/overweight-rate',
                'method': 'GET',
                'description': '统计超载货车的比例，反映合规风险（已启用数据脱敏）',
                'keywords': ['超载', '超重', '合规', '违规', '监管'],
                'use_cases': ['合规监测', '风险评估', '执法参考'],
                'parameters': common_params
            },
            {
                'tag': 'discount-rate',
                'tag_name': '优惠比例',
                'name': '路段通行费优惠比例',
                'endpoint': '/api/analytics/truck/discount-rate',
                'method': 'GET',
                'description': '统计享受通行费优惠的货车比例',
                'keywords': ['优惠', '折扣', '减免', '政策'],
                'use_cases': ['政策效果分析', '优惠统计', '成本优化'],
                'parameters': common_params
            },
            {
                'tag': 'peak-hours',
                'tag_name': '高峰时段',
                'name': '路段货车高峰时段',
                'endpoint': '/api/analytics/truck/peak-hours',
                'method': 'GET',
                'description': '识别货车流量最高的小时区间',
                'keywords': ['高峰', '繁忙', '时段', '高流量'],
                'use_cases': ['高峰识别', '调度优化', '资源规划'],
                'parameters': common_params
            },
            {
                'tag': 'avg-axle-count',
                'tag_name': '平均轴数',
                'name': '路段货车平均轴数',
                'endpoint': '/api/analytics/truck/avg-axle-count',
                'method': 'GET',
                'description': '统计货车的平均轴数，反映货车类型分布',
                'keywords': ['轴数', '车型', '类型', '结构'],
                'use_cases': ['车型分析', '结构分析', '承载能力评估'],
                'parameters': common_params
            },
            {
                'tag': 'lane-utilization',
                'tag_name': '车道利用率',
                'name': '路段车道利用率',
                'endpoint': '/api/analytics/truck/lane-utilization',
                'method': 'GET',
                'description': '统计货车流量与车道数的比值',
                'keywords': ['车道', '利用率', '容量', '资源'],
                'use_cases': ['资源利用分析', '容量评估', '优化规划'],
                'parameters': common_params
            },
            {
                'tag': 'exit-hourly-flow',
                'tag_name': '出口小时流量',
                'name': '路段货车出口小时流量',
                'endpoint': '/api/analytics/truck/exit-hourly-flow',
                'method': 'GET',
                'description': '统计每个路段每小时出口的货车数量',
                'keywords': ['出口', '流量', '出站'],
                'use_cases': ['出口监测', '流量统计', '出站分析'],
                'parameters': common_params
            },
            {
                'tag': 'exit-hourly-flow-k-anonymized',
                'tag_name': 'k匿名出口数据',
                'name': '出口数据k匿名（KACA）',
                'endpoint': '/api/analytics/truck/exit-hourly-flow-k-anonymized',
                'method': 'GET',
                'description': '基于KACA算法对货车出口交易数据进行k-匿名隐私保护',
                'keywords': ['k匿名', '隐私', '脱敏', 'KACA', '匿名化'],
                'use_cases': ['隐私保护', '数据脱敏', '对外发布', '合规分析'],
                'parameters': common_params + [
                    {'name': 'k', 'type': 'integer', 'required': False, 'description': 'k值（默认5）'}
                ]
            }
        ]
    
    def process_query(self, user_query: str, base_url: str = None) -> Dict[str, Any]:
        """处理用户查询的主入口 - 直接使用多智能体系统"""
        
        if not user_query:
            return {
                'success': False,
                'query': '',
                'execution_type': 'workflow',
                'error': '查询内容不能为空'
            }
        
        # 直接使用多智能体协作系统处理所有查询
        return self._execute_multi_agent(user_query)
    
    def _analyze_query(self, user_query: str) -> Dict[str, Any]:
        """使用LLM分析用户查询意图"""
        
        system_prompt = """你是一个高速公路数据服务的智能分析助手。

你的任务是分析用户查询，判断需要：
1. API推荐（query_type: "api"）- 货车数据分析查询（流量、费用、拥堵等单一维度分析）
2. 工作流编排（query_type: "workflow"）- 需要多步骤、跨主体的复杂业务场景（核算、稽核、全网分析）

=== 货车分析API（11个）===
**重要：推荐API时，必须使用下面的tag值填入recommended_apis数组**

1. hourly-flow - 小时流量：统计每小时货车通行量
   关键词：流量、小时、趋势、高峰、监测
   
2. avg-travel-time - 平均通行时间：评估通行效率
   关键词：时间、效率、拥堵、时效、速度
   
3. avg-toll-fee - 平均通行费：分析费用水平
   关键词：费用、成本、收费、价格、通行费
   
4. congestion-index - 拥堵指数：评估拥堵程度
   关键词：拥堵、路况、交通、堵塞、指数
   
5. overweight-rate - 超载比例：合规监管（数据脱敏）
   关键词：超载、超重、合规、违规、监管
   
6. discount-rate - 优惠比例：政策效果分析
   关键词：优惠、折扣、减免、政策
   
7. peak-hours - 高峰时段：识别繁忙时段
   关键词：高峰、繁忙、时段、高流量
   
8. avg-axle-count - 平均轴数：车型分布分析
   关键词：轴数、车型、类型、结构
   
9. lane-utilization - 车道利用率：资源利用评估
   关键词：车道、利用率、容量、资源
   
10. exit-hourly-flow - 出口小时流量：出口流量统计
    关键词：出口、流量、出站
    
11. exit-hourly-flow-k-anonymized - k匿名数据：隐私保护版本
    关键词：k匿名、隐私、脱敏、KACA、匿名化

=== 多智能体工作流模式 ===

当用户需求需要多步骤、跨主体协作时，使用workflow模式：
- 核算、结算、对账类业务（需要查询多个数据源并计算）
- 异常检测、稽核、监测类业务（需要获取数据并分析异常）
- 全网分析、整体统计类业务（需要聚合多个路段数据）
- 任何需要"计算"、"综合分析"、"对比"的复杂需求

多智能体系统会自主：
1. 理解需求并制定执行计划
2. 决定调用哪些API
3. 综合数据并生成分析结果

=== 匹配规则 ===
1. 单一维度查询 → api（直接推荐API）
2. 多步骤/复杂业务 → workflow（启动多智能体协作）

示例：
- "分析货车流量" → api, recommended_apis: ["hourly-flow"]
- "查看拥堵情况" → api, recommended_apis: ["congestion-index"]
- "统计通行费用" → api, recommended_apis: ["avg-toll-fee"]
- "检查超载" → api, recommended_apis: ["overweight-rate"]
- "核算通行费" → workflow（多智能体自主规划）
- "检测异常交易" → workflow（多智能体自主规划）
- "分析全网流量" → workflow（多智能体自主规划）
- "帮我计算..." → workflow（需要计算处理）
- "对比分析..." → workflow（需要综合分析）

请以JSON格式返回：
{
    "success": true,
    "query_type": "api" | "workflow",
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
            print(f"[DEBUG] LLM原始返回:\n{content}")
            
            # 提取JSON - 增强容错
            try:
                # 尝试直接解析
                if content.startswith('{'):
                    json_match = json.loads(content)
                else:
                    # 提取JSON块
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = content[start:end]
                        print(f"[DEBUG] 提取的JSON:\n{json_str}")
                        json_match = json.loads(json_str)
                    else:
                        raise ValueError("未找到JSON内容")
            except json.JSONDecodeError as je:
                print(f"[ERROR] JSON解析失败: {str(je)}")
                print(f"[ERROR] 问题内容: {content}")
                # 回退到关键词匹配
                return {
                    'success': True,
                    'query_type': 'api',
                    'recommended_apis': self._match_apis_by_keywords(user_query),
                    'params': {},
                    'reason': '使用关键词匹配（LLM返回格式错误）'
                }
            
            return json_match
            
        except Exception as e:
            print(f"[ERROR] LLM处理异常: {str(e)}")
            return {
                'success': False,
                'error': f'LLM分析失败: {str(e)}',
                'query_type': 'api',
                'recommended_apis': self._match_apis_by_keywords(user_query),
                'params': {}
            }
    
    def _recommend_api(self, user_query: str, analysis: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        """推荐合适的API（返回完整信息）"""
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
                example_url = f"{base_url}{api_info['endpoint']}"
                full_url = f"{example_url}?{param_str}" if param_str else example_url
                
                # 返回完整的API信息（兼容旧UI）
                response_examples = self._get_response_examples(api_info['tag'])
                api_rec = {
                    'tag': api_info['tag'],
                    'tag_name': api_info.get('tag_name', api_info['name']),
                    'name': api_info['name'],
                    'api_name': api_info['name'],
                    'endpoint': api_info['endpoint'],
                    'method': api_info.get('method', 'GET'),
                    'description': api_info['description'],
                    'use_cases': api_info.get('use_cases', []),
                    'parameters': api_info.get('parameters', []),
                    'example': full_url,
                    'example_url': full_url,
                    'full_url': full_url,
                    'response_example': response_examples['after']
                }
                # 添加数据脱敏前的示例（如果有）
                if response_examples.get('before'):
                    api_rec['response_example_before'] = response_examples['before']
                recommendations.append(api_rec)
        
        # 完全兼容旧版Agent格式
        return {
            'success': True,
            'execution_type': 'api',
            'understood': True,  # 旧版兼容字段
            'query': user_query,
            'explanation': analysis.get('reason', '根据您的需求，为您推荐以下最合适的API接口'),
            'recommendations': recommendations,
            'requirement_analysis': {
                'scenario': '货车数据分析',
                'matched_tags': recommended_tags,
                'tag_names': [api_info.get('tag_name', api_info['name']) for api_info in [next((a for a in self.api_tags if a['tag'] == t), {}) for t in recommended_tags]],
                'reason': analysis.get('reason', '')
            },
            'api_matching': {
                'total_apis': len(recommendations),
                'matched_tags': recommended_tags
            },
            'count': len(recommendations)
        }
    
    def _get_response_examples(self, tag: str) -> Dict[str, Any]:
        """获取API的响应示例，包含数据脱敏前后对比"""
        examples = {
            'hourly-flow': {
                'before': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'section_name': '麻文高速', 'hour': '2023-01-02 09', 'truck_count': 42}],
                    'count': 1,
                    'category': '📊 流量统计类（未加差分隐私）'
                },
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'section_name': '麻文高速', 'hour': '2023-01-02 09', 'truck_count_dp': 39, 'epsilon': 1.0, 'dp_method': 'Laplace'}],
                    'count': 1,
                    'category': '📊 流量统计类（差分隐私，ε=1.0，拉普拉斯机制）'
                }
            },
            'avg-travel-time': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'avg_travel_time_minutes': 45.32, 'sample_count': 1523}],
                    'category': '⏱️ 通行时效类'
                }
            },
            'avg-toll-fee': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'avg_toll_fee': 35.67, 'transaction_count': 2340}],
                    'category': '💰 费用分析类'
                }
            },
            'congestion-index': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'truck_count': 5432, 'avg_lanes': 4.0, 'congestion_index': 1358.0}],
                    'category': '📊 流量统计类'
                }
            },
            'overweight-rate': {
                'before': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'total_count': 2340, 'overweight_count': 356, 'overweight_rate': 0.1521, 'overweight_percentage': 15.21}],
                    'category': '⚖️ 合规监测类'
                },
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G*********0', 'section_id_masked': True, 'total_count': 2340, 'overweight_count': 356, 'overweight_rate': 0.1521, 'overweight_percentage': 15.21}],
                    'category': '⚖️ 合规监测类（数据脱敏，掩码Masking）',
                    'data_masking': {'enabled': True, 'method': '掩码(Masking)', 'fields': ['section_id']}
                }
            },
            'discount-rate': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'total_count': 2340, 'discount_count': 809, 'discount_rate': 0.3458, 'discount_percentage': 34.58}],
                    'category': '💰 费用分析类'
                }
            },
            'peak-hours': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'hour': 14, 'truck_count': 234}],
                    'category': '📊 流量统计类'
                }
            },
            'avg-axle-count': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'avg_axle_count': 4.23, 'truck_count': 2340}],
                    'category': '🚚 车辆特征类'
                }
            },
            'lane-utilization': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'truck_count': 5432, 'avg_lanes': 4.0, 'lane_utilization': 1358.0}],
                    'category': '📊 流量统计类'
                }
            },
            'exit-hourly-flow': {
                'after': {
                    'success': True,
                    'data': [{'section_id': 'G5615530120', 'section_name': '麻文高速', 'hour': '2023-01-02 09', 'exit_count': 38}],
                    'count': 1,
                    'category': '📊 流量统计类'
                }
            },
            'exit-hourly-flow-k-anonymized': {
                'before': {
                    'success': True,
                    'data': [
                        {
                            'section_id': 'G5615530120',
                            'exit_time': '2023-01-03 09:15:23',
                            'vehicle_class': '11',
                            'vehicle_plate_color_id': '0',
                            'axis_count': '2',
                            'total_weight': '31000',
                            'total_limit': '36000',
                            'toll_money': 29.55,
                            'real_money': 28.08
                        }
                    ],
                    'count': 983,
                    'category': '🔒 隐私保护类（原始出口交易记录）'
                },
                'after': {
                    'success': True,
                    'data': [
                        {
                            'section_region': 'G561区域',
                            'time_period': '上午时段(06-12)',
                            'vehicle_class': '11',
                            'vehicle_plate_color_id': '0',
                            'axis_count': '2',
                            'total_weight': '31000',
                            'total_limit': '36000',
                            'toll_money': 29.55,
                            'real_money': 28.08,
                            'k_anonymized': True,
                            'algorithm': 'KACA'
                        }
                    ],
                    'count': 983,
                    'category': '🔒 隐私保护类（记录级k匿名，KACA算法）',
                    'privacy_protection': {
                        'method': 'KACA (K-Anonymity Clustering Algorithm)',
                        'k_value': 5,
                        'quasi_identifiers': ['section_id', 'exit_time'],
                        'generalization': {
                            'geographic': 'section_id → section_region',
                            'temporal': 'exit_time → time_period'
                        }
                    }
                }
            }
        }
        return examples.get(tag, {'after': {'success': True, 'data': [], 'category': '📊 数据统计类'}})
    
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
    
    def _execute_multi_agent(self, user_query: str) -> Dict[str, Any]:
        """执行多智能体协作任务"""
        
        print(f"[DEBUG] 启动多智能体协作系统")
        print(f"[DEBUG] 用户查询: {user_query}")
        
        # 执行多智能体协作
        result = multi_agent_executor.execute(user_query)
        
        return {
            'success': result['success'],
            'query': user_query,
            'execution_type': 'workflow',
            'scenario_name': '多智能体自主规划',
            'scenario_description': result.get('plan', {}).get('task_understanding', ''),
            'result': result.get('result', {}),
            'execution_logs': result.get('execution_logs', []),
            'api_calls': result.get('api_calls', []),
            'plan': result.get('plan', {}),
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