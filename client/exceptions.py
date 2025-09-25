"""
Edge-VoMID 客户端异常定义
"""


class VoMIDException(Exception):
    """VoMID异常基类"""
    pass


class VoMIDConnectionError(VoMIDException):
    """连接错误"""
    pass


class VoMIDAuthenticationError(VoMIDException):
    """认证错误"""
    pass


class VoMIDValidationError(VoMIDException):
    """验证错误"""
    pass


class VoMIDTimeoutError(VoMIDException):
    """超时错误"""
    pass
