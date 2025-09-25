"""
监控指标收集模块
收集系统性能指标和业务指标
"""
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import statistics
import psutil
import json


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class SystemMetrics:
    """系统指标"""
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_available: int
    disk_usage_percent: float
    disk_free: int
    network_sent: int
    network_recv: int
    process_count: int
    timestamp: float


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.current_metrics: Dict[str, float] = {}
        self.counters: Dict[str, int] = defaultdict(int)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # 系统指标收集
        self.system_metrics_history: deque = deque(maxlen=100)
        self._last_network_stats = None
        self._start_time = time.time()
    
    def record_metric(self, name: str, value: float, 
                     labels: Dict[str, str] = None,
                     metric_type: MetricType = MetricType.GAUGE):
        """记录指标"""
        with self._lock:
            metric_value = MetricValue(
                name=name,
                value=value,
                timestamp=time.time(),
                labels=labels or {},
                metric_type=metric_type
            )
            
            self.metrics_history.append(metric_value)
            self.current_metrics[name] = value
    
    def increment_counter(self, name: str, value: int = 1, 
                         labels: Dict[str, str] = None):
        """增加计数器"""
        with self._lock:
            counter_key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self.counters[counter_key] += value
            self.record_metric(name, self.counters[counter_key], labels, MetricType.COUNTER)
    
    def record_timer(self, name: str, duration: float, 
                    labels: Dict[str, str] = None):
        """记录计时器"""
        with self._lock:
            timer_key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self.timers[timer_key].append(duration)
            
            # 只保留最近的100个值
            if len(self.timers[timer_key]) > 100:
                self.timers[timer_key] = self.timers[timer_key][-100:]
            
            self.record_metric(name, duration, labels, MetricType.TIMER)
    
    def collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        try:
            # CPU和内存
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 网络统计
            network = psutil.net_io_counters()
            if self._last_network_stats:
                network_sent = network.bytes_sent - self._last_network_stats.bytes_sent
                network_recv = network.bytes_recv - self._last_network_stats.bytes_recv
            else:
                network_sent = 0
                network_recv = 0
            
            self._last_network_stats = network
            
            # 进程数量
            process_count = len(psutil.pids())
            
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_available=memory.available,
                disk_usage_percent=disk.percent,
                disk_free=disk.free,
                network_sent=network_sent,
                network_recv=network_recv,
                process_count=process_count,
                timestamp=time.time()
            )
            
            self.system_metrics_history.append(metrics)
            return metrics
            
        except Exception as e:
            # 如果系统指标收集失败，返回默认值
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used=0,
                memory_available=0,
                disk_usage_percent=0.0,
                disk_free=0,
                network_sent=0,
                network_recv=0,
                process_count=0,
                timestamp=time.time()
            )
    
    def get_metric_summary(self, name: str, 
                          time_window: int = 300) -> Dict[str, Any]:
        """获取指标摘要"""
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - time_window
            
            # 筛选时间窗口内的指标
            recent_metrics = [
                m for m in self.metrics_history
                if m.name == name and m.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {
                    'name': name,
                    'count': 0,
                    'avg': 0,
                    'min': 0,
                    'max': 0,
                    'sum': 0
                }
            
            values = [m.value for m in recent_metrics]
            
            return {
                'name': name,
                'count': len(values),
                'avg': statistics.mean(values),
                'min': min(values),
                'max': max(values),
                'sum': sum(values),
                'std': statistics.stdev(values) if len(values) > 1 else 0
            }
    
    def get_timer_stats(self, name: str, 
                       labels: Dict[str, str] = None) -> Dict[str, float]:
        """获取计时器统计"""
        with self._lock:
            timer_key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            durations = self.timers.get(timer_key, [])
            
            if not durations:
                return {
                    'count': 0,
                    'avg': 0,
                    'min': 0,
                    'max': 0,
                    'p50': 0,
                    'p95': 0,
                    'p99': 0
                }
            
            sorted_durations = sorted(durations)
            count = len(sorted_durations)
            
            return {
                'count': count,
                'avg': statistics.mean(sorted_durations),
                'min': min(sorted_durations),
                'max': max(sorted_durations),
                'p50': sorted_durations[int(count * 0.5)],
                'p95': sorted_durations[int(count * 0.95)],
                'p99': sorted_durations[int(count * 0.99)]
            }
    
    def get_system_metrics_summary(self) -> Dict[str, Any]:
        """获取系统指标摘要"""
        if not self.system_metrics_history:
            return {}
        
        recent_metrics = list(self.system_metrics_history)[-10:]  # 最近10个
        
        return {
            'cpu': {
                'current': recent_metrics[-1].cpu_percent,
                'avg': statistics.mean([m.cpu_percent for m in recent_metrics])
            },
            'memory': {
                'current_percent': recent_metrics[-1].memory_percent,
                'avg_percent': statistics.mean([m.memory_percent for m in recent_metrics]),
                'current_used': recent_metrics[-1].memory_used,
                'current_available': recent_metrics[-1].memory_available
            },
            'disk': {
                'current_percent': recent_metrics[-1].disk_usage_percent,
                'current_free': recent_metrics[-1].disk_free
            },
            'network': {
                'sent': recent_metrics[-1].network_sent,
                'recv': recent_metrics[-1].network_recv
            },
            'process_count': recent_metrics[-1].process_count,
            'uptime': time.time() - self._start_time
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        with self._lock:
            return {
                'current_metrics': self.current_metrics.copy(),
                'counters': dict(self.counters),
                'system': self.get_system_metrics_summary(),
                'uptime': time.time() - self._start_time,
                'timestamp': time.time()
            }


class MetricsTimer:
    """指标计时器上下文管理器"""
    
    def __init__(self, collector: MetricsCollector, name: str, 
                 labels: Dict[str, str] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.record_timer(self.name, duration, self.labels)


class MetricsMiddleware:
    """指标中间件"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_request(self, endpoint: str, method: str, 
                      status_code: int, duration: float):
        """记录请求指标"""
        labels = {
            'endpoint': endpoint,
            'method': method,
            'status_code': str(status_code)
        }
        
        self.collector.record_timer('http_request_duration', duration, labels)
        self.collector.increment_counter('http_requests_total', labels=labels)
        
        if status_code >= 400:
            self.collector.increment_counter('http_errors_total', labels=labels)
    
    def record_voiceprint_operation(self, operation: str, success: bool, 
                                   duration: float):
        """记录声纹操作指标"""
        labels = {
            'operation': operation,
            'success': str(success)
        }
        
        self.collector.record_timer('voiceprint_operation_duration', duration, labels)
        self.collector.increment_counter('voiceprint_operations_total', labels=labels)
        
        if not success:
            self.collector.increment_counter('voiceprint_errors_total', labels=labels)
