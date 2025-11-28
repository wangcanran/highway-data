"""
配置文件 - LLM和API配置
"""

# LLM配置
OPENAI_API_BASE = "https://4zapi.com/v1"
OPENAI_API_KEY = "sk-qwSKwMOCMlxEOaXTvtvQ2ZpiLsgxGZrPkMVNPPa1GIbKFCl6"
FIXED_MODEL_NAME = "gpt-4.1-2025-04-14"
REQUEST_TIMEOUT = 120

# 数据库配置 - SQLite (已弃用)
DB_PATH = r'D:\python_code\testwork\highway_db_20251120_163848.sqlite'

# MySQL数据库配置 (原始连接方式，保留用于特殊用途)
MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '051005',
    'database': 'highway_db',
    'charset': 'utf8mb4',
    'cursorclass': 'DictCursor'
}

# SQLAlchemy配置
SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset={MYSQL_CONFIG['charset']}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False  # 设置为True可以看到SQL语句
SQLALCHEMY_POOL_SIZE = 10
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_POOL_TIMEOUT = 30

# Flask配置
DEBUG = True
HOST = '0.0.0.0'
PORT = 5000

# API认证配置
# 原始数据接口需要API Key认证，统计分析接口公开访问
API_KEYS = [
    'highway_admin_key_2024',  # 管理员密钥
    'highway_internal_key_2024',  # 内部系统密钥
]

# 是否启用认证（开发环境可设为False）
ENABLE_AUTH = False
