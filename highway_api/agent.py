"""
高速公路数据API智能Agent - 基于LLM的智能推荐
使用GPT-4理解用户需求并推荐合适的API接口
"""
import json
import re
from typing import Dict, List, Any
from openai import OpenAI
import config

class HighwayAPIAgent:
    """高速公路API智能助手"""
    
    def __init__(self):
        """初始化Agent，定义API知识库和LLM配置"""
        
        # LLM配置（从config.py加载）
        self.openai_client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_API_BASE
        )
        self.model_name = config.FIXED_MODEL_NAME
        self.request_timeout = config.REQUEST_TIMEOUT
        
        # API标签定义（用于LLM理解用户需求）
        self.api_tags = {
            'hourly-flow': {
                'name': '小时流量',
                'description': '统计每个路段每小时通过的货车数量',
                'use_cases': ['流量监测', '趋势分析', '高峰识别']
            },
            'avg-travel-time': {
                'name': '平均通行时间',
                'description': '统计货车的平均通行时间（分钟）',
                'use_cases': ['效率评估', '拥堵分析', '时效监控']
            },
            'avg-toll-fee': {
                'name': '平均通行费',
                'description': '统计货车的平均通行费用（元）',
                'use_cases': ['成本分析', '收费统计', '定价参考']
            },
            'congestion-index': {
                'name': '拥堵指数',
                'description': '通过货车流量与车道数比值评估拥堵程度',
                'use_cases': ['拥堵监测', '路况评估', '交通预警']
            },
            'overweight-rate': {
                'name': '超载比例',
                'description': '统计超载货车的比例，反映合规风险（已启用数据脱敏：section_id掩码处理）',
                'use_cases': ['合规监测', '风险评估', '执法参考'],
                'data_masking': True
            },
            'discount-rate': {
                'name': '优惠比例',
                'description': '统计享受通行费优惠的货车比例',
                'use_cases': ['政策效果分析', '优惠统计', '成本优化']
            },
            'peak-hours': {
                'name': '高峰时段',
                'description': '识别货车流量最高的小时区间',
                'use_cases': ['高峰识别', '调度优化', '资源规划']
            },
            'avg-axle-count': {
                'name': '平均轴数',
                'description': '统计货车的平均轴数，反映货车类型分布',
                'use_cases': ['车型分析', '结构分析', '承载能力评估']
            },
            'lane-utilization': {
                'name': '车道利用率',
                'description': '统计货车流量与车道数的比值',
                'use_cases': ['资源利用分析', '容量评估', '优化规划']
            },
            'toll-station-status': {
                'name': '收费站状态',
                'description': '查询收费站的运行状态',
                'use_cases': ['运营监控', '状态查询', '设备管理']
            },
            'exit-hourly-flow-k-anonymized': {
                'name': '出口数据k匿名(KACA)',
                'description': '基于KACA算法对货车出口交易数据进行k-匿名隐私保护，使用聚类和自适应泛化',
                'use_cases': ['隐私保护', '数据脱敏', '对外发布', '合规分析']
            }
        }
        
        # 第二步:API知识库(数据类型到具体API的映射)
        # 只保留货车分析标签API
        self.api_knowledge = {
            # 货车分析相关(标签API)
            'truck_analytics': {
                'keywords': ['货车', '卡车', 'truck', '货运', '物流', '货车分析', '超载', '轴数', '拥堵', '高峰', 'k匿名', 'k-匿名', '隐私保护', '数据脱敏', '匿名化', '出口交易', '出口数据'],
                'apis': [
                    {
                        'endpoint': '/api/analytics/truck/avg-travel-time',
                        'method': 'GET',
                        'description': '路段平均通行时间 - 统计货车的平均通行时间（分钟）',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/avg-travel-time?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'avg_travel_time_minutes': 45.32, 'sample_count': 1523}],
                            'category': '⏱️ 通行时效类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/avg-toll-fee',
                        'method': 'GET',
                        'description': '路段平均通行费 - 统计货车的平均通行费用（元）',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/avg-toll-fee?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'avg_toll_fee': 35.67, 'transaction_count': 2340}],
                            'category': '💰 费用分析类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/congestion-index',
                        'method': 'GET',
                        'description': '路段拥堵指数 - 通过货车流量与车道数比值评估拥堵程度',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/congestion-index?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'truck_count': 5432, 'avg_lanes': 4.0, 'congestion_index': 1358.0}],
                            'category': '📊 流量统计类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/overweight-rate',
                        'method': 'GET',
                        'description': '路段超载货车比例 - 统计超载货车的比例，反映合规风险（已启用数据脱敏）',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/overweight-rate?section_id=G5615530120',
                        'response_example_before': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'total_count': 2340, 'overweight_count': 356, 'overweight_rate': 0.1521, 'overweight_percentage': 15.21}],
                            'category': '⚖️ 合规监测类'
                        },
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G*********0', 'section_id_masked': True, 'total_count': 2340, 'overweight_count': 356, 'overweight_rate': 0.1521, 'overweight_percentage': 15.21}],
                            'category': '⚖️ 合规监测类',
                            'data_masking': {'enabled': True, 'method': '掩码(Masking)', 'fields': ['section_id'], 'description': '对路段ID进行掩码处理，保留首尾字符，中间用*替换'}
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/discount-rate',
                        'method': 'GET',
                        'description': '路段通行费优惠比例 - 统计享受通行费优惠的货车比例',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/discount-rate?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'total_count': 2340, 'discount_count': 809, 'discount_rate': 0.3458, 'discount_percentage': 34.58}],
                            'category': '💰 费用分析类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/peak-hours',
                        'method': 'GET',
                        'description': '路段货车高峰时段 - 识别货车流量最高的小时区间',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/peak-hours?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'hour': 14, 'truck_count': 234}],
                            'category': '📊 流量统计类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/avg-axle-count',
                        'method': 'GET',
                        'description': '路段货车平均轴数 - 统计货车的平均轴数，反映货车类型分布',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/avg-axle-count?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'avg_axle_count': 4.23, 'sample_count': 2340}],
                            'category': '⚖️ 合规监测类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/lane-utilization',
                        'method': 'GET',
                        'description': '路段车道利用率 - 统计货车流量与车道数的比值',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'}
                        ],
                        'example': '/api/analytics/truck/lane-utilization?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'section_id': 'G5615530120', 'avg_lanes': 4.0, 'total_transactions': 5432, 'lane_utilization': 1358.0}],
                            'category': '📊 流量统计类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/toll-station-status',
                        'method': 'GET',
                        'description': '路段收费站运行状态 - 查询收费站的运行状态',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID'}
                        ],
                        'example': '/api/analytics/truck/toll-station-status?section_id=G5615530120',
                        'response_example': {
                            'success': True,
                            'data': [{'toll_station_id': 'xxx', 'station_name': '新宝站', 'section_id': 'G5615530120', 'operation_status': '1', 'status_text': '正常'}],
                            'count': 5,
                            'category': '📈 基础指标类'
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/exit-hourly-flow-k-anonymized',
                        'method': 'GET',
                        'description': '货车出口交易数据k匿名(KACA) - 基于KACA算法进行记录级k-匿名隐私保护（删标识符，泛化路段与时间）',
                        'params': [
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始日期'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束日期'},
                            {'name': 'k', 'type': 'integer', 'required': False, 'description': 'k-匿名的k值（默认5）'}
                        ],
                        'example': '/api/analytics/truck/exit-hourly-flow-k-anonymized?start_date=2023-01-02&end_date=2023-01-04&k=5',
                        'response_example_before': {
                            'success': True,
                            'data': [
                                {
                                    'exit_transaction_id': '202301021234567890',
                                    'section_id': 'G5615530120',
                                    'section_name': '麻文高速',
                                    'exit_time': '2023-01-02 09:23:45',
                                    'vehicle_class': '11',
                                    'vehicle_plate_color_id': '0',
                                    'axis_count': '2',
                                    'total_weight': '31000',
                                    'total_limit': '36000',
                                    'toll_money': 29.55,
                                    'real_money': 28.08,
                                    'card_pay_toll': 28.08,
                                    'card_type': '23',
                                    'pay_type': '4',
                                    'pay_card_type': '23',
                                    'discount_type': '0'
                                }
                            ],
                            'count': 1,
                            'category': '原始出口交易记录（未做k匿名）'
                        },
                        'response_example': {
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
                                    'card_pay_toll': 28.08,
                                    'card_type': '23',
                                    'pay_type': '4',
                                    'pay_card_type': '23',
                                    'discount_type': '0',
                                    'k_anonymized': True,
                                    'algorithm': 'KACA'
                                }
                            ],
                            'count': 983,
                            'category': '🔒 隐私保护类（记录级k匿名，KACA算法）',
                            'privacy_protection': {
                                'method': 'KACA (K-Anonymity Clustering Algorithm)',
                                'algorithm': 'KACA',
                                'k_value': 5,
                                'input_source': '原始出口交易记录',
                                'quasi_identifiers': ['section_id', 'exit_time'],
                                'generalization': {
                                    'geographic': 'section_id → section_region',
                                    'temporal': 'exit_time → time_period'
                                },
                                'description': '使用KACA算法对出口交易记录进行聚类和泛化，删除标识符，仅保留泛化后的准标识符和业务/敏感字段，输出记录级k匿名数据'
                            }
                        }
                    },
                    {
                        'endpoint': '/api/analytics/truck/hourly-flow',
                        'method': 'GET',
                        'description': '路段货车小时流量 - 对每小时货车计数应用差分隐私（拉普拉斯机制）',
                        'params': [
                            {'name': 'section_id', 'type': 'string', 'required': False, 'description': '路段ID，可选'},
                            {'name': 'start_date', 'type': 'string', 'required': False, 'description': '开始时间'},
                            {'name': 'end_date', 'type': 'string', 'required': False, 'description': '结束时间'}
                        ],
                        'example': '/api/analytics/truck/hourly-flow?start_date=2023-01-02&end_date=2023-01-04',
                        'response_example_before': {
                            'success': True,
                            'data': [
                                {
                                    'section_id': 'G5615530120',
                                    'section_name': '麻文高速',
                                    'hour': '2023-01-02 09',
                                    'truck_count': 42
                                }
                            ],
                            'count': 1,
                            'category': '📊 流量统计类（未加差分隐私）'
                        },
                        'response_example': {
                            'success': True,
                            'data': [
                                {
                                    'section_id': 'G5615530120',
                                    'section_name': '麻文高速',
                                    'hour': '2023-01-02 09',
                                    'truck_count_dp': 39,
                                    'epsilon': 1.0,
                                    'dp_method': 'Laplace'
                                }
                            ],
                            'count': 1,
                            'category': '📊 流量统计类（差分隐私，ε=1.0，拉普拉斯机制）'
                        }
                    }
                ]
            }
        }
    
    def process_query(self, user_query: str, base_url: str) -> Dict[str, Any]:
        """
        处理用户查询，返回推荐的API（基于LLM的两步流程）
        
        流程：
        1. 第一步：使用LLM理解用户需求场景
        2. 第二步：根据LLM分析结果匹配对应的API接口
        
        Args:
            user_query: 用户的自然语言查询
            base_url: API基础URL
            
        Returns:
            包含需求理解和API推荐的响应字典
        """
        try:
            # ========== 第一步：使用LLM理解用户需求，返回匹配的API标签 ==========
            step1_result = self._llm_understand_requirement(user_query)
            
            if not step1_result['understood']:
                # LLM无法理解需求，返回建议
                return {
                    'understood': False,
                    'message': step1_result.get('message', '抱歉，我没有理解您的需求。'),
                    'available_tags': self._get_all_tags(),
                    'tip': '请尝试描述您想了解的数据，例如：流量情况、通行费用、超载监测等'
                }
            
            # ========== 第二步：根据匹配的标签构建API列表 ==========
            step2_result = self._build_apis_from_tags(step1_result['matched_tags'], base_url)
            
            # 生成完整响应
            return {
                'understood': True,
                'query': user_query,
                
                # 需求理解结果
                'requirement_analysis': {
                    'scenario': step1_result['scenario_description'],
                    'matched_tags': step1_result['matched_tags'],
                    'tag_names': step1_result['tag_names'],
                    'reason': step1_result['reason']
                },
                
                # API匹配结果
                'api_matching': {
                    'total_apis': len(step2_result['recommendations']),
                    'matched_tags': step1_result['matched_tags']
                },
                
                # 综合说明
                'explanation': self._generate_explanation_from_tags(
                    user_query, 
                    step1_result, 
                    step2_result
                ),
                
                # API推荐列表
                'recommendations': step2_result['recommendations']
            }
        except Exception as e:
            # 出现错误时回退到规则匹配
            print(f"LLM处理出错: {str(e)}, 回退到规则匹配")
            return self._fallback_rule_based_query(user_query, base_url)
    
    def _llm_understand_requirement(self, user_query: str) -> Dict[str, Any]:
        """
        使用LLM理解用户需求，直接返回匹配的API标签列表
        
        Returns:
            需求理解结果，包含匹配的API标签列表
        """
        # 准备API标签描述
        api_tags_desc = "可用的货车分析API标签：\n"
        for tag_id, tag_info in self.api_tags.items():
            use_cases_str = '、'.join(tag_info['use_cases'])
            api_tags_desc += f"- {tag_id} ({tag_info['name']}): {tag_info['description']}\n  适用场景: {use_cases_str}\n"
        
        # 构建系统提示词
        system_prompt = f"""你是高速公路货车数据分析API助手。根据用户的自然语言需求，智能匹配最相关的API标签。

{api_tags_desc}

要求：
1. 理解用户的真实需求意图，不要依赖关键词匹配
2. 根据需求场景，选择最相关的API标签
3. 如果需求涉及多个方面，可以返回多个相关标签
4. **如果用户要求"所有数据"、"全部数据"、"所有信息"等宽泛查询，返回所有可用标签**
5. 提供简洁的推荐理由

返回JSON格式：
{{
    "understood": true/false,
    "scenario_description": "对用户需求的理解描述（1句话）",
    "matched_tags": ["tag-id1", "tag-id2"],
    "reason": "为什么推荐这些标签（1句话）"
}}

无法理解时：{{"understood": false, "message": "原因"}}

示例：
- 用户问"哪个时间段货车最多" → matched_tags: ["hourly-flow", "peak-hours"]
- 用户问"通行费用贵不贵" → matched_tags: ["avg-toll-fee"]
- 用户问"有没有超载的车" → matched_tags: ["overweight-rate"]
- 用户问"所有数据"或"全部信息" → matched_tags: 返回所有标签ID

仅返回JSON，无需额外解释。"""
        
        user_prompt = f"用户需求：{user_query}"
        
        try:
            # 调用OpenAI API
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # 降低温度以获得更精准的结果
                timeout=self.request_timeout,
                response_format={"type": "json_object"}
            )
            
            # 解析响应
            result = json.loads(response.choices[0].message.content)
            
            if not result.get('understood', False):
                return {
                    'understood': False,
                    'message': result.get('message', '无法理解您的需求')
                }
            
            # 获取匹配的标签
            matched_tags = result.get('matched_tags', [])
            
            # 验证标签是否有效
            valid_tags = [tag for tag in matched_tags if tag in self.api_tags]
            
            if not valid_tags:
                return {
                    'understood': False,
                    'message': 'LLM返回的标签无效'
                }
            
            # 构建标签名称列表
            tag_names = [self.api_tags[tag]['name'] for tag in valid_tags]
            
            return {
                'understood': True,
                'scenario_description': result.get('scenario_description', ''),
                'matched_tags': valid_tags,
                'tag_names': tag_names,
                'reason': result.get('reason', '')
            }
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {str(e)}")
            return {'understood': False, 'message': 'AI响应格式错误'}
        except Exception as e:
            print(f"LLM调用错误: {str(e)}")
            raise
    
    def _build_apis_from_tags(self, matched_tags: List[str], base_url: str) -> Dict[str, Any]:
        """
        根据匹配的标签列表构建API推荐列表
        
        Args:
            matched_tags: LLM匹配的API标签列表
            base_url: API基础URL
            
        Returns:
            API推荐列表
        """
        recommendations = []
        
        # 遍历所有API，找到标签匹配的
        for api in self.api_knowledge['truck_analytics']['apis']:
            endpoint = api['endpoint']
            # 从endpoint中提取标签（例如 /api/analytics/truck/hourly-flow -> hourly-flow）
            tag = endpoint.split('/')[-1]
            
            if tag in matched_tags:
                # 构建完整URL
                full_url = base_url.rstrip('/') + api['endpoint']
                
                # 构建参数说明
                params_desc = []
                if api['params']:
                    for param in api['params']:
                        required_text = '【必需】' if param['required'] else '【可选】'
                        params_desc.append(f"  - {param['name']}: {param['description']} {required_text}")
                
                recommendation = {
                    'tag': tag,
                    'tag_name': self.api_tags[tag]['name'],
                    'api_name': api['description'],
                    'endpoint': api['endpoint'],
                    'method': api['method'],
                    'full_url': full_url,
                    'example_url': base_url.rstrip('/') + api['example'],
                    'parameters': api['params'],
                    'parameters_description': '\n'.join(params_desc) if params_desc else '无参数',
                    'response_example': api['response_example'],
                    'response_example_before': api.get('response_example_before'),  # 处理前的响应示例（用于数据脱敏对比）
                    'description': api['description'],
                    'use_cases': self.api_tags[tag]['use_cases']
                }
                recommendations.append(recommendation)
        
        return {
            'recommendations': recommendations
        }
    
    def _generate_explanation_from_tags(self, query: str, step1: Dict, step2: Dict) -> str:
        """基于标签生成简洁的综合说明"""
        tag_names = '、'.join(step1['tag_names'])
        
        explanation = f"🎯 需求：{query}\n\n"
        explanation += f"✓ 理解：{step1['scenario_description']}\n"
        explanation += f"✓ 推荐理由：{step1['reason']}\n"
        explanation += f"✓ 匹配标签：{tag_names}\n"
        explanation += f"✓ 匹配到 {len(step2['recommendations'])} 个API接口\n\n"
        explanation += "💡 系统已智能识别您的需求并推荐最相关的数据分析API"
        
        return explanation
    
    def _get_all_tags(self) -> List[Dict[str, Any]]:
        """获取所有可用的API标签"""
        return [
            {
                'tag_id': tag_id,
                'name': info['name'],
                'description': info['description'],
                'use_cases': info['use_cases']
            }
            for tag_id, info in self.api_tags.items()
        ]
    
    def _fallback_rule_based_query(self, user_query: str, base_url: str) -> Dict[str, Any]:
        """
        规则匹配的回退方法（当LLM失败时使用）
        返回所有可用的API标签供用户选择
        """
        return {
            'understood': False,
            'message': 'AI分析服务暂时不可用，以下是所有可用的数据分析API：',
            'available_tags': self._get_all_tags(),
            'tip': '请描述您想了解的数据，例如：流量情况、通行费用、超载监测等'
        }
