#!/usr/bin/env python3
"""
Edge-VoMID 服务器启动脚本
简化版本，用于快速启动和测试
"""
import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置环境变量
os.environ.setdefault('VOIMID_ENVIRONMENT', 'development')
os.environ.setdefault('VOIMID_API_HOST', '0.0.0.0')
os.environ.setdefault('VOIMID_API_PORT', '8080')
os.environ.setdefault('VOIMID_STORAGE_TYPE', 'memory')
os.environ.setdefault('VOIMID_DEBUG', 'true')

try:
    from config.logger import setup_logging
    from core.voiceprint_engine import VoiceprintEngine
    from core.distributed_storage import DistributedStorage, StorageConfig, StorageType
    from core.load_balancer import LoadBalancer, LoadBalanceStrategy
    
    # 简单的Flask应用
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保已安装所有依赖: pip install -r requirements.txt")
    sys.exit(1)


def create_simple_app():
    """创建简化的Flask应用"""
    app = Flask(__name__)
    CORS(app)
    
    # 初始化日志
    logger = setup_logging().bind(tag="simple_server")
    
    # 初始化组件
    voiceprint_engine = VoiceprintEngine()
    storage_config = StorageConfig(storage_type=StorageType.MEMORY)
    distributed_storage = DistributedStorage(storage_config)
    load_balancer = LoadBalancer(LoadBalanceStrategy.ROUND_ROBIN)
    
    logger.info("Edge-VoMID 简化服务器启动")
    logger.info("组件初始化完成")
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """健康检查"""
        try:
            engine_stats = voiceprint_engine.get_statistics()
            storage_stats = distributed_storage.get_statistics()
            
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'components': {
                    'voiceprint_engine': engine_stats,
                    'distributed_storage': storage_stats
                }
            }), 200
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }), 500
    
    @app.route('/api/v1/voiceprint/register', methods=['POST'])
    def register_voiceprint():
        """注册声纹"""
        try:
            if 'audio' not in request.files:
                return jsonify({'error': '缺少音频文件'}), 400
            
            audio_file = request.files['audio']
            if audio_file.filename == '':
                return jsonify({'error': '未选择文件'}), 400
            
            name = request.form.get('name', '')
            user_id = request.form.get('user_id', '')
            metadata_str = request.form.get('metadata', '{}')
            
            if not name:
                return jsonify({'error': '缺少用户名称'}), 400
            
            try:
                import json
                metadata = json.loads(metadata_str)
            except:
                metadata = {}
            
            # 保存临时文件
            import tempfile
            import uuid
            temp_filename = f"temp_{uuid.uuid4().hex}.wav"
            audio_file.save(temp_filename)
            
            try:
                # 注册声纹
                registered_user_id = voiceprint_engine.register_voiceprint(
                    name=name,
                    audio_path=temp_filename,
                    metadata=metadata,
                    user_id=user_id if user_id else None
                )
                
                # 存储到分布式存储
                voiceprint_record = voiceprint_engine.get_voiceprint_info(registered_user_id)
                if voiceprint_record:
                    distributed_storage.store(registered_user_id, voiceprint_record)
                
                return jsonify({
                    'success': True,
                    'user_id': registered_user_id,
                    'message': '声纹注册成功'
                }), 201
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    
        except Exception as e:
            logger.error(f"声纹注册失败: {e}")
            return jsonify({'error': f'声纹注册失败: {str(e)}'}), 500
    
    @app.route('/api/v1/voiceprint/verify', methods=['POST'])
    def verify_voiceprint():
        """验证声纹"""
        try:
            if 'audio' not in request.files:
                return jsonify({'error': '缺少音频文件'}), 400
            
            audio_file = request.files['audio']
            if audio_file.filename == '':
                return jsonify({'error': '未选择文件'}), 400
            
            threshold = float(request.form.get('threshold', 0.6))
            user_id = request.form.get('user_id', '')
            
            # 保存临时文件
            import tempfile
            import uuid
            temp_filename = f"temp_{uuid.uuid4().hex}.wav"
            audio_file.save(temp_filename)
            
            try:
                # 验证声纹
                verify_user_id = user_id if user_id else None
                result = voiceprint_engine.verify_voiceprint(
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
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    
        except Exception as e:
            logger.error(f"声纹验证失败: {e}")
            return jsonify({'error': f'声纹验证失败: {str(e)}'}), 500
    
    @app.route('/api/v1/stats', methods=['GET'])
    def get_statistics():
        """获取统计信息"""
        try:
            engine_stats = voiceprint_engine.get_statistics()
            storage_stats = distributed_storage.get_statistics()
            cluster_stats = load_balancer.get_node_statistics()
            
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
            logger.error(f"获取统计信息失败: {e}")
            return jsonify({'error': f'获取统计信息失败: {str(e)}'}), 500
    
    @app.route('/api/v1/voiceprints', methods=['GET'])
    def list_voiceprints():
        """列出声纹记录"""
        try:
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
            
            # 从分布式存储获取列表
            all_keys = distributed_storage.list_keys()
            
            voiceprints = []
            for key in all_keys[offset:offset + limit]:
                record = distributed_storage.retrieve(key)
                if record:
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
            logger.error(f"列出声纹失败: {e}")
            return jsonify({'error': f'列出声纹失败: {str(e)}'}), 500
    
    return app, logger


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Edge-VoMID 简化服务器')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8080, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    try:
        # 创建应用
        app, logger = create_simple_app()
        
        logger.info(f"启动服务器: {args.host}:{args.port}")
        logger.info("API端点:")
        logger.info("  GET  /health - 健康检查")
        logger.info("  POST /api/v1/voiceprint/register - 注册声纹")
        logger.info("  POST /api/v1/voiceprint/verify - 验证声纹")
        logger.info("  GET  /api/v1/stats - 获取统计信息")
        logger.info("  GET  /api/v1/voiceprints - 列出声纹记录")
        
        # 启动服务
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("服务器停止")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    import time
    main()
