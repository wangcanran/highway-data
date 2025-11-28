"""
AI SQL Agent - 自然语言转SQL查询
使用OpenAI理解用户意图，生成安全的SQL查询
"""
from openai import OpenAI
import json
import re
from typing import Dict, Any, List, Tuple
from models import db
from sqlalchemy import text
import config

# 配置OpenAI客户端
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_API_BASE
)

class AISQLAgent:
    """AI SQL代理 - 将自然语言转换为SQL查询"""
    
    def __init__(self):
        self.database_schema = self._get_database_schema()
    
    def _get_database_schema(self) -> str:
        """获取数据库schema描述"""
        return """
        数据库名: highway_db (高速公路数据库)
        
        表结构:
        
        1. section (路段表)
           - section_id: 路段ID (主键)
           - section_name: 路段名称
        
        2. tollstation (收费站表)
           - toll_station_id: 收费站ID (主键)
           - station_name: 收费站名称
           - section_id: 路段ID (外键)
           - station_type: 收费站类型
           - operation_status: 运营状态
           - station_status: 站点状态
           - latitude: 纬度
           - longitude: 经度
        
        3. gantry (门架表)
           - gantry_id: 门架ID (主键)
           - gantry_name: 门架名称
           - section_id: 路段ID (外键)
           - gantry_type: 门架类型
           - lane_count: 车道数
           - direction: 方向
        
        4. entrancetransaction (入口交易表)
           - entrance_transaction_id: 交易ID (主键)
           - pass_id: 通行标识
           - section_id: 路段ID (外键)
           - section_name: 路段名称
           - entrance_time: 入口时间
           - vehicle_class: 车型
           - card_type: 卡类型
        
        5. exittransaction (出口交易表)
           - exit_transaction_id: 交易ID (主键)
           - pass_id: 通行标识
           - section_id: 路段ID (外键)
           - section_name: 路段名称
           - exit_time: 出口时间
           - vehicle_class: 车型
           - toll_money: 应收金额
           - real_money: 实收金额
           - discount_type: 优惠类型
           - axis_count: 轴数
           - total_weight: 总重量
           - total_limit: 限重
        
        6. gantrytransaction (门架交易表)
           - gantry_transaction_id: 交易ID (主键)
           - gantry_id: 门架ID (外键)
           - pass_id: 通行标识
           - section_id: 路段ID
           - transaction_time: 交易时间
           - vehicle_type: 车辆类型
           - pay_fee: 支付费用
        
        常用车型代码:
        - 11-16: 货车（11=2轴货车, 12=3轴货车, 13=4轴货车, 14=5轴货车, 15=6轴货车, 16=6轴以上）
        - 1-4: 客车
        """
    
    def generate_sql(self, user_query: str) -> Dict[str, Any]:
        """
        使用AI生成SQL查询
        
        Args:
            user_query: 用户的自然语言查询
            
        Returns:
            包含SQL和说明的字典
        """
        prompt = f"""
你是一个SQL专家。根据用户的自然语言查询，生成对应的MySQL查询语句。

数据库schema:
{self.database_schema}

用户查询: {user_query}

请生成安全的SQL查询。要求:
1. 只能生成SELECT查询，不允许INSERT/UPDATE/DELETE
2. 使用LIMIT限制返回结果数量（默认100条）
3. 如果涉及时间范围，使用合理的默认值
4. 返回JSON格式，包含以下字段:
   - sql: 生成的SQL语句
   - explanation: 查询的中文说明
   - query_type: 查询类型 (simple/aggregate/join)
   - estimated_rows: 预估返回行数

示例:
用户: "查询所有路段"
{{
  "sql": "SELECT * FROM section LIMIT 100",
  "explanation": "查询所有路段信息，限制返回100条记录",
  "query_type": "simple",
  "estimated_rows": 8
}}

用户: "统计每个路段的收费站数量"
{{
  "sql": "SELECT s.section_name, COUNT(t.toll_station_id) as station_count FROM section s LEFT JOIN tollstation t ON s.section_id = t.section_id GROUP BY s.section_id, s.section_name",
  "explanation": "统计每个路段的收费站数量",
  "query_type": "aggregate",
  "estimated_rows": 8
}}

现在请为上述用户查询生成SQL。只返回JSON，不要其他内容。
"""
        
        try:
            response = client.chat.completions.create(
                model=config.FIXED_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是一个SQL专家，擅长将自然语言转换为SQL查询。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=config.REQUEST_TIMEOUT
            )
            
            content = response.choices[0].message.content.strip()
            
            # 提取JSON（可能被代码块包裹）
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            elif '```' in content:
                content = re.sub(r'```\w*\s*|\s*```', '', content)
            
            result = json.loads(content)
            
            # 验证SQL安全性
            sql = result.get('sql', '').upper()
            if not sql.strip().startswith('SELECT'):
                return {
                    'success': False,
                    'error': '安全检查失败：只允许SELECT查询'
                }
            
            # 检查危险关键字
            dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE']
            for keyword in dangerous_keywords:
                if keyword in sql:
                    return {
                        'success': False,
                        'error': f'安全检查失败：检测到危险关键字 {keyword}'
                    }
            
            result['success'] = True
            return result
            
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'AI返回的JSON格式错误: {str(e)}',
                'raw_response': content
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'生成SQL失败: {str(e)}'
            }
    
    def execute_sql(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """
        安全执行SQL查询
        
        Args:
            sql: SQL查询语句
            limit: 结果限制
            
        Returns:
            查询结果
        """
        try:
            # 添加LIMIT保护
            sql_upper = sql.upper()
            if 'LIMIT' not in sql_upper:
                sql = f"{sql.rstrip(';')} LIMIT {limit}"
            
            # 执行查询
            result = db.session.execute(text(sql))
            
            # 获取列名
            columns = result.keys()
            
            # 转换结果为字典列表
            rows = []
            for row in result:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # 处理特殊类型
                    if hasattr(value, 'isoformat'):  # datetime
                        value = value.isoformat()
                    elif isinstance(value, bytes):
                        value = value.decode('utf-8')
                    row_dict[col] = value
                rows.append(row_dict)
            
            return {
                'success': True,
                'data': rows,
                'count': len(rows),
                'columns': list(columns)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'SQL执行失败: {str(e)}'
            }
    
    def process_query(self, user_query: str, base_url: str = '') -> Dict[str, Any]:
        """
        处理用户的自然语言查询
        
        Args:
            user_query: 用户查询
            base_url: API基础URL
            
        Returns:
            包含结果和API链接的响应
        """
        # 1. 生成SQL
        sql_result = self.generate_sql(user_query)
        
        if not sql_result.get('success'):
            return sql_result
        
        # 2. 执行SQL
        sql = sql_result.get('sql')
        execution_result = self.execute_sql(sql)
        
        if not execution_result.get('success'):
            return execution_result
        
        # 3. 生成API链接（如果适用）
        api_endpoint = self._generate_api_endpoint(sql, base_url)
        
        # 4. 组合结果
        return {
            'success': True,
            'user_query': user_query,
            'explanation': sql_result.get('explanation'),
            'sql': sql,
            'query_type': sql_result.get('query_type'),
            'data': execution_result.get('data'),
            'count': execution_result.get('count'),
            'columns': execution_result.get('columns'),
            'api_endpoint': api_endpoint,
            'note': '这是AI生成的SQL查询结果。如果需要固定的API端点，请联系管理员。'
        }
    
    def _generate_api_endpoint(self, sql: str, base_url: str) -> str:
        """
        尝试生成对应的API端点
        
        Args:
            sql: SQL查询
            base_url: 基础URL
            
        Returns:
            API端点URL或说明
        """
        sql_lower = sql.lower()
        
        # 简单匹配常见查询模式
        if 'from section' in sql_lower and 'where' not in sql_lower:
            return f"{base_url}/api/sections"
        elif 'from tollstation' in sql_lower and 'where' not in sql_lower:
            return f"{base_url}/api/toll-stations"
        elif 'from gantry' in sql_lower and 'where' not in sql_lower:
            return f"{base_url}/api/gantries"
        elif 'from entrancetransaction' in sql_lower:
            return f"{base_url}/api/transactions/entrance"
        elif 'from exittransaction' in sql_lower:
            return f"{base_url}/api/transactions/exit"
        elif 'from gantrytransaction' in sql_lower:
            return f"{base_url}/api/transactions/gantry"
        else:
            return "该查询为自定义SQL，没有对应的固定API端点"


# 创建全局实例
ai_sql_agent = AISQLAgent()
