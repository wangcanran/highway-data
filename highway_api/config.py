"""
配置文件 - LLM和API配置
集成审计功能配置
"""
import os

# 获取项目根目录
basedir = os.path.abspath(os.path.dirname(__file__))

# ==================== LLM配置 ====================
OPENAI_API_BASE = "https://4zapi.com/v1"
OPENAI_API_KEY = "sk-qwSKwMOCMlxEOaXTvtvQ2ZpiLsgxGZrPkMVNPPa1GIbKFCl6"
FIXED_MODEL_NAME = "gpt-4.1-2025-04-14"
REQUEST_TIMEOUT = 120

# ==================== 数据库配置 ====================
# 选项1: MySQL数据库 (推荐用于生产环境)
MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '051005',
    'database': 'highway_db',
    'charset': 'utf8mb4'
}

# SQLAlchemy配置 - 默认使用MySQL
SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset={MYSQL_CONFIG['charset']}"

# 选项2: SQLite数据库 (用于开发或备份)
# 使用你现有的SQLite文件路径
SQLITE_DB_PATH = r'D:\python_code\testwork\highway_db_20251120_163848.sqlite'
SQLALCHEMY_DATABASE_URI_SQLITE = f"sqlite:///{SQLITE_DB_PATH}"

# SQLAlchemy通用配置
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = True  # 开发环境设为True便于调试，生产环境设为False
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_POOL_TIMEOUT = 30

# ==================== Flask配置 ====================
DEBUG = True
HOST = '0.0.0.0'
PORT = 5000
SECRET_KEY = 'highway-api-secret-key-2024-change-in-production'

# ==================== API认证配置 ====================
# 原始数据接口需要API Key认证，统计分析接口公开访问
API_KEYS = [
    'highway_admin_key_2024',      # 管理员密钥
    'highway_internal_key_2024',   # 内部系统密钥
    'testkey123',                  # 测试密钥
]

# 是否启用认证（开发环境可设为False）
ENABLE_AUTH = False

# ==================== 审计功能配置 ====================
# 是否启用审计功能
AUDIT_ENABLED = True

# 审计日志保留天数
AUDIT_RETENTION_DAYS = 90

# 审计记录截断设置（避免存储过大数据）
AUDIT_MAX_REQUEST_SIZE = 1024 * 10  # 10KB
AUDIT_MAX_RESPONSE_SIZE = 1024 * 50  # 50KB

# 审计排除路径（不记录审计日志的路径）
AUDIT_EXCLUDED_PATHS = [
    '/static/',
    '/favicon.ico',
    '/api/health',
    '/api/test/connection'
]

# ==================== Agent配置 ====================
# Agent超时时间（秒）
AGENT_TIMEOUT = 300

# 是否启用Agent缓存
AGENT_CACHE_ENABLED = True

# ==================== 多智能体配置 ====================
# 多智能体系统配置
MULTI_AGENT_ENABLED = True
MAX_CONCURRENT_AGENTS = 3

# ==================== 数据生成配置 ====================
# DGM数据生成配置
DGM_ENABLED = True
DGM_MAX_GENERATION_COUNT = 1000

# ==================== 安全配置 ====================
# 跨域配置
CORS_ENABLED = True
CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5000']

# 速率限制
RATE_LIMIT_ENABLED = False
RATE_LIMIT_DEFAULT = "200 per day, 50 per hour"

# ==================== 日志配置 ====================
# 日志级别
LOG_LEVEL = 'INFO'

# 日志文件配置
LOG_FILE = 'logs/app.log'
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 10

# 审计日志文件
AUDIT_LOG_FILE = 'logs/audit.log'