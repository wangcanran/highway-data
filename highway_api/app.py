"""
Highway API - 基于 Flask + SQLAlchemy + Marshmallow
使用ORM替代原始SQL查询
"""
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime
import json
import os
from functools import wraps
from agent import HighwayAPIAgent
from gantry_rule_generator import generate_rule_based_gantry_transaction
from model_gantry_generator import generate_model_based_gantry
from dgm_api import generate_dgm_gantry, get_dgm_api
import config
from sqlalchemy import func, text, case, desc
from sqlalchemy.sql import extract
import random, math

# 导入增强Agent（包含多智能体系统）
from enhanced_agent import enhanced_agent

# 导入模型和schemas
from models import db, Section, TollStation, Gantry, EntranceTransaction, ExitTransaction, GantryTransaction, AuditLog
from schemas import ma, section_schema, sections_schema, toll_station_schema, toll_stations_schema
from schemas import gantry_schema, gantries_schema, entrance_transaction_schema, entrance_transactions_schema
from schemas import exit_transaction_schema, exit_transactions_schema, gantry_transaction_schema, gantry_transactions_schema
from schemas import audit_log_schema, audit_logs_schema

# 导入AI SQL Agent
from ai_sql_agent import ai_sql_agent

app = Flask(__name__)
CORS(app)

# 配置SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SQLALCHEMY_ECHO'] = config.SQLALCHEMY_ECHO
app.config['SQLALCHEMY_POOL_SIZE'] = config.SQLALCHEMY_POOL_SIZE
app.config['SQLALCHEMY_POOL_RECYCLE'] = config.SQLALCHEMY_POOL_RECYCLE
app.config['SQLALCHEMY_POOL_TIMEOUT'] = config.SQLALCHEMY_POOL_TIMEOUT

# 初始化数据库和Marshmallow
db.init_app(app)
ma.init_app(app)

# 初始化Agent
agent = HighwayAPIAgent()

# 审计系统新增
import uuid
from datetime import datetime
import json
from typing import Dict

# ==================== 审计辅助函数 ====================
# 响应体最大长度（适配数据库TEXT字段，约64KB）
MAX_RESPONSE_BODY_LENGTH = 60000
MAX_ERROR_MESSAGE_LENGTH = 2000

def _truncate_for_audit(data: any, max_length: int = MAX_RESPONSE_BODY_LENGTH) -> str:
    """
    将数据截断到适合审计存储的长度
    对于大型响应，只保存摘要信息
    """
    if data is None:
        return None
    
    try:
        if isinstance(data, str):
            json_str = data
        else:
            json_str = json.dumps(data, ensure_ascii=False, default=str)
        
        if len(json_str) <= max_length:
            return json_str
        
        # 超过长度限制，创建摘要
        if isinstance(data, dict):
            summary = {
                '_truncated': True,
                '_original_length': len(json_str),
                'success': data.get('success'),
                'count': data.get('count'),
                'total': data.get('total'),
                'execution_type': data.get('execution_type'),
            }
            # 如果有data字段且是列表，记录数量
            if 'data' in data and isinstance(data['data'], list):
                summary['data_count'] = len(data['data'])
            if 'error' in data:
                summary['error'] = str(data['error'])[:500]
            if 'message' in data:
                summary['message'] = str(data['message'])[:500]
            return json.dumps(summary, ensure_ascii=False)
        else:
            # 对于非字典类型，直接截断
            return json_str[:max_length - 50] + '... [TRUNCATED]'
    except Exception as e:
        return json.dumps({'_error': f'序列化失败: {str(e)}'})


def _safe_audit_commit(audit_log, db_session):
    """
    安全地提交审计记录，处理各种异常情况
    """
    try:
        db_session.commit()
        return True
    except Exception as e:
        print(f"[AUDIT ERROR] 提交审计记录失败: {e}")
        try:
            db_session.rollback()
        except:
            pass
        return False


def _safe_audit_update(audit_log, db_session, **kwargs):
    """
    安全地更新审计记录
    """
    try:
        # 先回滚任何未完成的事务
        try:
            db_session.rollback()
        except:
            pass
        
        # 重新获取审计记录（避免detached instance问题）
        if audit_log and audit_log.id:
            fresh_log = db_session.get(AuditLog, audit_log.id)
            if fresh_log:
                for key, value in kwargs.items():
                    if key == 'response_body' and value:
                        # 确保response_body被截断
                        value = _truncate_for_audit(value)
                    if key == 'error_message' and value and len(str(value)) > MAX_ERROR_MESSAGE_LENGTH:
                        value = str(value)[:MAX_ERROR_MESSAGE_LENGTH] + '...[TRUNCATED]'
                    setattr(fresh_log, key, value)
                db_session.commit()
                return True
    except Exception as e:
        print(f"[AUDIT ERROR] 更新审计记录失败: {e}")
        try:
            db_session.rollback()
        except:
            pass
    return False


# ==================== 全局审计中间件 ====================
# 已经有独立审计逻辑的API（中间件跳过，避免重复记录）
SELF_AUDITED_APIS = {
    '/api/agent/query',      # 有详细的AGENT_QUERY审计
    '/api/ai/sql',           # 有详细的AI_SQL_QUERY审计
}

# 不需要审计的路径前缀（Dashboard、审计系统自身、静态资源等）
EXCLUDED_PREFIXES = (
    '/api/audit/',           # 审计系统自身的API
    '/dashboard',            # Dashboard页面
    '/static/',              # 静态资源
    '/_debug_toolbar/',      # 调试工具栏
)

# 不需要审计的完整路径（页面渲染、健康检查等）
EXCLUDED_PATHS = {
    '/',                     # 首页
    '/truck-agent',          # 页面
    '/old-index',            # 页面
    '/workflow-agent',       # 页面
    '/data-synthesis',       # 页面
    '/dgm-generation',       # 页面
    '/api/health',           # 健康检查（频繁调用）
    '/api/list',             # API列表（Dashboard用）
    '/api/test/connection',  # 连接测试
}


@app.before_request
def global_audit_before_request():
    """请求前：创建审计记录"""
    # 跳过非API请求
    if not request.path.startswith('/api/'):
        return
    
    # 跳过已有独立审计的API
    if request.path in SELF_AUDITED_APIS:
        return
    
    # 跳过排除的路径前缀
    if request.path.startswith(EXCLUDED_PREFIXES):
        return
    
    # 跳过排除的完整路径
    if request.path in EXCLUDED_PATHS:
        return
    
    # 跳过OPTIONS请求（CORS预检）
    if request.method == 'OPTIONS':
        return
    
    try:
        trace_id = request.headers.get('X-Trace-ID', str(uuid.uuid4()))
        
        # 获取请求体（对于POST/PUT请求）
        request_body = None
        if request.method in ('POST', 'PUT', 'PATCH'):
            try:
                if request.is_json:
                    request_body = json.dumps(request.get_json(silent=True) or {})
                    # 截断过长的请求体
                    if len(request_body) > 10000:
                        request_body = request_body[:10000] + '...[TRUNCATED]'
            except:
                pass
        
        # 获取请求参数（对于GET请求）
        request_params = None
        if request.args:
            request_params = json.dumps(dict(request.args))
        
        audit_log = AuditLog(
            trace_id=trace_id,
            parent_trace_id=request.headers.get('X-Parent-Trace-ID'),
            operation_type='API_CALL',
            api_endpoint=request.path,
            http_method=request.method,
            request_params=request_params,
            request_body=request_body,
            client_ip=request.remote_addr,
            server_ip=request.host,
            user_agent=request.user_agent.string[:500] if request.user_agent and request.user_agent.string else None,
            user_id=request.headers.get('X-User-ID'),
            session_id=request.headers.get('X-Session-ID'),
            created_at=datetime.now()
        )
        
        # 尝试从API Key识别用户
        api_key = request.headers.get('X-API-Key')
        if api_key:
            audit_log.user_id = f"api_key:{api_key[:8]}..."
        
        db.session.add(audit_log)
        db.session.commit()
        
        # 存储到请求上下文，供after_request使用
        request._audit_log_id = audit_log.id
        request._audit_start_time = datetime.now()
        request._audit_trace_id = trace_id
        
    except Exception as e:
        print(f"[AUDIT WARNING] 全局审计before_request失败: {e}")
        try:
            db.session.rollback()
        except:
            pass


@app.after_request
def global_audit_after_request(response):
    """请求后：更新审计记录"""
    # 检查是否有审计记录需要更新
    audit_log_id = getattr(request, '_audit_log_id', None)
    if not audit_log_id:
        return response
    
    try:
        start_time = getattr(request, '_audit_start_time', datetime.now())
        end_time = datetime.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # 获取响应体摘要
        response_body = None
        try:
            if response.is_json:
                data = response.get_json(silent=True)
                if data:
                    # 只保存摘要，不保存完整数据
                    response_body = json.dumps({
                        'success': data.get('success'),
                        'count': data.get('count'),
                        'total': data.get('total'),
                        'data_count': len(data.get('data', [])) if isinstance(data.get('data'), list) else None,
                        'error': str(data.get('error', ''))[:200] if data.get('error') else None
                    }, ensure_ascii=False)
        except:
            pass
        
        # 更新审计记录
        db.session.rollback()  # 先回滚任何未完成的事务
        fresh_log = db.session.get(AuditLog, audit_log_id)
        if fresh_log:
            fresh_log.response_status = response.status_code
            fresh_log.response_body = response_body
            fresh_log.response_time_ms = response_time_ms
            fresh_log.is_success = 200 <= response.status_code < 400
            fresh_log.ended_at = end_time
            db.session.commit()
        
    except Exception as e:
        print(f"[AUDIT WARNING] 全局审计after_request失败: {e}")
        try:
            db.session.rollback()
        except:
            pass
    
    return response


@app.route("/data-synthesis", methods=["GET"])
def data_synthesis_page():
    """数据合成 - 门架交易生成页面"""
    return render_template('data_synthesis.html')


@app.route("/dgm-generation", methods=["GET"])
def dgm_generation_page():
    """DGM大模型数据生成页面"""
    return render_template('dgm_generation.html')


@app.route("/api/generate/gantry", methods=["GET", "POST"])
def api_generate_gantry():
    """统一的门架数据生成服务。

    支持三种调用方式:
    - GET:  /api/generate/gantry?method=rule&count=3
    - POST: JSON {"method": "rule"|"model"|"dgm", "count": 3}
    
    方法说明:
    - rule: 基于规则的生成（快速，但质量一般）
    - model: 基于CTGAN模型的生成（质量较好）
    - dgm: 基于DGM框架的生成（最高质量，包含评估）
    """

    # 解析 method / count
    if request.method == "GET":
        method = (request.args.get("method") or "rule").lower()
        count_raw = request.args.get("count", "1")
    else:
        data = request.get_json(silent=True) or {}
        method = (data.get("method") or "rule").lower()
        count_raw = data.get("count", 1)

    try:
        count = int(count_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "count must be an integer"}), 400

    if count <= 0:
        return jsonify({"error": "count must be > 0"}), 400

    if method == "rule":
        records = [generate_rule_based_gantry_transaction() for _ in range(count)]
    elif method == "model":
        records = generate_model_based_gantry(count)
    elif method == "dgm":
        # DGM方法：生成高质量数据
        records = generate_dgm_gantry(count=count, auto_init=True)
    else:
        return jsonify({"error": f"unknown method: {method}, expected 'rule', 'model', or 'dgm'"}), 400

    return jsonify(records)

# 货车车型常量
TRUCK_CLASSES = ('11', '12', '13', '14', '15', '16')

def require_api_key(f):
    """
    API Key认证装饰器
    用于保护原始数据接口，要求请求头中包含有效的API Key
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not config.ENABLE_AUTH:
            return f(*args, **kwargs)
        
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': '未提供API Key',
                'message': '访问此接口需要在请求头中提供 X-API-Key'
            }), 401
        
        if api_key not in config.API_KEYS:
            return jsonify({
                'success': False,
                'error': 'API Key无效',
                'message': '提供的API Key无效或已过期'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

# ==================== 首页和Agent ====================

@app.route('/')
def index():
    """首页 - 货车智能Agent"""
    return render_template('truck_agent.html')

@app.route('/truck-agent')
def truck_agent():
    """货车数据分析Agent页面（兼容旧路由）"""
    return render_template('truck_agent.html')

@app.route('/old-index')
def old_index():
    """旧版SQL查询页面（保留）"""
    return render_template('index.html')

@app.route('/workflow-agent')
def workflow_agent():
    """工作流和智能Agent页面"""
    return render_template('workflow_agent.html')

@app.route('/api/agent/query', methods=['POST'])
def agent_query():
    """统一Agent查询接口 - 自动决策API推荐或工作流编排
    集成行为审计功能（已修复响应体过长问题）
    """
    audit_log = None
    audit_log_id = None
    start_time = datetime.now()
    trace_id = request.headers.get('X-Trace-ID', str(uuid.uuid4()))
    
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        source = data.get('source', 'input')  # 默认为输入框输入
        
        if not user_query:
            return jsonify({'error': '请提供查询描述'}), 400
        
        # ==================== 审计功能开始 ====================
        try:
            audit_log = AuditLog(
                trace_id=trace_id,
                parent_trace_id=request.headers.get('X-Parent-Trace-ID'),
                operation_type='AGENT_QUERY',
                api_endpoint='/api/agent/query',
                http_method='POST',
                request_body=json.dumps({'query': user_query[:1000]}),  # 限制查询长度
                client_ip=request.remote_addr,
                server_ip=request.host,
                user_agent=request.user_agent.string[:500] if request.user_agent.string else None,
                user_id=request.headers.get('X-User-ID'),
                session_id=request.headers.get('X-Session-ID'),
                created_at=start_time
            )
            
            # 尝试从API Key识别用户
            api_key = request.headers.get('X-API-Key')
            if api_key:
                audit_log.user_id = f"api_key:{api_key[:8]}..."
            
            db.session.add(audit_log)
            db.session.commit()
            audit_log_id = audit_log.id
        except Exception as audit_err:
            print(f"[AUDIT WARNING] 创建审计记录失败: {audit_err}")
            try:
                db.session.rollback()
            except:
                pass
        # ==================== 审计功能结束 ====================
        
        # 使用统一Agent处理（支持API推荐和工作流）
        response = enhanced_agent.process_query(user_query, request.host_url, source, trace_id=trace_id)
        
        # ==================== 更新审计记录 ====================
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if audit_log_id:
            # 构建响应摘要（避免存储完整响应）
            response_summary = {
                'execution_type': response.get('execution_type', 'unknown'),
                'success': response.get('success', False),
            }
            
            # 记录执行类型和调用数量
            if response.get('execution_type') == 'api':
                recommendations = response.get('recommendations', [])
                response_summary['api_recommendations'] = len(recommendations)
                response_summary['recommended_tags'] = [r.get('tag') for r in recommendations[:5]]
            elif response.get('execution_type') == 'workflow':
                api_calls = response.get('api_calls', [])
                response_summary['api_calls_count'] = len(api_calls)
                response_summary['scenario_name'] = response.get('scenario_name')
                # 如果有数据结果，只记录数量
                if 'data' in response and isinstance(response['data'], list):
                    response_summary['data_count'] = len(response['data'])
                if 'count' in response:
                    response_summary['count'] = response['count']
                if 'total' in response:
                    response_summary['total'] = response['total']
            
            _safe_audit_update(
                audit_log, db.session,
                response_status=200,
                response_body=response_summary,  # 使用摘要而非完整响应
                response_time_ms=duration_ms,
                ended_at=end_time,
                is_success=response.get('success', False),
                operation_type='AGENT_QUERY_COMPLETE'
            )
        # ==================== 审计更新完成 ====================
        
        # 在响应中添加审计追踪信息
        response['audit_trace'] = {
            'trace_id': trace_id,
            'execution_type': response.get('execution_type', 'unknown'),
            'duration_ms': duration_ms,
            'timestamp': end_time.isoformat(),
            'success': response.get('success', False)
        }
        
        # 添加追踪ID到响应头
        response_obj = jsonify(response)
        response_obj.headers['X-Trace-ID'] = trace_id
        return response_obj
        
    except Exception as e:
        # 错误处理：更新审计记录
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if audit_log_id:
            _safe_audit_update(
                audit_log, db.session,
                response_status=500,
                response_body={'error': str(e)[:500]},
                response_time_ms=duration_ms,
                ended_at=end_time,
                is_success=False,
                error_message=str(e)[:MAX_ERROR_MESSAGE_LENGTH],
                operation_type='AGENT_QUERY_ERROR'
            )
        
        return jsonify({'error': str(e)}), 500


def _summarize_agent_result(result: Dict) -> Dict:
    """总结Agent结果用于审计记录"""
    summary = {
        'execution_type': result.get('execution_type'),
        'success': result.get('success', False)
    }
    
    if result.get('execution_type') == 'api':
        recommendations = result.get('recommendations', [])
        summary['api_recommendations'] = len(recommendations)
        summary['recommended_tags'] = [r.get('tag') for r in recommendations]
    
    elif result.get('execution_type') == 'workflow':
        api_calls = result.get('api_calls', [])
        summary['api_calls'] = len(api_calls)
        summary['scenario_name'] = result.get('scenario_name')
    
    return summary


@app.route('/api/agent/smart-query', methods=['POST'])
def smart_agent_query():
    """统一Agent查询接口（别名，兼容旧代码）"""
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        
        if not user_query:
            return jsonify({
                'success': False,
                'error': '请提供查询描述'
            }), 400
        
        # 生成追踪ID
        trace_id = request.headers.get('X-Trace-ID', str(uuid.uuid4()))
        
        # 使用统一Agent处理
        response = enhanced_agent.process_query(user_query, request.host_url, trace_id=trace_id)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'智能Agent处理失败: {str(e)}'
        }), 500

@app.route('/api/ai/sql', methods=['POST'])
def ai_sql_query():
    """AI SQL查询接口 - 自然语言转SQL并执行
    集成审计功能（已修复响应体过长问题）
    """
    # ==================== 审计功能开始 ====================
    trace_id = request.headers.get('X-Trace-ID', str(uuid.uuid4()))
    start_time = datetime.now()
    audit_log = None
    
    try:
        audit_log = AuditLog(
            trace_id=trace_id,
            operation_type='AI_SQL_QUERY',
            api_endpoint='/api/ai/sql',
            http_method='POST',
            client_ip=request.remote_addr,
            user_agent=request.user_agent.string[:500] if request.user_agent.string else None,
            created_at=start_time
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        print(f"[AUDIT WARNING] 创建审计记录失败: {e}")
        try:
            db.session.rollback()
        except:
            pass
    # ==================== 审计功能结束 ====================
    
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        
        if not user_query:
            if audit_log:
                _safe_audit_update(
                    audit_log, db.session,
                    response_status=400,
                    error_message='请提供查询描述',
                    ended_at=datetime.now()
                )
            return jsonify({'success': False, 'error': '请提供查询描述'}), 400
        
        if audit_log:
            _safe_audit_update(
                audit_log, db.session,
                request_body=json.dumps({'query': user_query[:1000]})
            )
        
        # 使用AI SQL Agent处理查询
        response = ai_sql_agent.process_query(user_query, request.host_url)
        
        # 更新审计记录
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if audit_log:
            # 构建响应摘要
            response_summary = {
                'success': response.get('success', False),
                'has_sql': 'sql' in response,
                'has_data': 'data' in response,
            }
            if 'data' in response and isinstance(response['data'], list):
                response_summary['data_count'] = len(response['data'])
            
            _safe_audit_update(
                audit_log, db.session,
                response_status=200,
                response_body=response_summary,
                response_time_ms=duration_ms,
                ended_at=end_time,
                is_success=response.get('success', False)
            )
        
        # 添加审计追踪
        response['audit_trace_id'] = trace_id
        return jsonify(response)
        
    except Exception as e:
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if audit_log:
            _safe_audit_update(
                audit_log, db.session,
                response_status=500,
                response_body={'error': str(e)[:500]},
                response_time_ms=duration_ms,
                ended_at=end_time,
                is_success=False,
                error_message=str(e)[:MAX_ERROR_MESSAGE_LENGTH]
            )
        
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/sql/generate', methods=['POST'])
def ai_sql_generate():
    """AI SQL生成接口 - 只生成SQL不执行"""
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        
        if not user_query:
            return jsonify({
                'success': False,
                'error': '请提供查询描述'
            }), 400
        
        # 只生成SQL
        response = ai_sql_agent.generate_sql(user_query)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== 系统状态API ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    try:
        # 测试数据库连接
        sections_count = db.session.query(Section).count()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'database': 'connected',
            'sections_count': sections_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ==================== 路段相关API ====================

@app.route('/api/sections', methods=['GET'])
@require_api_key
def get_sections():
    """获取所有路段信息（需要认证）"""
    try:
        sections = Section.query.all()
        return jsonify({
            'success': True,
            'data': sections_schema.dump(sections),
            'count': len(sections)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sections/<section_id>', methods=['GET'])
@require_api_key
def get_section(section_id):
    """获取指定路段信息（需要认证）"""
    try:
        section = Section.query.filter_by(section_id=section_id).first()
        
        if section:
            return jsonify({
                'success': True,
                'data': section_schema.dump(section)
            })
        else:
            return jsonify({'success': False, 'error': '路段不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 收费站相关API ====================

@app.route('/api/toll-stations', methods=['GET'])
@require_api_key
def get_toll_stations():
    """获取收费站信息，支持按路段筛选（需要认证）"""
    try:
        section_id = request.args.get('section_id')
        station_type = request.args.get('station_type')
        
        query = TollStation.query
        
        if section_id:
            query = query.filter_by(section_id=section_id)
        
        if station_type:
            query = query.filter_by(station_type=station_type)
        
        stations = query.all()
        
        return jsonify({
            'success': True,
            'data': toll_stations_schema.dump(stations),
            'count': len(stations)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/toll-stations/<station_id>', methods=['GET'])
@require_api_key
def get_toll_station(station_id):
    """获取指定收费站信息（需要认证）"""
    try:
        station = TollStation.query.filter_by(toll_station_id=station_id).first()
        
        if station:
            return jsonify({
                'success': True,
                'data': toll_station_schema.dump(station)
            })
        else:
            return jsonify({'success': False, 'error': '收费站不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 门架相关API ====================

@app.route('/api/gantries', methods=['GET'])
@require_api_key
def get_gantries():
    """获取门架信息，支持按路段筛选（需要认证）"""
    try:
        section_id = request.args.get('section_id')
        gantry_type = request.args.get('gantry_type')
        
        query = Gantry.query
        
        if section_id:
            query = query.filter_by(section_id=section_id)
        
        if gantry_type:
            query = query.filter_by(gantry_type=gantry_type)
        
        gantries = query.all()
        
        return jsonify({
            'success': True,
            'data': gantries_schema.dump(gantries),
            'count': len(gantries)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gantries/<gantry_id>', methods=['GET'])
@require_api_key
def get_gantry(gantry_id):
    """获取指定门架信息（需要认证）"""
    try:
        gantry = Gantry.query.filter_by(gantry_id=gantry_id).first()
        
        if gantry:
            return jsonify({
                'success': True,
                'data': gantry_schema.dump(gantry)
            })
        else:
            return jsonify({'success': False, 'error': '门架不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 交易相关API ====================

@app.route('/api/transactions/entrance', methods=['GET'])
@require_api_key
def get_entrance_transactions():
    """获取入口交易记录（需要认证）"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        vehicle_class = request.args.get('vehicle_class')
        limit = request.args.get('limit', type=int)  # 去掉默认限制
        offset = request.args.get('offset', 0, type=int)
        
        query = EntranceTransaction.query
        
        if section_id:
            query = query.filter_by(section_id=section_id)
        
        if start_date:
            query = query.filter(EntranceTransaction.entrance_time >= start_date)
        
        if end_date:
            query = query.filter(EntranceTransaction.entrance_time <= end_date)
        
        if vehicle_class:
            query = query.filter_by(vehicle_class=vehicle_class)
        
        total = query.count()
        
        # 只有指定limit时才限制数量
        query = query.order_by(desc(EntranceTransaction.entrance_time))
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        transactions = query.all()
        
        return jsonify({
            'success': True,
            'data': entrance_transactions_schema.dump(transactions),
            'count': len(transactions),
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/exit', methods=['GET'])
@require_api_key
def get_exit_transactions():
    """获取出口交易记录（需要认证）"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        vehicle_class = request.args.get('vehicle_class')
        limit = request.args.get('limit', type=int)  # 去掉默认限制
        offset = request.args.get('offset', 0, type=int)
        
        query = ExitTransaction.query
        
        if section_id:
            query = query.filter_by(section_id=section_id)
        
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        if vehicle_class:
            query = query.filter_by(vehicle_class=vehicle_class)
        
        total = query.count()
        
        # 只有指定limit时才限制数量
        query = query.order_by(desc(ExitTransaction.exit_time))
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        transactions = query.all()
        
        return jsonify({
            'success': True,
            'data': exit_transactions_schema.dump(transactions),
            'count': len(transactions),
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/gantry', methods=['GET'])
@require_api_key
def get_gantry_transactions():
    """获取门架交易记录（需要认证）"""
    try:
        gantry_id = request.args.get('gantry_id')
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', type=int)  # 去掉默认限制
        offset = request.args.get('offset', 0, type=int)
        
        query = GantryTransaction.query
        
        if gantry_id:
            query = query.filter_by(gantry_id=gantry_id)
        
        if section_id:
            query = query.filter_by(section_id=section_id)
        
        if start_date:
            query = query.filter(GantryTransaction.transaction_time >= start_date)
        
        if end_date:
            query = query.filter(GantryTransaction.transaction_time <= end_date)
        
        total = query.count()
        
        # 只有指定limit时才限制数量
        query = query.order_by(desc(GantryTransaction.transaction_time))
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        transactions = query.all()
        
        return jsonify({
            'success': True,
            'data': gantry_transactions_schema.dump(transactions),
            'count': len(transactions),
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 统计分析API ====================

@app.route('/api/statistics/traffic-flow', methods=['GET'])
def get_traffic_flow():
    """获取交通流量统计"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = db.session.query(
            func.date(EntranceTransaction.entrance_time).label('date'),
            func.count().label('count'),
            EntranceTransaction.vehicle_class
        )
        
        if section_id:
            query = query.filter(EntranceTransaction.section_id == section_id)
        
        if start_date:
            query = query.filter(EntranceTransaction.entrance_time >= start_date)
        
        if end_date:
            query = query.filter(EntranceTransaction.entrance_time <= end_date)
        
        results = query.group_by(
            func.date(EntranceTransaction.entrance_time),
            EntranceTransaction.vehicle_class
        ).order_by(desc('date')).all()
        
        stats = [{'date': str(r.date), 'count': r.count, 'vehicle_class': r.vehicle_class} for r in results]
        
        return jsonify({
            'success': True,
            'data': stats,
            'count': len(stats)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/statistics/revenue', methods=['GET'])
def get_revenue_statistics():
    """获取收费统计"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = db.session.query(
            func.date(ExitTransaction.exit_time).label('date'),
            func.count().label('transaction_count'),
            func.sum(ExitTransaction.toll_money).label('total_toll'),
            func.sum(ExitTransaction.real_money).label('total_real_money'),
            func.avg(ExitTransaction.toll_money).label('avg_toll')
        )
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(func.date(ExitTransaction.exit_time)).order_by(desc('date')).all()
        
        stats = [{
            'date': str(r.date),
            'transaction_count': r.transaction_count,
            'total_toll': float(r.total_toll) if r.total_toll else 0,
            'total_real_money': float(r.total_real_money) if r.total_real_money else 0,
            'avg_toll': float(r.avg_toll) if r.avg_toll else 0
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': stats,
            'count': len(stats)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/statistics/vehicle-distribution', methods=['GET'])
def get_vehicle_distribution():
    """获取车型分布统计"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = db.session.query(
            EntranceTransaction.vehicle_class,
            func.count().label('count')
        )
        
        if section_id:
            query = query.filter(EntranceTransaction.section_id == section_id)
        
        if start_date:
            query = query.filter(EntranceTransaction.entrance_time >= start_date)
        
        if end_date:
            query = query.filter(EntranceTransaction.entrance_time <= end_date)
        
        results = query.group_by(EntranceTransaction.vehicle_class).order_by(desc('count')).all()
        
        total_count = sum([r.count for r in results])
        
        stats = [{
            'vehicle_class': r.vehicle_class,
            'count': r.count,
            'percentage': round(r.count * 100.0 / total_count, 2) if total_count > 0 else 0
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': stats,
            'count': len(stats)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 货车分析API（标签API）====================

@app.route('/api/analytics/truck/hourly-flow', methods=['GET'])
def get_truck_hourly_flow():
    """路段货车小时流量 - 统计每个路段每小时通过的货车数量"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 构建查询（按照设计文档使用EntranceTransaction）
        query = db.session.query(
            EntranceTransaction.section_id,
            Section.section_name,
            db.func.date_format(EntranceTransaction.entrance_time, '%Y-%m-%d %H').label('hour'),
            db.func.count(EntranceTransaction.entrance_transaction_id).label('truck_count')
        ).join(Section, EntranceTransaction.section_id == Section.section_id)\
         .filter(EntranceTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']))  # 货车类型
        
        if section_id:
            query = query.filter(EntranceTransaction.section_id == section_id)
        if start_date:
            query = query.filter(EntranceTransaction.entrance_time >= start_date)
        if end_date:
            query = query.filter(EntranceTransaction.entrance_time <= end_date)
        
        results = query.group_by(EntranceTransaction.section_id, 'hour').all()
        
        # 差分隐私参数（记录级DP，敏感度Δf=1，对计数加拉普拉斯噪声）
        epsilon = 1.0
        scale = 1.0 / epsilon  # Laplace(0, 1/epsilon)
        
        
        def laplace_noise(scale_value: float) -> float:
            """生成拉普拉斯噪声（中心0，尺度scale_value）"""
            u = random.random() - 0.5  # (-0.5, 0.5)
            return -scale_value * math.copysign(math.log(1 - 2 * abs(u)), u)
        
        data = []
        for r in results:
            true_count = int(r.truck_count)
            noisy = true_count + laplace_noise(scale)
            # 计数截断为非负整数
            noisy_count = max(0, int(round(noisy)))
            
            data.append({
                'section_id': r.section_id,
                'section_name': r.section_name,
                'hour': r.hour,
                'truck_count_dp': noisy_count,
                'epsilon': epsilon,
                'dp_method': 'Laplace'
            })
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'category': '📊 流量统计类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/avg-travel-time', methods=['GET'])
def get_truck_avg_travel_time():
    """路段平均通行时间 - 统计货车的平均通行时间（分钟）"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 构建查询（通过entrance和exit关联计算通行时间）
        query = db.session.query(
            ExitTransaction.section_id,
            db.func.avg(
                db.func.timestampdiff(
                    db.text('MINUTE'),
                    EntranceTransaction.entrance_time,
                    ExitTransaction.exit_time
                )
            ).label('avg_travel_time_minutes'),
            db.func.count(ExitTransaction.exit_transaction_id).label('sample_count')
        ).join(
            EntranceTransaction,
            db.and_(
                ExitTransaction.pass_id == EntranceTransaction.pass_id,
                ExitTransaction.section_id == EntranceTransaction.section_id
            )
        ).filter(ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']))
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(ExitTransaction.section_id).all()
        
        data = [{
            'section_id': r.section_id,
            'avg_travel_time_minutes': float(r.avg_travel_time_minutes) if r.avg_travel_time_minutes else 0.0,
            'sample_count': int(r.sample_count)
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '⏱️ 通行时效类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/avg-toll-fee', methods=['GET'])
def get_truck_avg_toll_fee():
    """路段平均通行费 - 统计货车的平均通行费用（元）"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 按照设计文档使用real_money字段
        query = db.session.query(
            ExitTransaction.section_id,
            db.func.avg(ExitTransaction.real_money).label('avg_toll_fee'),
            db.func.count(ExitTransaction.exit_transaction_id).label('transaction_count')
        ).filter(ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']))
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(ExitTransaction.section_id).all()
        
        data = [{
            'section_id': r.section_id,
            'avg_toll_fee': float(r.avg_toll_fee) if r.avg_toll_fee else 0.0,
            'transaction_count': int(r.transaction_count)
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '💰 费用分析类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/congestion-index', methods=['GET'])
def get_truck_congestion_index():
    """路段拥堵指数 - 通过货车流量与车道数比值评估拥堵程度"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 子查询1：计算每个路段的平均车道数（按门架去重）
        lanes_subquery = db.session.query(
            Gantry.section_id,
            db.func.avg(db.func.cast(Gantry.lane_count, db.Numeric)).label('avg_lanes')
        ).group_by(Gantry.section_id).subquery()
        
        # 主查询：统计货车数量并关联平均车道数
        query = db.session.query(
            Gantry.section_id,
            db.func.count(
                db.case(
                    (GantryTransaction.vehicle_type.in_(['11', '12', '13', '14', '15', '16']), GantryTransaction.gantry_transaction_id),
                    else_=None
                )
            ).label('truck_count'),
            lanes_subquery.c.avg_lanes
        ).join(Gantry, GantryTransaction.gantry_id == Gantry.gantry_id)\
         .outerjoin(lanes_subquery, Gantry.section_id == lanes_subquery.c.section_id)
        
        if section_id:
            query = query.filter(Gantry.section_id == section_id)
        if start_date:
            query = query.filter(GantryTransaction.transaction_time >= start_date)
        if end_date:
            query = query.filter(GantryTransaction.transaction_time <= end_date)
        
        results = query.group_by(Gantry.section_id, lanes_subquery.c.avg_lanes).all()
        
        data = [{
            'section_id': r.section_id,
            'truck_count': int(r.truck_count or 0),
            'avg_lanes': round(float(r.avg_lanes), 1) if r.avg_lanes else 4.0,
            'congestion_index': round(float(r.truck_count or 0) / float(r.avg_lanes if r.avg_lanes else 4), 2)
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '📊 流量统计类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/exit-hourly-flow', methods=['GET'])
def get_truck_exit_hourly_flow():
    """路段货车小时出口流量 - 统计每个路段每小时出口的货车数量"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 构建查询（按路段和小时分组）
        query = db.session.query(
            ExitTransaction.section_id,
            db.func.date_format(ExitTransaction.exit_time, '%Y-%m-%d %H').label('hour'),
            db.func.count(ExitTransaction.exit_transaction_id).label('truck_count'),
            db.func.avg(ExitTransaction.real_money).label('avg_toll')
        ).filter(ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']))  # 货车类型
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(ExitTransaction.section_id, 'hour').all()
        
        data = [{
            'section_id': r.section_id,
            'hour': r.hour,
            'truck_count': int(r.truck_count),
            'avg_toll': float(r.avg_toll) if r.avg_toll else 0
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'category': '📊 流量统计类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/exit-hourly-flow-k-anonymized', methods=['GET'])
def get_truck_exit_hourly_flow_k_anonymized():
    """
    路段货车小时出口流量（k-匿名保护版本）
    
    基于KACA (K-Anonymity Clustering Algorithm) 算法进行k-匿名处理：
    1. 获取原始出口交易记录
    2. 特征提取：将准标识符转换为数值特征
    3. 聚类：使用K-Means将记录聚类，确保每个聚类>=k
    4. 泛化：对每个聚类内的准标识符进行自适应泛化
    5. 聚合：计算每个等价类的统计信息
    """
    try:
        from kaca_anonymizer import KACAAnonymizer
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        k_value = int(request.args.get('k', 5))  # 默认 k=5
        
        # 步骤1: 查询原始交易记录（货车）
        query = ExitTransaction.query.filter(
            ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16'])
        )
        
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        # 获取原始记录
        raw_records = query.all()
        
        if not raw_records:
            return jsonify({
                'success': True,
                'data': [],
                'count': 0,
                'category': '📊 流量统计类（k-匿名保护）',
                'message': '没有找到符合条件的记录'
            })
        
        # 步骤2-5: 使用KACA算法进行k-匿名处理（记录级输出）
        anonymizer = KACAAnonymizer(k_value=k_value)
        result = anonymizer.anonymize_exit_transactions(raw_records)
        
        records = result['records']
        suppressed_count = result['suppressed_count']
        total_records = result['total_records']
        equivalence_classes = result['equivalence_classes']
        
        # 按区域和时段排序
        records.sort(key=lambda x: (x.get('section_region', ''), x.get('time_period', '')))
        
        return jsonify({
            'success': True,
            'data': records,
            'count': len(records),
            'category': '🔒 记录级k-匿名数据（KACA）',
            'data_source': '出口交易数据（ExitTransaction）',
            'privacy_protection': {
                'method': 'KACA (K-Anonymity Clustering Algorithm)',
                'algorithm': 'KACA',
                'k_value': k_value,
                'input_source': '原始出口交易记录',
                'quasi_identifiers': ['section_id', 'exit_time'],
                'clustering': {
                    'algorithm': 'K-Means',
                    'equivalence_classes': equivalence_classes,
                    'description': '基于聚类的自适应泛化，保证每个等价类大小≥k'
                },
                'generalization': {
                    'geographic': 'cluster内section_id公共前缀 → section_region',
                    'temporal': 'cluster内时间范围 → time_period'
                },
                'statistics': {
                    'total_records': total_records,
                    'anonymized_records': len(records),
                    'equivalence_classes': equivalence_classes,
                    'suppressed_records': suppressed_count,
                    'retention_rate': round((total_records - suppressed_count) / total_records * 100, 2) if total_records > 0 else 0
                },
                'description': f'使用KACA算法进行聚类和泛化，输出记录级k匿名数据，每个(section_region, time_period)组合至少包含 {k_value} 条原始记录'
            }
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"KACA算法错误: {error_detail}")
        return jsonify({'success': False, 'error': str(e), 'detail': error_detail}), 500

@app.route('/api/analytics/truck/overweight-rate', methods=['GET'])
def get_truck_overweight_rate():
    """
    路段超载货车比例 - 统计超载货车的比例，反映合规风险
    
    数据脱敏: 对 section_id 字段进行掩码处理（保留首尾字符，中间用*替换）
    
    处理前: {"section_id": "G5615530120", ...}
    处理后: {"section_id": "G*********0", "section_id_masked": true, ...}
    """
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 统计超载货车比例（total_weight > total_limit为超载）
        # 过滤掉total_weight或total_limit为NULL、空字符串、0的无效记录
        query = db.session.query(
            ExitTransaction.section_id,
            db.func.count(ExitTransaction.exit_transaction_id).label('total_count'),
            db.func.sum(
                db.case(
                    (db.func.cast(ExitTransaction.total_weight, db.Numeric) > db.func.cast(ExitTransaction.total_limit, db.Numeric), 1),
                    else_=0
                )
            ).label('overweight_count')
        ).filter(
            ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']),
            ExitTransaction.total_weight.isnot(None),
            ExitTransaction.total_weight != '',
            ExitTransaction.total_weight != '0',
            ExitTransaction.total_limit.isnot(None),
            ExitTransaction.total_limit != '',
            ExitTransaction.total_limit != '0'
        )
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(ExitTransaction.section_id).all()
        
        # 掩码函数：对section_id进行脱敏处理
        def mask_section_id(section_id):
            """
            掩码脱敏：保留首尾字符，中间用*替换
            例如：G0001-001 → G****-**1
            """
            if not section_id or len(section_id) < 3:
                return '***'
            return section_id[0] + '*' * (len(section_id) - 2) + section_id[-1]
        
        data = [{
            'section_id': mask_section_id(r.section_id),  # 掩码脱敏
            'section_id_masked': True,  # 标记已脱敏
            'total_count': int(r.total_count),
            'overweight_count': int(r.overweight_count or 0),
            'overweight_rate': round(float(r.overweight_count or 0) / float(r.total_count), 4) if r.total_count > 0 else 0,
            'overweight_percentage': round(float(r.overweight_count or 0) / float(r.total_count) * 100, 2) if r.total_count > 0 else 0
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '⚖️ 合规监测类',
            'data_masking': {
                'enabled': True,
                'method': '掩码(Masking)',
                'fields': ['section_id'],
                'description': '对路段ID进行掩码处理，保留首尾字符，中间用*替换'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/discount-rate', methods=['GET'])
def get_truck_discount_rate():
    """路段通行费优惠比例 - 统计享受通行费优惠的货车比例"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 统计优惠比例（按照设计文档使用discount_type字段）
        query = db.session.query(
            ExitTransaction.section_id,
            db.func.count(ExitTransaction.exit_transaction_id).label('total_count'),
            db.func.sum(
                db.case(
                    (db.and_(
                        ExitTransaction.discount_type.isnot(None),
                        ExitTransaction.discount_type != ''
                    ), 1),
                    else_=0
                )
            ).label('discount_count')
        ).filter(ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']))
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(ExitTransaction.section_id).all()
        
        data = [{
            'section_id': r.section_id,
            'total_count': int(r.total_count),
            'discount_count': int(r.discount_count or 0),
            'discount_rate': round(float(r.discount_count or 0) / float(r.total_count), 4) if r.total_count > 0 else 0,
            'discount_percentage': round(float(r.discount_count or 0) / float(r.total_count) * 100, 2) if r.total_count > 0 else 0
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '💰 费用分析类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/peak-hours', methods=['GET'])
def get_truck_peak_hours():
    """路段货车高峰时段 - 识别货车流量最高的小时区间"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 按小时统计货车数量，找出高峰时段（按照设计文档使用EntranceTransaction）
        query = db.session.query(
            EntranceTransaction.section_id,
            db.func.date_format(EntranceTransaction.entrance_time, '%H').label('hour'),
            db.func.count(EntranceTransaction.entrance_transaction_id).label('truck_count')
        ).filter(EntranceTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']))
        
        if section_id:
            query = query.filter(EntranceTransaction.section_id == section_id)
        if start_date:
            query = query.filter(EntranceTransaction.entrance_time >= start_date)
        if end_date:
            query = query.filter(EntranceTransaction.entrance_time <= end_date)
        
        # 按路段和小时分组，按流量降序排序
        results = query.group_by(EntranceTransaction.section_id, 'hour')\
                      .order_by(EntranceTransaction.section_id, db.desc('truck_count'))\
                      .all()
        
        # 对每个路段只取前3个高峰时段
        section_peaks = {}
        for r in results:
            if r.section_id not in section_peaks:
                section_peaks[r.section_id] = []
            if len(section_peaks[r.section_id]) < 3:  # 每个路段最多3个高峰时段
                section_peaks[r.section_id].append({
                    'section_id': r.section_id,
                    'hour': r.hour,
                    'truck_count': int(r.truck_count)
                })
        
        # 展平结果
        data = []
        for peaks in section_peaks.values():
            data.extend(peaks)
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '📊 流量统计类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/avg-axle-count', methods=['GET'])
def get_truck_avg_axle_count():
    """路段货车平均轴数 - 统计货车的平均轴数，反映货车类型分布"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 过滤掉axis_count为NULL、空字符串、0的无效记录
        query = db.session.query(
            ExitTransaction.section_id,
            db.func.avg(db.func.cast(ExitTransaction.axis_count, db.Numeric)).label('avg_axle_count'),
            db.func.count(ExitTransaction.exit_transaction_id).label('sample_count')
        ).filter(
            ExitTransaction.vehicle_class.in_(['11', '12', '13', '14', '15', '16']),
            ExitTransaction.axis_count.isnot(None),
            ExitTransaction.axis_count != '',
            ExitTransaction.axis_count != '0'
        )
        
        if section_id:
            query = query.filter(ExitTransaction.section_id == section_id)
        if start_date:
            query = query.filter(ExitTransaction.exit_time >= start_date)
        if end_date:
            query = query.filter(ExitTransaction.exit_time <= end_date)
        
        results = query.group_by(ExitTransaction.section_id).all()
        
        data = [{
            'section_id': r.section_id,
            'avg_axle_count': round(float(r.avg_axle_count), 2) if r.avg_axle_count else 0.0,
            'sample_count': int(r.sample_count)
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '⚖️ 合规监测类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/lane-utilization', methods=['GET'])
def get_truck_lane_utilization():
    """路段车道利用率 - 统计货车流量与车道数的比值"""
    try:
        section_id = request.args.get('section_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 子查询：计算每个路段的平均车道数（按门架去重）
        lanes_subquery = db.session.query(
            Gantry.section_id,
            db.func.avg(db.func.cast(Gantry.lane_count, db.Numeric)).label('avg_lanes')
        ).group_by(Gantry.section_id).subquery()
        
        # 主查询：统计货车交易数量并关联平均车道数
        query = db.session.query(
            Gantry.section_id,
            db.func.count(GantryTransaction.gantry_transaction_id).label('total_transactions'),
            lanes_subquery.c.avg_lanes
        ).join(Gantry, GantryTransaction.gantry_id == Gantry.gantry_id)\
         .outerjoin(lanes_subquery, Gantry.section_id == lanes_subquery.c.section_id)\
         .filter(GantryTransaction.vehicle_type.in_(['11', '12', '13', '14', '15', '16']))
        
        if section_id:
            query = query.filter(Gantry.section_id == section_id)
        if start_date:
            query = query.filter(GantryTransaction.transaction_time >= start_date)
        if end_date:
            query = query.filter(GantryTransaction.transaction_time <= end_date)
        
        results = query.group_by(Gantry.section_id, lanes_subquery.c.avg_lanes).all()
        
        data = [{
            'section_id': r.section_id,
            'avg_lanes': round(float(r.avg_lanes), 1) if r.avg_lanes else 4.0,
            'total_transactions': int(r.total_transactions),
            'lane_utilization': round(float(r.total_transactions) / float(r.avg_lanes if r.avg_lanes else 4), 2)
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'category': '📊 流量统计类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/truck/toll-station-status', methods=['GET'])
def get_truck_toll_station_status():
    """路段收费站运行状态 - 查询收费站的运行状态"""
    try:
        section_id = request.args.get('section_id')
        
        query = db.session.query(
            TollStation.toll_station_id,
            TollStation.station_name,
            TollStation.section_id,
            TollStation.operation_status
        )
        
        if section_id:
            query = query.filter(TollStation.section_id == section_id)
        
        results = query.all()
        
        data = [{
            'toll_station_id': r.toll_station_id,
            'station_name': r.station_name,
            'section_id': r.section_id,
            'operation_status': r.operation_status,
            'status_text': '正常' if r.operation_status == '1' else '异常'
        } for r in results]
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'category': '📈 基础指标类'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 测试连接 ====================

@app.route('/api/test/connection', methods=['GET'])
def test_connection():
    """测试数据库连接"""
    try:
        # 执行一个简单的查询
        count = Section.query.count()
        return jsonify({
            'success': True,
            'message': '数据库连接正常',
            'section_count': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== DGM数据生成专用API ====================

@app.route('/api/dgm/initialize', methods=['POST'])
def dgm_initialize():
    """初始化DGM生成器
    
    POST /api/dgm/initialize
    {
        "real_data_limit": 300,
        "evaluation_limit": 1000,
        "use_discriminative": true
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        real_data_limit = data.get('real_data_limit', 300)
        evaluation_limit = data.get('evaluation_limit', 1000)
        use_discriminative = data.get('use_discriminative', True)
        
        api = get_dgm_api(use_discriminative=use_discriminative)
        result = api.initialize(
            real_data_limit=real_data_limit,
            evaluation_limit=evaluation_limit,
            use_database=True
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/dgm/generate', methods=['POST'])
def dgm_generate():
    """使用DGM生成器生成数据（包含完整评估）
    
    POST /api/dgm/generate
    {
        "count": 50,
        "verbose": false
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        count = data.get('count', 10)
        verbose = data.get('verbose', False)
        
        api = get_dgm_api()
        result = api.generate(count=count, verbose=verbose)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'samples': []
        }), 500


@app.route('/api/dgm/stats', methods=['GET'])
def dgm_stats():
    """获取DGM生成器学习到的统计信息
    
    GET /api/dgm/stats
    """
    try:
        api = get_dgm_api()
        result = api.get_stats()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/dgm/status', methods=['GET'])
def dgm_status():
    """获取DGM生成器状态
    
    GET /api/dgm/status
    """
    try:
        api = get_dgm_api()
        return jsonify({
            'status': 'success',
            'is_initialized': api.is_initialized,
            'use_discriminative': api.use_discriminative
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ==================== 多智能体协作 API ====================
# 注意：多智能体协作功能已集成到统一Agent中
# 通过 /api/agent/query 接口使用，系统会自动判断是API推荐还是多智能体协作


# ==================== 审计系统API ====================

@app.route('/api/audit/logs', methods=['GET'])
@require_api_key
def get_audit_logs():
    """获取审计日志（需要认证）"""
    try:
        # 分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # 过滤条件
        operation_type = request.args.get('operation_type')
        api_endpoint = request.args.get('api_endpoint')
        user_id = request.args.get('user_id')
        client_ip = request.args.get('client_ip')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        is_success = request.args.get('is_success')
        trace_id = request.args.get('trace_id')
        
        # 构建查询
        query = AuditLog.query
        
        if operation_type:
            query = query.filter(AuditLog.operation_type == operation_type)
        if api_endpoint:
            query = query.filter(AuditLog.api_endpoint.like(f'%{api_endpoint}%'))
        if user_id:
            query = query.filter(AuditLog.user_id.like(f'%{user_id}%'))
        if client_ip:
            query = query.filter(AuditLog.client_ip == client_ip)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        if is_success is not None:
            query = query.filter(AuditLog.is_success == (is_success.lower() == 'true'))
        if trace_id:
            query = query.filter(AuditLog.trace_id == trace_id)
        
        # 排序和分页
        pagination = query.order_by(desc(AuditLog.created_at))\
                         .paginate(page=page, per_page=per_page, error_out=False)
        
        logs = pagination.items
        
        return jsonify({
            'success': True,
            'data': audit_logs_schema.dump(logs),
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/trace/<trace_id>', methods=['GET'])
@require_api_key
def get_audit_trace(trace_id):
    """获取完整的调用链路"""
    try:
        # 获取指定trace的所有日志
        logs = AuditLog.query.filter(
            db.or_(
                AuditLog.trace_id == trace_id,
                AuditLog.parent_trace_id == trace_id
            )
        ).order_by(AuditLog.created_at).all()
        
        # 构建调用树
        trace_tree = _build_trace_tree(logs, trace_id)
        
        return jsonify({
            'success': True,
            'trace_id': trace_id,
            'logs': audit_logs_schema.dump(logs),
            'trace_tree': trace_tree,
            'total_calls': len(logs),
            'total_duration': _calculate_total_duration(logs)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/statistics', methods=['GET'])
@require_api_key
def get_audit_statistics():
    """获取审计统计信息"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = AuditLog.query
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        # 基础统计
        total_requests = query.count()
        success_requests = query.filter(AuditLog.is_success == True).count()
        failed_requests = total_requests - success_requests
        
        # API调用频率排名
        api_stats = db.session.query(
            AuditLog.api_endpoint,
            func.count().label('count'),
            func.avg(AuditLog.response_time_ms).label('avg_time'),
            func.sum(case((AuditLog.is_success == True, 1), else_=0)).label('success_count')
        ).group_by(AuditLog.api_endpoint).order_by(desc('count')).limit(10).all()
        
        # 用户活跃度
        user_stats = db.session.query(
            AuditLog.user_id,
            func.count().label('count'),
            func.max(AuditLog.created_at).label('last_active')
        ).filter(AuditLog.user_id.isnot(None)).group_by(AuditLog.user_id)\
         .order_by(desc('count')).limit(10).all()
        
        # 时间分布
        hourly_stats = db.session.query(
            func.hour(AuditLog.created_at).label('hour'),
            func.count().label('count')
        ).group_by('hour').order_by('hour').all()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_requests': total_requests,
                'success_rate': round(success_requests / total_requests * 100, 2) if total_requests > 0 else 0,
                'avg_response_time': db.session.query(func.avg(AuditLog.response_time_ms)).scalar() or 0,
                'api_ranking': [
                    {
                        'endpoint': r.api_endpoint,
                        'count': r.count,
                        'avg_time': round(float(r.avg_time or 0), 2),
                        'success_rate': round(r.success_count / r.count * 100, 2)
                    } for r in api_stats
                ],
                'user_activity': [
                    {
                        'user_id': r.user_id,
                        'request_count': r.count,
                        'last_active': r.last_active.isoformat() if r.last_active else None
                    } for r in user_stats
                ],
                'hourly_distribution': [
                    {'hour': r.hour, 'count': r.count} for r in hourly_stats
                ]
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _build_trace_tree(logs, root_trace_id):
    """构建调用树"""
    tree = {}
    
    # 查找根节点
    root_logs = [log for log in logs if log.trace_id == root_trace_id]
    
    for log in root_logs:
        node = {
            'id': log.id,
            'trace_id': log.trace_id,
            'api': log.api_endpoint,
            'method': log.http_method,
            'status': log.response_status,
            'duration': log.response_time_ms,
            'timestamp': log.created_at.isoformat(),
            'children': []
        }
        
        # 查找子调用
        child_logs = [child for child in logs 
                     if child.parent_trace_id == log.trace_id and child.id != log.id]
        
        for child in child_logs:
            node['children'].append(_build_trace_tree([child], child.trace_id))
        
        tree = node
    
    return tree


def _calculate_total_duration(logs):
    """计算总持续时间"""
    if not logs:
        return 0
    
    start_times = [log.created_at for log in logs]
    end_times = [log.ended_at for log in logs if log.ended_at]
    
    if not end_times:
        return 0
    
    min_start = min(start_times)
    max_end = max(end_times)
    
    return int((max_end - min_start).total_seconds() * 1000)


# @app.route('/dashboard')
# def admin_dashboard():
#     """数据治理平台管理后台"""
#     return render_template('dashboard.html')
@app.route('/dashboard')
def admin_dashboard():
    return render_template('dashboard.html')



@app.route('/api/list', methods=['GET'])
def get_api_list():
    """获取所有可用的API列表"""
    try:
        api_list = [
            # ==================== 基础数据 (6个) ====================
            {'name': '路段列表', 'endpoint': '/api/sections', 'method': 'GET', 'category': '基础数据', 'description': '获取所有路段信息', 'auth_required': False},
            {'name': '单个路段', 'endpoint': '/api/sections/<section_id>', 'method': 'GET', 'category': '基础数据', 'description': '获取指定路段详细信息', 'auth_required': False},
            {'name': '收费站列表', 'endpoint': '/api/toll-stations', 'method': 'GET', 'category': '基础数据', 'description': '获取所有收费站信息', 'auth_required': False},
            {'name': '单个收费站', 'endpoint': '/api/toll-stations/<station_id>', 'method': 'GET', 'category': '基础数据', 'description': '获取指定收费站详细信息', 'auth_required': False},
            {'name': '门架列表', 'endpoint': '/api/gantries', 'method': 'GET', 'category': '基础数据', 'description': '获取所有门架信息', 'auth_required': False},
            {'name': '单个门架', 'endpoint': '/api/gantries/<gantry_id>', 'method': 'GET', 'category': '基础数据', 'description': '获取指定门架详细信息', 'auth_required': False},
            
            # ==================== 交易数据 (3个) ====================
            {'name': '入口交易', 'endpoint': '/api/transactions/entrance', 'method': 'GET', 'category': '交易数据', 'description': '获取入口交易记录', 'auth_required': True},
            {'name': '出口交易', 'endpoint': '/api/transactions/exit', 'method': 'GET', 'category': '交易数据', 'description': '获取出口交易记录', 'auth_required': True},
            {'name': '门架交易', 'endpoint': '/api/transactions/gantry', 'method': 'GET', 'category': '交易数据', 'description': '获取门架交易记录', 'auth_required': True},
            
            # ==================== 统计分析 (3个) ====================
            {'name': '交通流量统计', 'endpoint': '/api/statistics/traffic-flow', 'method': 'GET', 'category': '统计分析', 'description': '按时段统计交通流量', 'auth_required': False},
            {'name': '收入统计', 'endpoint': '/api/statistics/revenue', 'method': 'GET', 'category': '统计分析', 'description': '按路段或收费站统计收入', 'auth_required': False},
            {'name': '车辆分布', 'endpoint': '/api/statistics/vehicle-distribution', 'method': 'GET', 'category': '统计分析', 'description': '车型分布统计', 'auth_required': False},
            
            # ==================== 货车分析 (12个)  ====================
            {'name': '货车小时流量', 'endpoint': '/api/analytics/truck/hourly-flow', 'method': 'GET', 'category': '货车分析', 'description': '统计每个路段每小时通过的货车数量', 'auth_required': False},
            {'name': '货车平均行驶时间', 'endpoint': '/api/analytics/truck/avg-travel-time', 'method': 'GET', 'category': '货车分析', 'description': '计算货车在各路段的平均行驶时间', 'auth_required': False},
            {'name': '货车平均通行费', 'endpoint': '/api/analytics/truck/avg-toll-fee', 'method': 'GET', 'category': '货车分析', 'description': '按车型统计平均通行费用', 'auth_required': False},
            {'name': '货车拥堵指数', 'endpoint': '/api/analytics/truck/congestion-index', 'method': 'GET', 'category': '货车分析', 'description': '基于流量和速度计算拥堵指数', 'auth_required': False},
            {'name': '出口小时流量', 'endpoint': '/api/analytics/truck/exit-hourly-flow', 'method': 'GET', 'category': '货车分析', 'description': '统计出口货车小时流量', 'auth_required': False},
            {'name': '出口流量K匿名化', 'endpoint': '/api/analytics/truck/exit-hourly-flow-k-anonymized', 'method': 'GET', 'category': '货车分析', 'description': '隐私保护的出口流量统计', 'auth_required': False},
            {'name': '货车超重率', 'endpoint': '/api/analytics/truck/overweight-rate', 'method': 'GET', 'category': '货车分析', 'description': '统计货车超重情况', 'auth_required': False},
            {'name': '货车优惠率', 'endpoint': '/api/analytics/truck/discount-rate', 'method': 'GET', 'category': '货车分析', 'description': '分析货车享受优惠的比例', 'auth_required': False},
            {'name': '货车高峰时段', 'endpoint': '/api/analytics/truck/peak-hours', 'method': 'GET', 'category': '货车分析', 'description': '识别货车流量高峰时段', 'auth_required': False},
            {'name': '货车平均轴数', 'endpoint': '/api/analytics/truck/avg-axle-count', 'method': 'GET', 'category': '货车分析', 'description': '按车型统计平均轴数', 'auth_required': False},
            {'name': '车道利用率', 'endpoint': '/api/analytics/truck/lane-utilization', 'method': 'GET', 'category': '货车分析', 'description': '分析各车道货车通行情况', 'auth_required': False},
            {'name': '收费站状态', 'endpoint': '/api/analytics/truck/toll-station-status', 'method': 'GET', 'category': '货车分析', 'description': '收费站货车通行状态监控', 'auth_required': False},
            
            # ==================== AI功能 (4个) ====================
            {'name': 'Agent查询', 'endpoint': '/api/agent/query', 'method': 'POST', 'category': 'AI功能', 'description': '智能Agent自然语言查询', 'auth_required': False},
            {'name': 'Smart Query', 'endpoint': '/api/agent/smart-query', 'method': 'POST', 'category': 'AI功能', 'description': '智能查询增强版', 'auth_required': False},
            {'name': 'SQL Agent', 'endpoint': '/api/ai/sql', 'method': 'POST', 'category': 'AI功能', 'description': '自然语言转SQL查询', 'auth_required': False},
            {'name': 'SQL生成', 'endpoint': '/api/ai/sql/generate', 'method': 'POST', 'category': 'AI功能', 'description': '生成SQL查询语句', 'auth_required': False},
            
            # ==================== 数据生成 (5个) ====================
            {'name': '生成门架数据', 'endpoint': '/api/generate/gantry', 'method': 'GET', 'category': '数据生成', 'description': '生成模拟门架交易数据', 'auth_required': False},
            {'name': 'DGM初始化', 'endpoint': '/api/dgm/initialize', 'method': 'POST', 'category': '数据生成', 'description': '初始化DGM模型', 'auth_required': False},
            {'name': 'DGM生成', 'endpoint': '/api/dgm/generate', 'method': 'POST', 'category': '数据生成', 'description': 'DGM模型生成数据', 'auth_required': False},
            {'name': 'DGM统计', 'endpoint': '/api/dgm/stats', 'method': 'GET', 'category': '数据生成', 'description': 'DGM生成数据统计', 'auth_required': False},
            {'name': 'DGM状态', 'endpoint': '/api/dgm/status', 'method': 'GET', 'category': '数据生成', 'description': 'DGM模型状态', 'auth_required': False},
            
            # ==================== 审计系统 (3个) ====================
            {'name': '审计日志', 'endpoint': '/api/audit/logs', 'method': 'GET', 'category': '审计系统', 'description': '获取系统审计日志', 'auth_required': True},
            {'name': '审计统计', 'endpoint': '/api/audit/statistics', 'method': 'GET', 'category': '审计系统', 'description': '获取审计统计信息', 'auth_required': True},
            {'name': '链路追踪', 'endpoint': '/api/audit/trace/<trace_id>', 'method': 'GET', 'category': '审计系统', 'description': '获取完整的调用链路', 'auth_required': True},
            
            # ==================== 系统管理 (3个) ====================
            {'name': '健康检查', 'endpoint': '/api/health', 'method': 'GET', 'category': '系统管理', 'description': '检查系统健康状态', 'auth_required': False},
            {'name': 'API列表', 'endpoint': '/api/list', 'method': 'GET', 'category': '系统管理', 'description': '获取所有可用API列表', 'auth_required': False},
            {'name': '连接测试', 'endpoint': '/api/test/connection', 'method': 'GET', 'category': '系统管理', 'description': '测试数据库连接', 'auth_required': False},
        ]

        
        categories = {}
        for api in api_list:
            category = api['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(api)
        
        return jsonify({'success': True, 'total': len(api_list), 'categories': categories, 'apis': api_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )