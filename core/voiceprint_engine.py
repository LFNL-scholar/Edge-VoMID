"""
声纹识别引擎核心模块
基于阿里3D Speaker模型的高性能声纹识别引擎
"""
import numpy as np
import torch
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
import logging
from typing import Dict, List, Tuple, Optional, Any
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
import time

# 禁用modelscope的日志输出
logging.getLogger('modelscope').setLevel(logging.CRITICAL)


class VoiceprintStatus(Enum):
    """声纹状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass
class VoiceprintRecord:
    """声纹记录数据结构"""
    user_id: str
    name: str
    embedding: np.ndarray
    status: VoiceprintStatus
    created_at: float
    updated_at: float
    metadata: Dict[str, Any]
    version: int = 1


@dataclass
class VerificationResult:
    """验证结果数据结构"""
    user_id: Optional[str]
    confidence: float
    is_verified: bool
    all_scores: Dict[str, float]
    processing_time: float
    timestamp: float


class VoiceprintEngine:
    """声纹识别引擎"""
    
    def __init__(self, model_name: str = "iic/speech_campplus_sv_zh-cn_3dspeaker_16k"):
        """
        初始化声纹识别引擎
        
        Args:
            model_name: 模型名称
        """
        self.model_name = model_name
        self.pipeline = None
        self.voiceprints: Dict[str, VoiceprintRecord] = {}
        self._init_model()
    
    def _init_model(self):
        """初始化模型"""
        try:
            self.pipeline = pipeline(
                task=Tasks.speaker_verification,
                model=self.model_name
            )
        except Exception as e:
            raise RuntimeError(f"模型初始化失败: {e}")
    
    def _to_numpy(self, x):
        """转换为numpy数组"""
        return x.cpu().numpy() if torch.is_tensor(x) else np.asarray(x)
    
    def _generate_user_id(self, name: str, metadata: Dict[str, Any] = None) -> str:
        """生成用户ID"""
        content = f"{name}_{json.dumps(metadata or {}, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def register_voiceprint(self, name: str, audio_path: str, 
                          metadata: Dict[str, Any] = None,
                          user_id: str = None) -> str:
        """
        注册声纹特征
        
        Args:
            name: 用户名称
            audio_path: 音频文件路径
            metadata: 元数据
            user_id: 用户ID，如果未提供则自动生成
            
        Returns:
            用户ID
        """
        start_time = time.time()
        
        try:
            # 提取声纹特征
            result = self.pipeline([audio_path], output_emb=True)
            embedding = self._to_numpy(result["embs"][0])
            
            # 生成用户ID
            if user_id is None:
                user_id = self._generate_user_id(name, metadata)
            
            # 创建声纹记录
            current_time = time.time()
            record = VoiceprintRecord(
                user_id=user_id,
                name=name,
                embedding=embedding,
                status=VoiceprintStatus.ACTIVE,
                created_at=current_time,
                updated_at=current_time,
                metadata=metadata or {}
            )
            
            # 存储声纹记录
            self.voiceprints[user_id] = record
            
            processing_time = time.time() - start_time
            
            return user_id
            
        except Exception as e:
            raise RuntimeError(f"声纹注册失败: {e}")
    
    def verify_voiceprint(self, audio_path: str, threshold: float = 0.6,
                         user_id: str = None) -> VerificationResult:
        """
        验证声纹
        
        Args:
            audio_path: 音频文件路径
            threshold: 相似度阈值
            user_id: 指定用户ID进行验证，如果为None则进行全局匹配
            
        Returns:
            验证结果
        """
        start_time = time.time()
        
        try:
            # 提取测试音频特征
            test_result = self.pipeline([audio_path], output_emb=True)
            test_embedding = self._to_numpy(test_result["embs"][0])
            
            # 计算相似度
            similarities = {}
            
            if user_id:
                # 指定用户验证
                if user_id in self.voiceprints:
                    record = self.voiceprints[user_id]
                    if record.status == VoiceprintStatus.ACTIVE:
                        cos_sim = np.dot(test_embedding, record.embedding) / (
                            np.linalg.norm(test_embedding) * np.linalg.norm(record.embedding)
                        )
                        similarities[user_id] = cos_sim
            else:
                # 全局匹配
                for uid, record in self.voiceprints.items():
                    if record.status == VoiceprintStatus.ACTIVE:
                        cos_sim = np.dot(test_embedding, record.embedding) / (
                            np.linalg.norm(test_embedding) * np.linalg.norm(record.embedding)
                        )
                        similarities[uid] = cos_sim
            
            # 确定最佳匹配
            if similarities:
                best_match = max(similarities, key=similarities.get)
                best_score = similarities[best_match]
                is_verified = best_score >= threshold
            else:
                best_match = None
                best_score = 0.0
                is_verified = False
            
            processing_time = time.time() - start_time
            
            return VerificationResult(
                user_id=best_match,
                confidence=best_score,
                is_verified=is_verified,
                all_scores=similarities,
                processing_time=processing_time,
                timestamp=time.time()
            )
            
        except Exception as e:
            raise RuntimeError(f"声纹验证失败: {e}")
    
    def get_voiceprint_info(self, user_id: str) -> Optional[VoiceprintRecord]:
        """获取声纹信息"""
        return self.voiceprints.get(user_id)
    
    def update_voiceprint_status(self, user_id: str, status: VoiceprintStatus) -> bool:
        """更新声纹状态"""
        if user_id in self.voiceprints:
            self.voiceprints[user_id].status = status
            self.voiceprints[user_id].updated_at = time.time()
            return True
        return False
    
    def delete_voiceprint(self, user_id: str) -> bool:
        """删除声纹记录"""
        if user_id in self.voiceprints:
            del self.voiceprints[user_id]
            return True
        return False
    
    def list_voiceprints(self, status: VoiceprintStatus = None) -> List[VoiceprintRecord]:
        """列出声纹记录"""
        if status is None:
            return list(self.voiceprints.values())
        return [record for record in self.voiceprints.values() if record.status == status]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.voiceprints)
        active = len([r for r in self.voiceprints.values() if r.status == VoiceprintStatus.ACTIVE])
        
        return {
            "total_voiceprints": total,
            "active_voiceprints": active,
            "inactive_voiceprints": total - active,
            "model_name": self.model_name
        }
