"""
Edge-VoMID 主应用入口
基于分布式的端侧声纹认证中间件
"""
import os
import sys
import argparse
from typing import Optional

from config.app_config import init_config, get_config, Environment
from config.logger import setup_logging
from api.gateway import APIGateway, APIConfig
from core.distributed_storage import StorageConfig, StorageType
from core.load_balancer import LoadBalanceStrategy


def create_app(config_file: Optional[str] = None):
    """创建Flask应用"""
    # 初始化配置
    config_manager = init_config(config_file)
    config = config_manager.get_config()
    
    # 初始化日志
    logger = setup_logging()
    logger = logger.bind(tag="main")
    
    logger.info(f"启动 {config.app_name} v{config.version}")
    logger.info(f"环境: {config.environment.value}")
    
    # 创建API配置
    api_config = APIConfig(
        host=config.api.host,
        port=config.api.port,
        debug=config.debug,
        storage_type=StorageType(config.storage.type),
        redis_host=config.storage.redis.host,
        redis_port=config.storage.redis.port,
        redis_db=config.storage.redis.db,
        redis_password=config.storage.redis.password,
        file_storage_path=config.storage.file_path,
        load_balance_strategy=LoadBalanceStrategy(config.load_balancer.strategy),
        enable_cors=config.api.enable_cors,
        max_file_size=config.api.max_file_size,
        allowed_extensions=config.api.allowed_extensions
    )
    
    # 创建API网关
    gateway = APIGateway(api_config)
    
    logger.info(f"API网关配置完成，监听地址: {config.api.host}:{config.api.port}")
    
    return gateway.app, gateway


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Edge-VoMID 分布式声纹认证中间件')
    parser.add_argument('--config', '-c', type=str, help='配置文件路径')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8080, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    parser.add_argument('--env', type=str, choices=['development', 'staging', 'production'], 
                       help='环境类型')
    
    args = parser.parse_args()
    
    # 设置环境变量
    if args.env:
        os.environ['VOIMID_ENVIRONMENT'] = args.env
    if args.host:
        os.environ['VOIMID_API_HOST'] = args.host
    if args.port:
        os.environ['VOIMID_API_PORT'] = str(args.port)
    if args.debug:
        os.environ['VOIMID_DEBUG'] = 'true'
    
    try:
        # 创建应用
        app, gateway = create_app(args.config)
        
        # 启动服务
        gateway.run()
        
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
        sys.exit(0)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
