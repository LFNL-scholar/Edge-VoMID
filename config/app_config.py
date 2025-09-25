"""
应用配置管理模块
支持多种配置源和环境变量
"""
import os
import json
import yaml
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging


class Environment(Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str = "localhost"
    port: int = 5432
    name: str = "voimid"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20


@dataclass
class RedisConfig:
    """Redis配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 100
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


@dataclass
class StorageConfig:
    """存储配置"""
    type: str = "memory"  # memory, redis, file
    file_path: str = "data/voiceprints"
    redis: RedisConfig = field(default_factory=RedisConfig)
    cache_size: int = 1000
    cache_ttl: int = 3600


@dataclass
class LoadBalancerConfig:
    """负载均衡配置"""
    strategy: str = "round_robin"  # round_robin, random, least_connections, weighted_round_robin, least_response_time
    health_check_interval: int = 30
    max_retries: int = 3
    timeout: int = 30


@dataclass
class APIConfig:
    """API配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = field(default_factory=lambda: ['.wav', '.mp3', '.flac', '.m4a'])
    enable_cors: bool = True
    cors_origins: list = field(default_factory=lambda: ['*'])
    rate_limit: str = "1000/hour"
    api_key_required: bool = False
    api_keys: list = field(default_factory=list)


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "<green>{time:YY-MM-DD HH:mm:ss.SSS}</green> - [<light-blue>{extra[tag]}</light-blue>] - <level>{level}</level> - <light-green>{message}</light-green>"
    file_path: str = "logs/server.log"
    rotation: str = "100 MB"
    retention: str = "7 days"
    compression: str = "zip"
    enqueue: bool = True
    backtrace: bool = True
    diagnose: bool = True


@dataclass
class ModelConfig:
    """模型配置"""
    name: str = "iic/speech_campplus_sv_zh-cn_3dspeaker_16k"
    cache_dir: str = "models"
    device: str = "auto"  # auto, cpu, cuda
    batch_size: int = 1
    max_audio_length: int = 30  # 秒
    min_audio_length: float = 1.0  # 秒


@dataclass
class SecurityConfig:
    """安全配置"""
    secret_key: str = ""
    jwt_secret: str = ""
    jwt_expiration: int = 3600  # 秒
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration: int = 300  # 秒
    enable_rate_limiting: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 秒


@dataclass
class MonitoringConfig:
    """监控配置"""
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_health_checks: bool = True
    health_check_interval: int = 30
    enable_tracing: bool = False
    jaeger_endpoint: str = "http://localhost:14268/api/traces"


@dataclass
class AppConfig:
    """应用配置"""
    environment: Environment = Environment.DEVELOPMENT
    app_name: str = "Edge-VoMID"
    version: str = "1.0.0"
    debug: bool = False
    
    # 子配置
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    load_balancer: LoadBalancerConfig = field(default_factory=LoadBalancerConfig)
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.config = AppConfig()
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 1. 加载默认配置
        self.config = AppConfig()
        
        # 2. 从配置文件加载
        if self.config_file and os.path.exists(self.config_file):
            self._load_from_file(self.config_file)
        
        # 3. 从环境变量覆盖
        self._load_from_env()
        
        # 4. 验证配置
        self._validate_config()
    
    def _load_from_file(self, config_file: str):
        """从配置文件加载"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.endswith('.json'):
                    config_data = json.load(f)
                elif config_file.endswith(('.yml', '.yaml')):
                    config_data = yaml.safe_load(f)
                else:
                    raise ValueError(f"不支持的配置文件格式: {config_file}")
            
            self._merge_config(config_data)
            
        except Exception as e:
            logging.warning(f"加载配置文件失败: {e}")
    
    def _load_from_env(self):
        """从环境变量加载"""
        env_mappings = {
            # 应用配置
            'VOIMID_ENVIRONMENT': ('environment', lambda x: Environment(x)),
            'VOIMID_DEBUG': ('debug', lambda x: x.lower() == 'true'),
            'VOIMID_VERSION': ('version', str),
            
            # API配置
            'VOIMID_API_HOST': ('api.host', str),
            'VOIMID_API_PORT': ('api.port', int),
            'VOIMID_API_DEBUG': ('api.debug', lambda x: x.lower() == 'true'),
            'VOIMID_API_MAX_FILE_SIZE': ('api.max_file_size', int),
            
            # 存储配置
            'VOIMID_STORAGE_TYPE': ('storage.type', str),
            'VOIMID_STORAGE_FILE_PATH': ('storage.file_path', str),
            'VOIMID_REDIS_HOST': ('storage.redis.host', str),
            'VOIMID_REDIS_PORT': ('storage.redis.port', int),
            'VOIMID_REDIS_DB': ('storage.redis.db', int),
            'VOIMID_REDIS_PASSWORD': ('storage.redis.password', str),
            
            # 数据库配置
            'VOIMID_DB_HOST': ('database.host', str),
            'VOIMID_DB_PORT': ('database.port', int),
            'VOIMID_DB_NAME': ('database.name', str),
            'VOIMID_DB_USER': ('database.user', str),
            'VOIMID_DB_PASSWORD': ('database.password', str),
            
            # 模型配置
            'VOIMID_MODEL_NAME': ('model.name', str),
            'VOIMID_MODEL_DEVICE': ('model.device', str),
            'VOIMID_MODEL_CACHE_DIR': ('model.cache_dir', str),
            
            # 日志配置
            'VOIMID_LOG_LEVEL': ('logging.level', str),
            'VOIMID_LOG_FILE': ('logging.file_path', str),
            
            # 安全配置
            'VOIMID_SECRET_KEY': ('security.secret_key', str),
            'VOIMID_JWT_SECRET': ('security.jwt_secret', str),
        }
        
        for env_var, (config_path, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    self._set_nested_config(config_path, converted_value)
                except Exception as e:
                    logging.warning(f"环境变量 {env_var} 转换失败: {e}")
    
    def _merge_config(self, config_data: Dict[str, Any]):
        """合并配置数据"""
        # 这里可以实现更复杂的配置合并逻辑
        # 暂时简化处理
        for key, value in config_data.items():
            if hasattr(self.config, key):
                if isinstance(value, dict) and hasattr(getattr(self.config, key), '__dict__'):
                    # 嵌套对象
                    nested_obj = getattr(self.config, key)
                    for nested_key, nested_value in value.items():
                        if hasattr(nested_obj, nested_key):
                            setattr(nested_obj, nested_key, nested_value)
                else:
                    # 简单属性
                    setattr(self.config, key, value)
    
    def _set_nested_config(self, path: str, value: Any):
        """设置嵌套配置"""
        parts = path.split('.')
        obj = self.config
        
        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return
        
        if hasattr(obj, parts[-1]):
            setattr(obj, parts[-1], value)
    
    def _validate_config(self):
        """验证配置"""
        # 验证必需的配置项
        if not self.config.security.secret_key:
            self.config.security.secret_key = os.urandom(32).hex()
        
        if not self.config.security.jwt_secret:
            self.config.security.jwt_secret = os.urandom(32).hex()
        
        # 验证端口范围
        if not (1 <= self.config.api.port <= 65535):
            raise ValueError(f"无效的API端口: {self.config.api.port}")
        
        # 验证文件大小限制
        if self.config.api.max_file_size <= 0:
            raise ValueError("文件大小限制必须大于0")
        
        # 验证存储类型
        valid_storage_types = ['memory', 'redis', 'file']
        if self.config.storage.type not in valid_storage_types:
            raise ValueError(f"无效的存储类型: {self.config.storage.type}")
    
    def get_config(self) -> AppConfig:
        """获取配置"""
        return self.config
    
    def save_config(self, config_file: str):
        """保存配置到文件"""
        config_dict = self._config_to_dict(self.config)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            if config_file.endswith('.json'):
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            elif config_file.endswith(('.yml', '.yaml')):
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
    
    def _config_to_dict(self, config_obj) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        if hasattr(config_obj, '__dict__'):
            result = {}
            for key, value in config_obj.__dict__.items():
                if hasattr(value, '__dict__'):
                    result[key] = self._config_to_dict(value)
                else:
                    result[key] = value
            return result
        return config_obj
    
    def reload_config(self):
        """重新加载配置"""
        self._load_config()
    
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        return f"postgresql://{self.config.database.user}:{self.config.database.password}@{self.config.database.host}:{self.config.database.port}/{self.config.database.name}"
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        auth = f":{self.config.storage.redis.password}@" if self.config.storage.redis.password else ""
        return f"redis://{auth}{self.config.storage.redis.host}:{self.config.storage.redis.port}/{self.config.storage.redis.db}"


# 全局配置实例
_config_manager: Optional[ConfigManager] = None


def get_config() -> AppConfig:
    """获取全局配置"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.get_config()


def init_config(config_file: Optional[str] = None) -> ConfigManager:
    """初始化配置"""
    global _config_manager
    _config_manager = ConfigManager(config_file)
    return _config_manager
