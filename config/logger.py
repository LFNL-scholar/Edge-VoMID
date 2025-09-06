import os
import sys
from loguru import logger
from typing import Dict, Any

DEFAULT_LOG_CONFIG: Dict[str, Any] = {
    "log_format": "<green>{time:YY-MM-DD HH:mm:ss.SSS}</green> - "
                 "[<light-blue>{extra[tag]}</light-blue>] - "
                 "<level>{level}</level> - "
                 "<light-green>{message}</light-green>",
    "log_format_simple": "{time:YYYY-MM-DD HH:mm:ss.SSS} - "
                        "{extra[tag]} - {level} - {message}",
    "log_level": "INFO",
    "log_dir": "logs",
    "log_file": "server.log",
    "rotation": "100 MB",
    "retention": "7 days",
    "compression": "zip",
    "enqueue": True,
    "backtrace": True,  # 记录异常堆栈
    "diagnose": True,   # 显示诊断信息
}

def setup_logging():
    """从配置文件中读取日志配置，并设置日志输出格式和级别"""
    log_config = DEFAULT_LOG_CONFIG

    os.makedirs(log_config["log_dir"], exist_ok=True)

    # 配置日志输出
    logger.remove()

    # 输出到控制台
    logger.add(sys.stdout, format=log_config["log_format"], level=log_config["log_level"])

    # 输出到文件
    logger.add(
        os.path.join(log_config["log_dir"], log_config["log_file"]), 
        format=log_config["log_format_simple"], 
        level=log_config["log_level"]
    )

    return logger
