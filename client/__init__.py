"""
Edge-VoMID 客户端SDK
提供Python客户端接口
"""
from .voimid_client import VoMIDClient
from .exceptions import VoMIDException, VoMIDConnectionError, VoMIDAuthenticationError

__version__ = "1.0.0"
__all__ = ["VoMIDClient", "VoMIDException", "VoMIDConnectionError", "VoMIDAuthenticationError"]
