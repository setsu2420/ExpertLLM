"""
配置管理模块
从环境变量中读取配置信息
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# API 密钥配置
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
SILICON_KEY = os.getenv('SILICON_KEY', '')

# API URL 配置
SILICON_URL = os.getenv('SILICON_URL', 'https://api.siliconflow.cn/v1/chat/completions')

# 应用配置
MAX_THREAD_MESSAGES = int(os.getenv('MAX_THREAD_MESSAGES', '30'))
TRENDING_BOARD_SIZE = int(os.getenv('TRENDING_BOARD_SIZE', '10'))  # 热点榜单显示数量
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8885'))
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
# 全局系统提示词，可通过环境变量覆盖
SYSTEM_PROMPT = os.getenv(
    'SYSTEM_PROMPT',
    '使用中文，有学术性且逻辑严密不失创造力地回答。' \
    # '你是一个学术专家，请遵循下述要求:' \
    # '1、所有的公式必须以latex格式书写，被包裹在$...$或$$...$$中。' \
    # '2、所有的要求都要与学术有关，如自然科学、工程与技术科学、医学与生命健康科学、社会科学、人文学科、交叉学科与新兴领域。' \
    # '3、如果与学术无关，立刻停止思考，并回复“本系统暂时仅回答学术问题。”' \
    # '4、回答时必须使用严谨且富有逻辑的语言' \
    # '5、如非必要，尽量多使用完整的句子，而非分点回答' \
)
# WebSocket 安全模式：启用后仅允许基于会话的认证，拒绝通过 auth 传递 user_id
SECURE_SOCKETS = os.getenv('SECURE_SOCKETS', 'false').lower() in ('true', '1', 'yes')

# Redis 配置（公屏聊天 / 缓存 / PubSub）
REDIS_URL = os.getenv('REDIS_URL', '')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'true').lower() in ('true', '1', 'yes')
# 公屏缓存 TTL（秒），默认 7 天
REDIS_PUBLIC_TTL_SECONDS = int(os.getenv('REDIS_PUBLIC_TTL_SECONDS', '604800'))
# 公屏缓存列表最大长度（条）
REDIS_PUBLIC_LIST_MAX = int(os.getenv('REDIS_PUBLIC_LIST_MAX', '300'))
# Redis 键前缀（列表/哈希/频道）
REDIS_PUBLIC_LIST_PREFIX = os.getenv('REDIS_PUBLIC_LIST_PREFIX', 'public:list')
REDIS_PUBLIC_HASH_PREFIX = os.getenv('REDIS_PUBLIC_HASH_PREFIX', 'public:msg')
REDIS_PUBLIC_CHANNEL_PREFIX = os.getenv('REDIS_PUBLIC_CHANNEL_PREFIX', 'public:major')
# 登录态 Redis 前缀与 TTL（秒）
SESSION_TOKEN_PREFIX = os.getenv('SESSION_TOKEN_PREFIX', 'session:token')
SESSION_TOKEN_TTL_SECONDS = int(os.getenv('SESSION_TOKEN_TTL_SECONDS', '604800'))

# 会话密钥（用于 Flask session）
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')

# 数据库配置
SQLALCHEMY_DATABASE_URI = os.getenv(
    'SQLALCHEMY_DATABASE_URI',
    'mysql+pymysql://root:123456@localhost:3306/expertllm-db?charset=utf8mb4',
    # 'mysql+pymysql://root:123456@localhost:3306/expertllm-db?charset=utf8mb4'
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# 嵌入与语义热点配置
EMBEDDING_BACKEND = os.getenv('EMBEDDING_BACKEND', 'silicon').lower()  # silicon | local
EMBEDDING_LOCAL_MODEL = os.getenv('EMBEDDING_LOCAL_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
SILICON_EMBEDDING_MODEL = os.getenv('SILICON_EMBEDDING_MODEL', '')
QUESTION_EMBEDDING_LOOKBACK_DAYS = int(os.getenv('QUESTION_EMBEDDING_LOOKBACK_DAYS', '7'))
QUESTION_EMBEDDING_MAX_SAMPLES = int(os.getenv('QUESTION_EMBEDDING_MAX_SAMPLES', '10000'))
SIM_THRESHOLD = float(os.getenv('SIM_THRESHOLD', '0.8'))
QUESTION_TRENDING_TOP_K = int(os.getenv('QUESTION_TRENDING_TOP_K', '10'))
QUESTION_TRENDING_INTERVAL_SECONDS = int(os.getenv('QUESTION_TRENDING_INTERVAL_SECONDS', str(2 * 60 * 60)))
QUESTION_TRENDING_DECAY = float(os.getenv('QUESTION_TRENDING_DECAY', '0.02'))


def validate_config():
    """验证必需的配置项是否存在"""
    missing = []
    
    if not GEMINI_API_KEY:
        missing.append('GEMINI_API_KEY')
    if not OPENAI_API_KEY:
        missing.append('OPENAI_API_KEY')
    if not SILICON_KEY:
        missing.append('SILICON_KEY')
    
    if missing:
        print(f"警告: 缺少以下环境变量: {', '.join(missing)}")
        print("请在 .env 文件中配置这些变量")
        return False
    
    return True
