"""
负载均衡器模块
支持多种负载均衡策略和健康检查
"""
import time
import threading
import random
import statistics
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
from abc import ABC, abstractmethod


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_RESPONSE_TIME = "least_response_time"


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 100
    health_check_url: Optional[str] = None
    last_health_check: float = field(default_factory=time.time)
    is_healthy: bool = True
    active_connections: int = 0
    total_requests: int = 0
    total_response_time: float = 0.0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestContext:
    """请求上下文"""
    request_id: str
    timestamp: float
    client_ip: str
    user_agent: str
    request_type: str
    priority: int = 0


class HealthChecker(ABC):
    """健康检查器抽象类"""
    
    @abstractmethod
    def check_health(self, node: NodeInfo) -> bool:
        """检查节点健康状态"""
        pass


class HTTPHealthChecker(HealthChecker):
    """HTTP健康检查器"""
    
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
    
    def check_health(self, node: NodeInfo) -> bool:
        """通过HTTP检查节点健康状态"""
        if not node.health_check_url:
            return True  # 没有健康检查URL则认为健康
        
        try:
            import requests
            response = requests.get(
                node.health_check_url,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception:
            return False


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
                 health_check_interval: int = 30):
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self.nodes: Dict[str, NodeInfo] = {}
        self.current_index: int = 0
        self.health_checker = HTTPHealthChecker()
        self._lock = threading.RLock()
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = threading.Event()
        
        self._start_health_check_thread()
    
    def _start_health_check_thread(self):
        """启动健康检查线程"""
        if self._health_check_thread is None or not self._health_check_thread.is_alive():
            self._stop_health_check.clear()
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop,
                daemon=True
            )
            self._health_check_thread.start()
    
    def _health_check_loop(self):
        """健康检查循环"""
        while not self._stop_health_check.is_set():
            try:
                self._perform_health_checks()
                self._stop_health_check.wait(self.health_check_interval)
            except Exception:
                pass  # 健康检查失败不影响主服务
    
    def _perform_health_checks(self):
        """执行健康检查"""
        with self._lock:
            for node in self.nodes.values():
                is_healthy = self.health_checker.check_health(node)
                node.is_healthy = is_healthy
                node.last_health_check = time.time()
                
                if not is_healthy:
                    node.error_count += 1
    
    def add_node(self, node: NodeInfo) -> bool:
        """添加节点"""
        with self._lock:
            self.nodes[node.node_id] = node
            return True
    
    def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                return True
            return False
    
    def update_node(self, node_id: str, **kwargs) -> bool:
        """更新节点信息"""
        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                for key, value in kwargs.items():
                    if hasattr(node, key):
                        setattr(node, key, value)
                return True
            return False
    
    def get_healthy_nodes(self) -> List[NodeInfo]:
        """获取健康节点列表"""
        with self._lock:
            return [node for node in self.nodes.values() if node.is_healthy]
    
    def select_node(self, context: RequestContext = None) -> Optional[NodeInfo]:
        """选择节点"""
        with self._lock:
            healthy_nodes = self.get_healthy_nodes()
            if not healthy_nodes:
                return None
            
            if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
                return self._round_robin_selection(healthy_nodes)
            elif self.strategy == LoadBalanceStrategy.RANDOM:
                return self._random_selection(healthy_nodes)
            elif self.strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
                return self._least_connections_selection(healthy_nodes)
            elif self.strategy == LoadBalanceStrategy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin_selection(healthy_nodes)
            elif self.strategy == LoadBalanceStrategy.LEAST_RESPONSE_TIME:
                return self._least_response_time_selection(healthy_nodes)
            else:
                return self._round_robin_selection(healthy_nodes)
    
    def _round_robin_selection(self, nodes: List[NodeInfo]) -> NodeInfo:
        """轮询选择"""
        if not nodes:
            return None
        
        selected_node = nodes[self.current_index % len(nodes)]
        self.current_index += 1
        return selected_node
    
    def _random_selection(self, nodes: List[NodeInfo]) -> NodeInfo:
        """随机选择"""
        return random.choice(nodes) if nodes else None
    
    def _least_connections_selection(self, nodes: List[NodeInfo]) -> NodeInfo:
        """最少连接选择"""
        return min(nodes, key=lambda node: node.active_connections) if nodes else None
    
    def _weighted_round_robin_selection(self, nodes: List[NodeInfo]) -> NodeInfo:
        """加权轮询选择"""
        if not nodes:
            return None
        
        # 按权重排序
        weighted_nodes = []
        for node in nodes:
            weighted_nodes.extend([node] * node.weight)
        
        if not weighted_nodes:
            return nodes[0]
        
        selected_node = weighted_nodes[self.current_index % len(weighted_nodes)]
        self.current_index += 1
        return selected_node
    
    def _least_response_time_selection(self, nodes: List[NodeInfo]) -> NodeInfo:
        """最少响应时间选择"""
        if not nodes:
            return None
        
        def avg_response_time(node):
            if node.total_requests == 0:
                return float('inf')
            return node.total_response_time / node.total_requests
        
        return min(nodes, key=avg_response_time)
    
    def record_request(self, node_id: str, response_time: float, success: bool = True):
        """记录请求统计"""
        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.total_requests += 1
                node.total_response_time += response_time
                
                if success:
                    node.active_connections = max(0, node.active_connections - 1)
                else:
                    node.error_count += 1
    
    def get_node_statistics(self) -> Dict[str, Any]:
        """获取节点统计信息"""
        with self._lock:
            stats = {
                "total_nodes": len(self.nodes),
                "healthy_nodes": len(self.get_healthy_nodes()),
                "strategy": self.strategy.value,
                "nodes": {}
            }
            
            for node_id, node in self.nodes.items():
                avg_response_time = (
                    node.total_response_time / node.total_requests
                    if node.total_requests > 0 else 0
                )
                
                stats["nodes"][node_id] = {
                    "host": node.host,
                    "port": node.port,
                    "is_healthy": node.is_healthy,
                    "active_connections": node.active_connections,
                    "total_requests": node.total_requests,
                    "error_count": node.error_count,
                    "avg_response_time": avg_response_time,
                    "last_health_check": node.last_health_check
                }
            
            return stats
    
    def shutdown(self):
        """关闭负载均衡器"""
        self._stop_health_check.set()
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=5)


class NodeManager:
    """节点管理器"""
    
    def __init__(self, load_balancer: LoadBalancer):
        self.load_balancer = load_balancer
    
    def register_node(self, node_id: str, host: str, port: int, 
                     weight: int = 1, health_check_url: str = None,
                     metadata: Dict[str, Any] = None) -> bool:
        """注册节点"""
        node = NodeInfo(
            node_id=node_id,
            host=host,
            port=port,
            weight=weight,
            health_check_url=health_check_url,
            metadata=metadata or {}
        )
        return self.load_balancer.add_node(node)
    
    def unregister_node(self, node_id: str) -> bool:
        """注销节点"""
        return self.load_balancer.remove_node(node_id)
    
    def update_node_weight(self, node_id: str, weight: int) -> bool:
        """更新节点权重"""
        return self.load_balancer.update_node(node_id, weight=weight)
    
    def get_node_info(self, node_id: str) -> Optional[NodeInfo]:
        """获取节点信息"""
        return self.load_balancer.nodes.get(node_id)
    
    def list_nodes(self, healthy_only: bool = False) -> List[NodeInfo]:
        """列出节点"""
        if healthy_only:
            return self.load_balancer.get_healthy_nodes()
        return list(self.load_balancer.nodes.values())
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """获取集群状态"""
        return self.load_balancer.get_node_statistics()
