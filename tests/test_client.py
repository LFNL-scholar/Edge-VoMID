"""
客户端测试
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from client.voimid_client import VoMIDClient, VoMIDException, VoMIDConnectionError


class TestVoMIDClient:
    """VoMID客户端测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.client = VoMIDClient("http://localhost:8080")
    
    def test_init(self):
        """测试客户端初始化"""
        client = VoMIDClient("http://localhost:8080", "test-key", 60)
        assert client.base_url == "http://localhost:8080"
        assert client.api_key == "test-key"
        assert client.timeout == 60
    
    def test_health_check_success(self):
        """测试健康检查成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            result = self.client.health_check()
            assert result["status"] == "healthy"
    
    def test_health_check_connection_error(self):
        """测试健康检查连接错误"""
        with patch.object(self.client.session, 'request', 
                         side_effect=Exception("Connection error")):
            with pytest.raises(VoMIDConnectionError):
                self.client.health_check()
    
    def test_register_voiceprint_file(self):
        """测试注册声纹（文件）"""
        # 创建临时音频文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"fake audio data")
            temp_file = f.name
        
        try:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "success": True,
                "user_id": "test_user_123"
            }
            
            with patch.object(self.client.session, 'request', return_value=mock_response):
                user_id = self.client.register_voiceprint("test_user", temp_file)
                assert user_id == "test_user_123"
        finally:
            os.unlink(temp_file)
    
    def test_register_voiceprint_bytes(self):
        """测试注册声纹（字节数据）"""
        audio_bytes = b"fake audio data"
        
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "success": True,
            "user_id": "test_user_456"
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            user_id = self.client.register_voiceprint("test_user", audio_bytes)
            assert user_id == "test_user_456"
    
    def test_register_voiceprint_file_not_found(self):
        """测试注册声纹（文件不存在）"""
        with pytest.raises(VoMIDException, match="音频文件不存在"):
            self.client.register_voiceprint("test_user", "nonexistent.wav")
    
    def test_verify_voiceprint_success(self):
        """测试验证声纹成功"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"fake audio data")
            temp_file = f.name
        
        try:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "verified": True,
                "user_id": "test_user_123",
                "confidence": 0.85,
                "threshold": 0.6,
                "processing_time": 1.2,
                "timestamp": 1234567890,
                "all_scores": {"test_user_123": 0.85}
            }
            
            with patch.object(self.client.session, 'request', return_value=mock_response):
                result = self.client.verify_voiceprint(temp_file, 0.6)
                assert result.verified is True
                assert result.user_id == "test_user_123"
                assert result.confidence == 0.85
                assert result.threshold == 0.6
        finally:
            os.unlink(temp_file)
    
    def test_verify_voiceprint_not_verified(self):
        """测试验证声纹失败"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"fake audio data")
            temp_file = f.name
        
        try:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "verified": False,
                "user_id": None,
                "confidence": 0.3,
                "threshold": 0.6,
                "processing_time": 1.1,
                "timestamp": 1234567890,
                "all_scores": {"test_user_123": 0.3}
            }
            
            with patch.object(self.client.session, 'request', return_value=mock_response):
                result = self.client.verify_voiceprint(temp_file, 0.6)
                assert result.verified is False
                assert result.user_id is None
                assert result.confidence == 0.3
        finally:
            os.unlink(temp_file)
    
    def test_get_voiceprint(self):
        """测试获取声纹信息"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "user_id": "test_user_123",
            "name": "test_user",
            "status": "active",
            "created_at": 1234567890,
            "updated_at": 1234567890,
            "metadata": {"department": "IT"},
            "version": 1
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            result = self.client.get_voiceprint("test_user_123")
            assert result.user_id == "test_user_123"
            assert result.name == "test_user"
            assert result.status == "active"
            assert result.metadata == {"department": "IT"}
    
    def test_delete_voiceprint(self):
        """测试删除声纹"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "声纹删除成功"
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            result = self.client.delete_voiceprint("test_user_123")
            assert result is True
    
    def test_update_voiceprint_status(self):
        """测试更新声纹状态"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "声纹状态更新成功"
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            result = self.client.update_voiceprint_status("test_user_123", "inactive")
            assert result is True
    
    def test_list_voiceprints(self):
        """测试列出声纹记录"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "voiceprints": [
                {
                    "user_id": "test_user_123",
                    "name": "test_user",
                    "status": "active",
                    "created_at": 1234567890,
                    "updated_at": 1234567890,
                    "metadata": {}
                }
            ],
            "total": 1,
            "limit": 100,
            "offset": 0
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            result = self.client.list_voiceprints()
            assert len(result['voiceprints']) == 1
            assert result['total'] == 1
            assert result['voiceprints'][0]['user_id'] == "test_user_123"
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "statistics": {
                "voiceprint_engine": {"total_voiceprints": 10},
                "distributed_storage": {"total_records": 10}
            }
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            result = self.client.get_statistics()
            assert "voiceprint_engine" in result
            assert "distributed_storage" in result
            assert result["voiceprint_engine"]["total_voiceprints"] == 10
    
    def test_server_error(self):
        """测试服务器错误"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": "内部服务器错误",
            "message": "服务器内部错误，请稍后重试"
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            with pytest.raises(VoMIDException, match="服务器错误"):
                self.client.health_check()
    
    def test_authentication_error(self):
        """测试认证错误"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": "认证失败",
            "message": "认证失败，请检查API密钥"
        }
        
        with patch.object(self.client.session, 'request', return_value=mock_response):
            with pytest.raises(VoMIDException, match="认证失败"):
                self.client.health_check()
