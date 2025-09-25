"""
API网关模块
提供统一的API入口和路由管理
"""
import time
import uuid
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import threading
from functools import wraps

from core.voiceprint_engine import VoiceprintEngine, VerificationResult, VoiceprintStatus
from core.distributed_storage import DistributedStorage, StorageConfig, StorageType
from core.load_balancer import LoadBalancer, LoadBalanceStrategy, NodeManager, RequestContext
from config.logger import setup_logging


@dataclass
class APIConfig:
    """API配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    storage_type: StorageType = StorageType.MEMORY
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    file_storage_path: str = "data/voiceprints"
    load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    enable_cors: bool = True
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = None


class APIGateway:
    """API网关"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.app = Flask(__name__)
        self.logger = setup_logging().bind(tag="api_gateway")
        
        # 初始化组件
        self.voiceprint_engine = VoiceprintEngine()
        self.storage_config = self._create_storage_config()
        self.distributed_storage = DistributedStorage(self.storage_config)
        self.load_balancer = LoadBalancer(config.load_balance_strategy)
        self.node_manager = NodeManager(self.load_balancer)
        
        # 配置Flask应用
        self._configure_app()
        self._register_routes()
        
        # 启动时注册当前节点
        self._register_self_as_node()
    
    def _create_storage_config(self) -> StorageConfig:
        """创建存储配置"""
        return StorageConfig(
            storage_type=self.config.storage_type,
            redis_host=self.config.redis_host,
            redis_port=self.config.redis_port,
            redis_db=self.config.redis_db,
            redis_password=self.config.redis_password,
            file_path=self.config.file_storage_path
        )
    
    def _configure_app(self):
        """配置Flask应用"""
        # 设置最大文件大小
        self.app.config['MAX_CONTENT_LENGTH'] = self.config.max_file_size
        
        # 启用CORS
        if self.config.enable_cors:
            CORS(self.app)
        
        # 设置错误处理
        self.app.errorhandler(413)(self._handle_file_too_large)
        self.app.errorhandler(400)(self._handle_bad_request)
        self.app.errorhandler(500)(self._handle_internal_error)
    
    def _register_self_as_node(self):
        """将当前实例注册为节点"""
        node_id = f"node_{uuid.uuid4().hex[:8]}"
        health_check_url = f"http://{self.config.host}:{self.config.port}/health"
        
        self.node_manager.register_node(
            node_id=node_id,
            host=self.config.host,
            port=self.config.port,
            health_check_url=health_check_url,
            metadata={"self": True}
        )
    
    def _register_routes(self):
        """注册路由"""
        
        # 健康检查
        self.app.route('/health', methods=['GET'])(self.health_check)
        
        # 声纹注册
        self.app.route('/api/v1/voiceprint/register', methods=['POST'])(self.register_voiceprint)
        
        # 声纹验证
        self.app.route('/api/v1/voiceprint/verify', methods=['POST'])(self.verify_voiceprint)
        
        # 声纹管理
        self.app.route('/api/v1/voiceprint/<user_id>', methods=['GET'])(self.get_voiceprint)
        self.app.route('/api/v1/voiceprint/<user_id>', methods=['DELETE'])(self.delete_voiceprint)
        self.app.route('/api/v1/voiceprint/<user_id>/status', methods=['PUT'])(self.update_voiceprint_status)
        
        # 声纹列表
        self.app.route('/api/v1/voiceprints', methods=['GET'])(self.list_voiceprints)
        
        # 统计信息
        self.app.route('/api/v1/stats', methods=['GET'])(self.get_statistics)
        
        # 集群管理
        self.app.route('/api/v1/cluster/nodes', methods=['GET'])(self.list_nodes)
        self.app.route('/api/v1/cluster/nodes', methods=['POST'])(self.register_node)
        self.app.route('/api/v1/cluster/nodes/<node_id>', methods=['DELETE'])(self.unregister_node)
        self.app.route('/api/v1/cluster/status', methods=['GET'])(self.get_cluster_status)
        
        # 存储管理
        self.app.route('/api/v1/storage/stats', methods=['GET'])(self.get_storage_stats)
    
    def _create_request_context(self) -> RequestContext:
        """创建请求上下文"""
        return RequestContext(
            request_id=str(uuid.uuid4()),
            timestamp=time.time(),
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            request_type=request.method
        )
    
    def _handle_file_too_large(self, e):
        """处理文件过大错误"""
        return jsonify({
            'error': '文件过大',
            'message': f'文件大小超过限制 ({self.config.max_file_size} bytes)',
            'code': 413
        }), 413
    
    def _handle_bad_request(self, e):
        """处理请求错误"""
        return jsonify({
            'error': '请求错误',
            'message': str(e),
            'code': 400
        }), 400
    
    def _handle_internal_error(self, e):
        """处理内部错误"""
        self.logger.error(f"内部错误: {e}")
        return jsonify({
            'error': '内部服务器错误',
            'message': '服务器内部错误，请稍后重试',
            'code': 500
        }), 500
    
    def health_check(self):
        """健康检查接口"""
        try:
            # 检查各个组件状态
            engine_stats = self.voiceprint_engine.get_statistics()
            storage_stats = self.distributed_storage.get_statistics()
            
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'components': {
                    'voiceprint_engine': engine_stats,
                    'distributed_storage': storage_stats
                }
            }), 200
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }), 500
    
    def register_voiceprint(self):
        """注册声纹接口"""
        try:
            if 'audio' not in request.files:
                return jsonify({'error': '缺少音频文件'}), 400
            
            audio_file = request.files['audio']
            if audio_file.filename == '':
                return jsonify({'error': '未选择文件'}), 400
            
            # 检查文件扩展名
            if self.config.allowed_extensions:
                if not audio_file.filename.lower().endswith(tuple(self.config.allowed_extensions)):
                    return jsonify({'error': '不支持的文件格式'}), 400
            
            # 获取参数
            name = request.form.get('name', '')
            user_id = request.form.get('user_id', '')
            metadata_str = request.form.get('metadata', '{}')
            
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}
            
            if not name:
                return jsonify({'error': '缺少用户名称'}), 400
            
            # 保存临时文件
            temp_filename = f"temp_{uuid.uuid4().hex}.wav"
            audio_file.save(temp_filename)
            
            try:
                # 注册声纹
                registered_user_id = self.voiceprint_engine.register_voiceprint(
                    name=name,
                    audio_path=temp_filename,
                    metadata=metadata,
                    user_id=user_id if user_id else None
                )
                
                # 存储到分布式存储
                voiceprint_record = self.voiceprint_engine.get_voiceprint_info(registered_user_id)
                if voiceprint_record:
                    self.distributed_storage.store(registered_user_id, voiceprint_record)
                
                return jsonify({
                    'success': True,
                    'user_id': registered_user_id,
                    'message': '声纹注册成功'
                }), 201
                
            finally:
                # 清理临时文件
                import os
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    
        except Exception as e:
            self.logger.error(f"声纹注册失败: {e}")
            return jsonify({'error': f'声纹注册失败: {str(e)}'}), 500
    
    def verify_voiceprint(self):
        """验证声纹接口"""
        try:
            if 'audio' not in request.files:
                return jsonify({'error': '缺少音频文件'}), 400
            
            audio_file = request.files['audio']
            if audio_file.filename == '':
                return jsonify({'error': '未选择文件'}), 400
            
            # 获取参数
            threshold = float(request.form.get('threshold', 0.6))
            user_id = request.form.get('user_id', '')
            
            # 保存临时文件
            temp_filename = f"temp_{uuid.uuid4().hex}.wav"
            audio_file.save(temp_filename)
            
            try:
                # 验证声纹
                verify_user_id = user_id if user_id else None
                result = self.voiceprint_engine.verify_voiceprint(
                    audio_path=temp_filename,
                    threshold=threshold,
                    user_id=verify_user_id
                )
                
                return jsonify({
                    'success': True,
                    'verified': result.is_verified,
                    'user_id': result.user_id,
                    'confidence': result.confidence,
                    'threshold': threshold,
                    'processing_time': result.processing_time,
                    'timestamp': result.timestamp,
                    'all_scores': result.all_scores
                }), 200
                
            finally:
                # 清理临时文件
                import os
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    
        except Exception as e:
            self.logger.error(f"声纹验证失败: {e}")
            return jsonify({'error': f'声纹验证失败: {str(e)}'}), 500
    
    def get_voiceprint(self, user_id: str):
        """获取声纹信息接口"""
        try:
            # 先从分布式存储获取
            voiceprint_record = self.distributed_storage.retrieve(user_id)
            
            if not voiceprint_record:
                # 如果分布式存储没有，从本地引擎获取
                voiceprint_record = self.voiceprint_engine.get_voiceprint_info(user_id)
            
            if not voiceprint_record:
                return jsonify({'error': '声纹记录不存在'}), 404
            
            return jsonify({
                'success': True,
                'user_id': voiceprint_record.user_id,
                'name': voiceprint_record.name,
                'status': voiceprint_record.status.value,
                'created_at': voiceprint_record.created_at,
                'updated_at': voiceprint_record.updated_at,
                'metadata': voiceprint_record.metadata,
                'version': voiceprint_record.version
            }), 200
            
        except Exception as e:
            self.logger.error(f"获取声纹信息失败: {e}")
            return jsonify({'error': f'获取声纹信息失败: {str(e)}'}), 500
    
    def delete_voiceprint(self, user_id: str):
        """删除声纹接口"""
        try:
            # 从本地引擎删除
            local_deleted = self.voiceprint_engine.delete_voiceprint(user_id)
            
            # 从分布式存储删除
            storage_deleted = self.distributed_storage.delete(user_id)
            
            if not local_deleted and not storage_deleted:
                return jsonify({'error': '声纹记录不存在'}), 404
            
            return jsonify({
                'success': True,
                'message': '声纹删除成功'
            }), 200
            
        except Exception as e:
            self.logger.error(f"删除声纹失败: {e}")
            return jsonify({'error': f'删除声纹失败: {str(e)}'}), 500
    
    def update_voiceprint_status(self, user_id: str):
        """更新声纹状态接口"""
        try:
            data = request.get_json()
            if not data or 'status' not in data:
                return jsonify({'error': '缺少状态参数'}), 400
            
            try:
                status = VoiceprintStatus(data['status'])
            except ValueError:
                return jsonify({'error': '无效的状态值'}), 400
            
            # 更新本地引擎状态
            local_updated = self.voiceprint_engine.update_voiceprint_status(user_id, status)
            
            # 更新分布式存储状态
            voiceprint_record = self.distributed_storage.retrieve(user_id)
            if voiceprint_record:
                voiceprint_record.status = status
                voiceprint_record.updated_at = time.time()
                self.distributed_storage.store(user_id, voiceprint_record)
                storage_updated = True
            else:
                storage_updated = False
            
            if not local_updated and not storage_updated:
                return jsonify({'error': '声纹记录不存在'}), 404
            
            return jsonify({
                'success': True,
                'message': '声纹状态更新成功'
            }), 200
            
        except Exception as e:
            self.logger.error(f"更新声纹状态失败: {e}")
            return jsonify({'error': f'更新声纹状态失败: {str(e)}'}), 500
    
    def list_voiceprints(self):
        """列出声纹接口"""
        try:
            status_param = request.args.get('status')
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
            
            # 从分布式存储获取列表
            all_keys = self.distributed_storage.list_keys()
            
            voiceprints = []
            for key in all_keys[offset:offset + limit]:
                record = self.distributed_storage.retrieve(key)
                if record and (status_param is None or record.status.value == status_param):
                    voiceprints.append({
                        'user_id': record.user_id,
                        'name': record.name,
                        'status': record.status.value,
                        'created_at': record.created_at,
                        'updated_at': record.updated_at,
                        'metadata': record.metadata
                    })
            
            return jsonify({
                'success': True,
                'voiceprints': voiceprints,
                'total': len(all_keys),
                'limit': limit,
                'offset': offset
            }), 200
            
        except Exception as e:
            self.logger.error(f"列出声纹失败: {e}")
            return jsonify({'error': f'列出声纹失败: {str(e)}'}), 500
    
    def get_statistics(self):
        """获取统计信息接口"""
        try:
            engine_stats = self.voiceprint_engine.get_statistics()
            storage_stats = self.distributed_storage.get_statistics()
            cluster_stats = self.load_balancer.get_node_statistics()
            
            return jsonify({
                'success': True,
                'statistics': {
                    'voiceprint_engine': engine_stats,
                    'distributed_storage': storage_stats,
                    'cluster': cluster_stats
                },
                'timestamp': time.time()
            }), 200
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return jsonify({'error': f'获取统计信息失败: {str(e)}'}), 500
    
    def list_nodes(self):
        """列出节点接口"""
        try:
            healthy_only = request.args.get('healthy_only', 'false').lower() == 'true'
            nodes = self.node_manager.list_nodes(healthy_only=healthy_only)
            
            node_list = []
            for node in nodes:
                avg_response_time = (
                    node.total_response_time / node.total_requests
                    if node.total_requests > 0 else 0
                )
                
                node_list.append({
                    'node_id': node.node_id,
                    'host': node.host,
                    'port': node.port,
                    'weight': node.weight,
                    'is_healthy': node.is_healthy,
                    'active_connections': node.active_connections,
                    'total_requests': node.total_requests,
                    'error_count': node.error_count,
                    'avg_response_time': avg_response_time,
                    'last_health_check': node.last_health_check,
                    'metadata': node.metadata
                })
            
            return jsonify({
                'success': True,
                'nodes': node_list,
                'total': len(node_list)
            }), 200
            
        except Exception as e:
            self.logger.error(f"列出节点失败: {e}")
            return jsonify({'error': f'列出节点失败: {str(e)}'}), 500
    
    def register_node(self):
        """注册节点接口"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': '缺少请求数据'}), 400
            
            required_fields = ['node_id', 'host', 'port']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'缺少必需字段: {field}'}), 400
            
            success = self.node_manager.register_node(
                node_id=data['node_id'],
                host=data['host'],
                port=data['port'],
                weight=data.get('weight', 1),
                health_check_url=data.get('health_check_url'),
                metadata=data.get('metadata', {})
            )
            
            if success:
                return jsonify({
                    'success': True,
                    'message': '节点注册成功'
                }), 201
            else:
                return jsonify({'error': '节点注册失败'}), 400
                
        except Exception as e:
            self.logger.error(f"注册节点失败: {e}")
            return jsonify({'error': f'注册节点失败: {str(e)}'}), 500
    
    def unregister_node(self, node_id: str):
        """注销节点接口"""
        try:
            success = self.node_manager.unregister_node(node_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': '节点注销成功'
                }), 200
            else:
                return jsonify({'error': '节点不存在'}), 404
                
        except Exception as e:
            self.logger.error(f"注销节点失败: {e}")
            return jsonify({'error': f'注销节点失败: {str(e)}'}), 500
    
    def get_cluster_status(self):
        """获取集群状态接口"""
        try:
            status = self.node_manager.get_cluster_status()
            return jsonify({
                'success': True,
                'cluster_status': status,
                'timestamp': time.time()
            }), 200
            
        except Exception as e:
            self.logger.error(f"获取集群状态失败: {e}")
            return jsonify({'error': f'获取集群状态失败: {str(e)}'}), 500
    
    def get_storage_stats(self):
        """获取存储统计信息接口"""
        try:
            stats = self.distributed_storage.get_statistics()
            return jsonify({
                'success': True,
                'storage_stats': stats,
                'timestamp': time.time()
            }), 200
            
        except Exception as e:
            self.logger.error(f"获取存储统计信息失败: {e}")
            return jsonify({'error': f'获取存储统计信息失败: {str(e)}'}), 500
    
    def run(self):
        """启动API网关"""
        self.logger.info(f"启动API网关，地址: {self.config.host}:{self.config.port}")
        self.app.run(
            host=self.config.host,
            port=self.config.port,
            debug=self.config.debug,
            threaded=True
        )
