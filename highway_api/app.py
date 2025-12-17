"""
Highway API - 基于 Flask + SQLAlchemy + Marshmallow
使用ORM替代原始SQL查询
"""
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime
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

# 导入LangGraph工作流
from langgraph_workflows import workflow_executor
from enhanced_agent import enhanced_agent

# 导入模型和schemas
from models import db, Section, TollStation, Gantry, EntranceTransaction, ExitTransaction, GantryTransaction
from schemas import ma, section_schema, sections_schema, toll_station_schema, toll_stations_schema
from schemas import gantry_schema, gantries_schema, entrance_transaction_schema, entrance_transactions_schema
from schemas import exit_transaction_schema, exit_transactions_schema, gantry_transaction_schema, gantry_transactions_schema

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
    
    POST /api/agent/query
    Body: {
        "query": "用户的自然语言查询"
    }
    
    示例：
    - "分析货车流量" -> 推荐流量相关API
    - "查看拥堵情况" -> 推荐拥堵指数API
    - "核算通行费" -> 执行场景1工作流
    - "检测异常交易" -> 执行场景2工作流
    """
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        
        if not user_query:
            return jsonify({'error': '请提供查询描述'}), 400
        
        # 使用统一Agent处理（支持API推荐和工作流）
        response = enhanced_agent.process_query(user_query, request.host_url)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        
        # 使用统一Agent处理
        response = enhanced_agent.process_query(user_query, request.host_url)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'智能Agent处理失败: {str(e)}'
        }), 500

@app.route('/api/ai/sql', methods=['POST'])
def ai_sql_query():
    """AI SQL查询接口 - 自然语言转SQL并执行"""
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        
        if not user_query:
            return jsonify({
                'success': False,
                'error': '请提供查询描述'
            }), 400
        
        # 使用AI SQL Agent处理查询
        response = ai_sql_agent.process_query(user_query, request.host_url)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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


# ==================== LangGraph服务编排 API ====================

@app.route('/api/workflow/execute', methods=['POST'])
def workflow_execute():
    """执行LangGraph工作流
    
    POST /api/workflow/execute
    Body: {
        "scenario": "scenario1|scenario2|scenario3",
        "params": {...}
    }
    """
    try:
        data = request.get_json()
        scenario = data.get('scenario', '')
        params = data.get('params', {})
        
        if not scenario:
            return jsonify({
                'success': False,
                'error': '请提供场景名称 (scenario1/scenario2/scenario3)'
            }), 400
        
        # 执行工作流
        result = workflow_executor.execute(scenario, params)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'工作流执行失败: {str(e)}'
        }), 500


@app.route('/api/workflow/scenarios', methods=['GET'])
def workflow_scenarios():
    """获取所有可用场景信息
    
    GET /api/workflow/scenarios
    GET /api/workflow/scenarios?scenario=scenario1
    """
    try:
        scenario = request.args.get('scenario', '')
        
        if scenario:
            # 获取单个场景信息
            info = workflow_executor.get_scenario_info(scenario)
            if not info:
                return jsonify({
                    'success': False,
                    'error': f'场景不存在: {scenario}'
                }), 404
            return jsonify({
                'success': True,
                'scenario': scenario,
                'info': info
            })
        else:
            # 获取所有场景信息
            scenarios = {}
            for s in ['scenario1', 'scenario2', 'scenario3']:
                scenarios[s] = workflow_executor.get_scenario_info(s)
            
            return jsonify({
                'success': True,
                'scenarios': scenarios
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
