"""
分布式声纹特征存储模块
支持Redis、内存和文件系统的多级存储
"""
import json
import pickle
import os
import hashlib
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import time
import threading
from abc import ABC, abstractmethod

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .voiceprint_engine import VoiceprintRecord, VoiceprintStatus


class StorageType(Enum):
    """存储类型枚举"""
    MEMORY = "memory"
    REDIS = "redis"
    FILE = "file"


@dataclass
class StorageConfig:
    """存储配置"""
    storage_type: StorageType
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    file_path: str = "data/voiceprints"
    cache_size: int = 1000
    cache_ttl: int = 3600  # 秒


class StorageInterface(ABC):
    """存储接口抽象类"""
    
    @abstractmethod
    def store(self, key: str, data: VoiceprintRecord) -> bool:
        """存储数据"""
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> Optional[VoiceprintRecord]:
        """检索数据"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除数据"""
        pass
    
    @abstractmethod
    def list_keys(self) -> List[str]:
        """列出所有键"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass


class MemoryStorage(StorageInterface):
    """内存存储实现"""
    
    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self._storage: Dict[str, VoiceprintRecord] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.RLock()
    
    def store(self, key: str, data: VoiceprintRecord) -> bool:
        """存储数据到内存"""
        with self._lock:
            # 检查缓存大小限制
            if len(self._storage) >= self.cache_size:
                self._evict_oldest()
            
            self._storage[key] = data
            self._timestamps[key] = time.time()
            return True
    
    def retrieve(self, key: str) -> Optional[VoiceprintRecord]:
        """从内存检索数据"""
        with self._lock:
            if key not in self._storage:
                return None
            
            # 检查TTL
            if time.time() - self._timestamps[key] > self.cache_ttl:
                self.delete(key)
                return None
            
            return self._storage[key]
    
    def delete(self, key: str) -> bool:
        """从内存删除数据"""
        with self._lock:
            if key in self._storage:
                del self._storage[key]
                del self._timestamps[key]
                return True
            return False
    
    def list_keys(self) -> List[str]:
        """列出所有键"""
        with self._lock:
            # 清理过期数据
            current_time = time.time()
            expired_keys = [
                key for key, timestamp in self._timestamps.items()
                if current_time - timestamp > self.cache_ttl
            ]
            for key in expired_keys:
                self.delete(key)
            
            return list(self._storage.keys())
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.retrieve(key) is not None
    
    def _evict_oldest(self):
        """淘汰最旧的数据"""
        if not self._timestamps:
            return
        
        oldest_key = min(self._timestamps, key=self._timestamps.get)
        self.delete(oldest_key)


class RedisStorage(StorageInterface):
    """Redis存储实现"""
    
    def __init__(self, host: str = "localhost", port: int = 6379, 
                 db: int = 0, password: Optional[str] = None):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis模块未安装，请运行: pip install redis")
        
        self.redis_client = redis.Redis(
            host=host, port=port, db=db, password=password,
            decode_responses=False  # 保持二进制数据
        )
        
        # 测试连接
        try:
            self.redis_client.ping()
        except redis.ConnectionError:
            raise ConnectionError("无法连接到Redis服务器")
    
    def store(self, key: str, data: VoiceprintRecord) -> bool:
        """存储数据到Redis"""
        try:
            # 序列化数据
            serialized_data = pickle.dumps(data)
            self.redis_client.set(key, serialized_data)
            return True
        except Exception:
            return False
    
    def retrieve(self, key: str) -> Optional[VoiceprintRecord]:
        """从Redis检索数据"""
        try:
            serialized_data = self.redis_client.get(key)
            if serialized_data is None:
                return None
            return pickle.loads(serialized_data)
        except Exception:
            return None
    
    def delete(self, key: str) -> bool:
        """从Redis删除数据"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception:
            return False
    
    def list_keys(self) -> List[str]:
        """列出所有键"""
        try:
            return [key.decode('utf-8') for key in self.redis_client.keys("*")]
        except Exception:
            return []
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception:
            return False


class FileStorage(StorageInterface):
    """文件系统存储实现"""
    
    def __init__(self, base_path: str = "data/voiceprints"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def _get_file_path(self, key: str) -> str:
        """获取文件路径"""
        return os.path.join(self.base_path, f"{key}.json")
    
    def store(self, key: str, data: VoiceprintRecord) -> bool:
        """存储数据到文件"""
        try:
            file_path = self._get_file_path(key)
            
            # 转换为可序列化的格式
            data_dict = asdict(data)
            data_dict['embedding'] = data.embedding.tolist()  # numpy数组转列表
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def retrieve(self, key: str) -> Optional[VoiceprintRecord]:
        """从文件检索数据"""
        try:
            file_path = self._get_file_path(key)
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data_dict = json.load(f)
            
            # 恢复numpy数组
            import numpy as np
            data_dict['embedding'] = np.array(data_dict['embedding'])
            data_dict['status'] = VoiceprintStatus(data_dict['status'])
            
            return VoiceprintRecord(**data_dict)
        except Exception:
            return None
    
    def delete(self, key: str) -> bool:
        """从文件删除数据"""
        try:
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
    
    def list_keys(self) -> List[str]:
        """列出所有键"""
        try:
            keys = []
            for filename in os.listdir(self.base_path):
                if filename.endswith('.json'):
                    keys.append(filename[:-5])  # 移除.json后缀
            return keys
        except Exception:
            return []
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return os.path.exists(self._get_file_path(key))


class DistributedStorage:
    """分布式存储管理器"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self._primary_storage: StorageInterface
        self._secondary_storage: Optional[StorageInterface] = None
        self._lock = threading.RLock()
        
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储后端"""
        # 主存储
        if self.config.storage_type == StorageType.MEMORY:
            self._primary_storage = MemoryStorage(
                self.config.cache_size, self.config.cache_ttl
            )
        elif self.config.storage_type == StorageType.REDIS:
            self._primary_storage = RedisStorage(
                self.config.redis_host, self.config.redis_port,
                self.config.redis_db, self.config.redis_password
            )
        elif self.config.storage_type == StorageType.FILE:
            self._primary_storage = FileStorage(self.config.file_path)
        else:
            raise ValueError(f"不支持的存储类型: {self.config.storage_type}")
        
        # 配置二级存储（用于备份）
        if self.config.storage_type != StorageType.FILE:
            self._secondary_storage = FileStorage(self.config.file_path)
    
    def store(self, key: str, data: VoiceprintRecord) -> bool:
        """存储数据（主存储 + 备份存储）"""
        with self._lock:
            success = self._primary_storage.store(key, data)
            
            # 备份到二级存储
            if success and self._secondary_storage:
                try:
                    self._secondary_storage.store(key, data)
                except Exception:
                    pass  # 备份失败不影响主操作
            
            return success
    
    def retrieve(self, key: str) -> Optional[VoiceprintRecord]:
        """检索数据（主存储 -> 备份存储）"""
        with self._lock:
            # 首先尝试主存储
            data = self._primary_storage.retrieve(key)
            
            # 如果主存储没有，尝试备份存储
            if data is None and self._secondary_storage:
                data = self._secondary_storage.retrieve(key)
                
                # 如果备份存储有数据，恢复到主存储
                if data is not None:
                    try:
                        self._primary_storage.store(key, data)
                    except Exception:
                        pass  # 恢复失败不影响数据返回
            
            return data
    
    def delete(self, key: str) -> bool:
        """删除数据（主存储 + 备份存储）"""
        with self._lock:
            primary_success = self._primary_storage.delete(key)
            
            # 同时删除备份
            if self._secondary_storage:
                try:
                    self._secondary_storage.delete(key)
                except Exception:
                    pass
            
            return primary_success
    
    def list_keys(self) -> List[str]:
        """列出所有键"""
        with self._lock:
            return self._primary_storage.list_keys()
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.retrieve(key) is not None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        keys = self.list_keys()
        return {
            "total_records": len(keys),
            "storage_type": self.config.storage_type.value,
            "primary_storage": type(self._primary_storage).__name__,
            "secondary_storage": type(self._secondary_storage).__name__ if self._secondary_storage else None
        }
