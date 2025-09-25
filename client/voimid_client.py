"""
Edge-VoMID Python客户端
提供简单的Python接口来使用声纹认证服务
"""
import requests
import json
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import os


@dataclass
class VerificationResult:
    """验证结果"""
    verified: bool
    user_id: Optional[str]
    confidence: float
    threshold: float
    processing_time: float
    timestamp: float
    all_scores: Dict[str, float]


@dataclass
class VoiceprintInfo:
    """声纹信息"""
    user_id: str
    name: str
    status: str
    created_at: float
    updated_at: float
    metadata: Dict[str, Any]
    version: int


class VoMIDException(Exception):
    """VoMID异常基类"""
    pass


class VoMIDConnectionError(VoMIDException):
    """连接错误"""
    pass


class VoMIDAuthenticationError(VoMIDException):
    """认证错误"""
    pass


class VoMIDClient:
    """Edge-VoMID客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8080", 
                 api_key: Optional[str] = None,
                 timeout: int = 30):
        """
        初始化客户端
        
        Args:
            base_url: API服务器地址
            api_key: API密钥（可选）
            timeout: 请求超时时间
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': 'VoMID-Python-Client/1.0.0'
        })
        
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            
            # 检查HTTP状态码
            if response.status_code == 401:
                raise VoMIDAuthenticationError("认证失败，请检查API密钥")
            elif response.status_code == 404:
                raise VoMIDException("资源不存在")
            elif response.status_code >= 500:
                raise VoMIDException(f"服务器错误: {response.status_code}")
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', f'请求失败: {response.status_code}')
                except:
                    error_msg = f'请求失败: {response.status_code}'
                raise VoMIDException(error_msg)
            
            # 解析响应
            try:
                return response.json()
            except json.JSONDecodeError:
                return {'success': True, 'data': response.text}
                
        except requests.exceptions.ConnectionError:
            raise VoMIDConnectionError(f"无法连接到服务器: {self.base_url}")
        except requests.exceptions.Timeout:
            raise VoMIDException("请求超时")
        except requests.exceptions.RequestException as e:
            raise VoMIDException(f"请求失败: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return self._make_request('GET', '/health')
    
    def register_voiceprint(self, name: str, audio_file: Union[str, bytes],
                          user_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        注册声纹
        
        Args:
            name: 用户名称
            audio_file: 音频文件路径或字节数据
            user_id: 用户ID（可选）
            metadata: 元数据（可选）
            
        Returns:
            用户ID
        """
        # 准备文件数据
        if isinstance(audio_file, str):
            if not os.path.exists(audio_file):
                raise VoMIDException(f"音频文件不存在: {audio_file}")
            
            with open(audio_file, 'rb') as f:
                files = {'audio': f}
                data = {'name': name}
                
                if user_id:
                    data['user_id'] = user_id
                if metadata:
                    data['metadata'] = json.dumps(metadata)
                
                response = self._make_request('POST', '/api/v1/voiceprint/register',
                                            files=files, data=data)
        else:
            # 字节数据
            files = {'audio': ('audio.wav', audio_file, 'audio/wav')}
            data = {'name': name}
            
            if user_id:
                data['user_id'] = user_id
            if metadata:
                data['metadata'] = json.dumps(metadata)
            
            response = self._make_request('POST', '/api/v1/voiceprint/register',
                                        files=files, data=data)
        
        if response.get('success'):
            return response['user_id']
        else:
            raise VoMIDException(f"注册失败: {response.get('error', '未知错误')}")
    
    def verify_voiceprint(self, audio_file: Union[str, bytes],
                         threshold: float = 0.6,
                         user_id: Optional[str] = None) -> VerificationResult:
        """
        验证声纹
        
        Args:
            audio_file: 音频文件路径或字节数据
            threshold: 相似度阈值
            user_id: 指定用户ID进行验证（可选）
            
        Returns:
            验证结果
        """
        # 准备文件数据
        if isinstance(audio_file, str):
            if not os.path.exists(audio_file):
                raise VoMIDException(f"音频文件不存在: {audio_file}")
            
            with open(audio_file, 'rb') as f:
                files = {'audio': f}
                data = {'threshold': threshold}
                
                if user_id:
                    data['user_id'] = user_id
                
                response = self._make_request('POST', '/api/v1/voiceprint/verify',
                                            files=files, data=data)
        else:
            # 字节数据
            files = {'audio': ('audio.wav', audio_file, 'audio/wav')}
            data = {'threshold': threshold}
            
            if user_id:
                data['user_id'] = user_id
            
            response = self._make_request('POST', '/api/v1/voiceprint/verify',
                                        files=files, data=data)
        
        if response.get('success'):
            return VerificationResult(
                verified=response['verified'],
                user_id=response['user_id'],
                confidence=response['confidence'],
                threshold=response['threshold'],
                processing_time=response['processing_time'],
                timestamp=response['timestamp'],
                all_scores=response['all_scores']
            )
        else:
            raise VoMIDException(f"验证失败: {response.get('error', '未知错误')}")
    
    def get_voiceprint(self, user_id: str) -> VoiceprintInfo:
        """获取声纹信息"""
        response = self._make_request('GET', f'/api/v1/voiceprint/{user_id}')
        
        if response.get('success'):
            return VoiceprintInfo(
                user_id=response['user_id'],
                name=response['name'],
                status=response['status'],
                created_at=response['created_at'],
                updated_at=response['updated_at'],
                metadata=response['metadata'],
                version=response['version']
            )
        else:
            raise VoMIDException(f"获取声纹信息失败: {response.get('error', '未知错误')}")
    
    def delete_voiceprint(self, user_id: str) -> bool:
        """删除声纹"""
        response = self._make_request('DELETE', f'/api/v1/voiceprint/{user_id}')
        
        if response.get('success'):
            return True
        else:
            raise VoMIDException(f"删除声纹失败: {response.get('error', '未知错误')}")
    
    def update_voiceprint_status(self, user_id: str, status: str) -> bool:
        """更新声纹状态"""
        data = {'status': status}
        response = self._make_request('PUT', f'/api/v1/voiceprint/{user_id}/status',
                                    json=data)
        
        if response.get('success'):
            return True
        else:
            raise VoMIDException(f"更新声纹状态失败: {response.get('error', '未知错误')}")
    
    def list_voiceprints(self, status: Optional[str] = None,
                        limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """列出声纹记录"""
        params = {'limit': limit, 'offset': offset}
        if status:
            params['status'] = status
        
        response = self._make_request('GET', '/api/v1/voiceprints', params=params)
        
        if response.get('success'):
            return {
                'voiceprints': response['voiceprints'],
                'total': response['total'],
                'limit': response['limit'],
                'offset': response['offset']
            }
        else:
            raise VoMIDException(f"列出声纹失败: {response.get('error', '未知错误')}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        response = self._make_request('GET', '/api/v1/stats')
        
        if response.get('success'):
            return response['statistics']
        else:
            raise VoMIDException(f"获取统计信息失败: {response.get('error', '未知错误')}")
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """获取集群状态"""
        response = self._make_request('GET', '/api/v1/cluster/status')
        
        if response.get('success'):
            return response['cluster_status']
        else:
            raise VoMIDException(f"获取集群状态失败: {response.get('error', '未知错误')}")


# 便捷函数
def create_client(base_url: str = "http://localhost:8080", 
                 api_key: Optional[str] = None) -> VoMIDClient:
    """创建客户端实例"""
    return VoMIDClient(base_url, api_key)


def quick_verify(audio_file: str, base_url: str = "http://localhost:8080",
                threshold: float = 0.6) -> VerificationResult:
    """快速验证声纹"""
    client = VoMIDClient(base_url)
    return client.verify_voiceprint(audio_file, threshold)


def quick_register(name: str, audio_file: str, 
                  base_url: str = "http://localhost:8080") -> str:
    """快速注册声纹"""
    client = VoMIDClient(base_url)
    return client.register_voiceprint(name, audio_file)
