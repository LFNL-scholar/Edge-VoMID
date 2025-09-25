# Edge-VoMID

基于分布式的端侧声纹认证中间件

## 项目简介

Edge-VoMID 是一个基于阿里达摩院3D Speaker模型的分布式声纹认证中间件，专为边缘计算和高可用环境设计。该系统提供完整的声纹识别解决方案，包括说话人注册、声纹特征提取、实时验证、分布式存储、负载均衡和监控等功能。

## 核心特性

### 🎯 高精度识别
- 基于阿里3D Speaker模型，提供业界领先的声纹识别精度
- 支持多种音频格式（WAV、MP3、FLAC、M4A、OGG）
- 可配置的相似度阈值，平衡识别精度和误识率

### ⚡ 分布式架构
- 支持多节点集群部署
- 多种负载均衡策略（轮询、随机、最少连接、加权轮询、最少响应时间）
- 自动健康检查和故障转移
- 分布式声纹特征存储（内存、Redis、文件系统）

### 🔧 易于集成
- 完整的RESTful API接口
- Python客户端SDK
- 支持多种部署方式（Docker、Kubernetes）
- 详细的API文档和示例

### 📊 监控和管理
- 实时系统监控和指标收集
- Prometheus + Grafana监控面板
- 完整的日志管理和审计
- 集群状态和性能统计

### 🛡️ 安全可靠
- 支持API密钥认证
- 请求频率限制
- 数据加密和备份
- 高可用性和容错设计

## 技术架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Load Balancer  │    │  Monitoring     │
│   (Flask)       │◄──►│  (Round Robin)  │◄──►│  (Prometheus)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Voiceprint      │    │ Distributed     │    │ Health Check    │
│ Engine          │◄──►│ Storage         │◄──►│ Service         │
│ (3D Speaker)    │    │ (Redis/Memory)  │    │ (Auto Recovery) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 核心组件

- **声纹识别引擎**: 基于阿里达摩院 speech_campplus_sv_zh-cn_3dspeaker_16k
- **分布式存储**: 支持Redis、内存、文件系统的多级存储
- **负载均衡器**: 多种策略的智能负载分配
- **API网关**: 统一的API入口和路由管理
- **监控系统**: 完整的系统监控和告警

## 快速开始

### 1. 环境要求

- Python 3.9+
- Docker & Docker Compose
- Redis (可选，用于分布式存储)
- PostgreSQL (可选，用于数据持久化)

### 2. 安装部署

#### 使用Docker Compose（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd Edge-VoMID

# 一键部署
./scripts/deploy.sh deploy
```

#### 手动部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py --config config/production.yaml
```

### 3. 验证部署

```bash
# 健康检查
curl http://localhost:8080/health

# 查看服务状态
./scripts/deploy.sh status
```

## API使用示例

### Python客户端

```python
from client import VoMIDClient

# 创建客户端
client = VoMIDClient("http://localhost:8080")

# 注册声纹
user_id = client.register_voiceprint(
    name="张三",
    audio_file="audio/zhang_san.wav",
    metadata={"department": "IT", "role": "developer"}
)

# 验证声纹
result = client.verify_voiceprint(
    audio_file="audio/test.wav",
    threshold=0.6
)

if result.verified:
    print(f"验证成功: {result.user_id}, 置信度: {result.confidence}")
else:
    print("验证失败")
```

### REST API

```bash
# 注册声纹
curl -X POST http://localhost:8080/api/v1/voiceprint/register \
  -F "name=张三" \
  -F "audio=@audio/zhang_san.wav"

# 验证声纹
curl -X POST http://localhost:8080/api/v1/voiceprint/verify \
  -F "audio=@audio/test.wav" \
  -F "threshold=0.6"

# 获取统计信息
curl http://localhost:8080/api/v1/stats
```

## 配置说明

### 环境变量配置

```bash
# 应用配置
export VOIMID_ENVIRONMENT=production
export VOIMID_API_HOST=0.0.0.0
export VOIMID_API_PORT=8080

# 存储配置
export VOIMID_STORAGE_TYPE=redis
export VOIMID_REDIS_HOST=redis
export VOIMID_REDIS_PORT=6379

# 数据库配置
export VOIMID_DB_HOST=postgres
export VOIMID_DB_USER=voimid
export VOIMID_DB_PASSWORD=voimid_password
```

### 配置文件

支持YAML和JSON格式的配置文件：

```yaml
# config/production.yaml
environment: production
api:
  host: "0.0.0.0"
  port: 8080
  max_file_size: 10485760  # 10MB

storage:
  type: "redis"
  redis:
    host: "redis"
    port: 6379

model:
  name: "iic/speech_campplus_sv_zh-cn_3dspeaker_16k"
  device: "auto"
```

## 集群部署

### 多节点部署

```bash
# 启动多个节点
docker-compose up -d --scale voimid=3

# 配置负载均衡
# Nginx会自动将请求分发到不同的节点
```

### Kubernetes部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voimid
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voimid
  template:
    metadata:
      labels:
        app: voimid
    spec:
      containers:
      - name: voimid
        image: voimid:latest
        ports:
        - containerPort: 8080
        env:
        - name: VOIMID_STORAGE_TYPE
          value: "redis"
        - name: VOIMID_REDIS_HOST
          value: "redis-service"
```

## 监控和管理

### 访问监控面板

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **API文档**: http://localhost:8080/api/v1/docs

### 常用管理命令

```bash
# 查看服务状态
./scripts/deploy.sh status

# 查看日志
./scripts/deploy.sh logs

# 备份数据
./scripts/deploy.sh backup

# 重启服务
./scripts/deploy.sh restart
```

## 性能优化

### 系统调优

1. **模型优化**
   - 使用GPU加速（如果可用）
   - 调整批处理大小
   - 启用模型缓存

2. **存储优化**
   - 使用Redis集群
   - 配置适当的缓存策略
   - 定期清理过期数据

3. **网络优化**
   - 配置CDN加速
   - 启用HTTP/2
   - 优化负载均衡策略

### 性能指标

- **吞吐量**: 支持1000+ QPS
- **延迟**: 平均响应时间 < 200ms
- **可用性**: 99.9% 服务可用性
- **扩展性**: 支持水平扩展

## 使用场景

### 🔐 身份验证
- 语音门禁系统
- 电话客服身份确认
- 移动应用声纹登录

### 📞 通话监控
- 通话录音说话人识别
- 客服质量监控
- 欺诈检测

### 🎙️ 会议记录
- 会议发言者自动标注
- 会议纪要生成
- 多语言会议支持

### 🛡️ 安全防护
- 声纹反欺诈系统
- 金融交易验证
- 高安全等级访问控制

## 注意事项

1. **音频质量**: 建议使用清晰、无噪音的音频文件
2. **采样率**: 支持16kHz采样率，自动格式转换
3. **时长要求**: 建议音频时长在1-30秒之间
4. **阈值设置**: 根据实际场景调整相似度阈值
5. **数据安全**: 声纹特征经过加密存储
6. **合规性**: 遵循数据保护法规要求

## 开发和贡献

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行测试
pytest tests/

# 代码格式化
black .
flake8 .

# 生成文档
sphinx-build docs/ docs/_build/
```

### 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

本项目采用 Apache 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。


**Edge-VoMID** - 让分布式声纹认证更简单、更高效、更可靠