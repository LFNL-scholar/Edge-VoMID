#!/bin/bash

# Edge-VoMID 部署脚本
# 支持单机部署和集群部署

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    log_success "系统依赖检查通过"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p data/voiceprints
    mkdir -p logs
    mkdir -p models
    mkdir -p nginx
    mkdir -p monitoring
    
    log_success "目录创建完成"
}

# 生成配置文件
generate_configs() {
    log_info "生成配置文件..."
    
    # 生成环境变量文件
    if [ ! -f .env ]; then
        cat > .env << EOF
# Edge-VoMID 环境变量配置

# 应用配置
VOIMID_ENVIRONMENT=production
VOIMID_DEBUG=false

# API配置
VOIMID_API_HOST=0.0.0.0
VOIMID_API_PORT=8080

# 存储配置
VOIMID_STORAGE_TYPE=redis
VOIMID_REDIS_HOST=redis
VOIMID_REDIS_PORT=6379

# 数据库配置
VOIMID_DB_HOST=postgres
VOIMID_DB_USER=voimid
VOIMID_DB_PASSWORD=voimid_password
VOIMID_DB_NAME=voimid

# 安全配置
VOIMID_SECRET_KEY=$(openssl rand -hex 32)
VOIMID_JWT_SECRET=$(openssl rand -hex 32)
EOF
        log_success "环境变量文件已生成"
    else
        log_info "环境变量文件已存在，跳过生成"
    fi
    
    # 生成Nginx配置
    if [ ! -f nginx/nginx.conf ]; then
        cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream voimid_backend {
        server voimid:8080;
    }
    
    server {
        listen 80;
        server_name localhost;
        
        # 健康检查
        location /health {
            proxy_pass http://voimid_backend/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # API代理
        location /api/ {
            proxy_pass http://voimid_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # 文件上传配置
            client_max_body_size 10M;
            proxy_read_timeout 300;
            proxy_connect_timeout 300;
            proxy_send_timeout 300;
        }
        
        # 静态文件
        location /static/ {
            alias /app/static/;
            expires 1d;
        }
    }
}
EOF
        log_success "Nginx配置文件已生成"
    fi
    
    # 生成Prometheus配置
    if [ ! -f monitoring/prometheus.yml ]; then
        cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'voimid'
    static_configs:
      - targets: ['voimid:8080']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 30s
EOF
        log_success "Prometheus配置文件已生成"
    fi
}

# 构建镜像
build_images() {
    log_info "构建Docker镜像..."
    
    docker-compose build --no-cache
    
    log_success "Docker镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    # 启动基础服务
    docker-compose up -d redis postgres
    
    # 等待数据库启动
    log_info "等待数据库启动..."
    sleep 10
    
    # 启动主服务
    docker-compose up -d voimid
    
    # 启动监控服务
    docker-compose up -d prometheus grafana
    
    # 启动负载均衡器
    docker-compose up -d nginx
    
    log_success "所有服务启动完成"
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    
    # 等待服务启动
    sleep 30
    
    # 检查健康状态
    if curl -f http://localhost/health > /dev/null 2>&1; then
        log_success "服务健康检查通过"
    else
        log_warning "服务健康检查失败，请检查日志"
    fi
    
    # 显示服务状态
    docker-compose ps
}

# 显示访问信息
show_access_info() {
    log_info "服务访问信息："
    echo "================================"
    echo "API服务: http://localhost/api/v1"
    echo "健康检查: http://localhost/health"
    echo "Prometheus: http://localhost:9090"
    echo "Grafana: http://localhost:3000 (admin/admin)"
    echo "================================"
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    docker-compose down
    log_success "服务已停止"
}

# 清理数据
clean_data() {
    log_warning "这将删除所有数据，包括声纹记录和数据库数据"
    read -p "确定要继续吗？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "清理数据..."
        docker-compose down -v
        docker system prune -f
        rm -rf data logs models
        log_success "数据清理完成"
    else
        log_info "取消清理操作"
    fi
}

# 显示日志
show_logs() {
    docker-compose logs -f voimid
}

# 备份数据
backup_data() {
    log_info "备份数据..."
    
    backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    # 备份数据目录
    if [ -d "data" ]; then
        cp -r data "$backup_dir/"
    fi
    
    # 备份数据库
    docker-compose exec -T postgres pg_dump -U voimid voimid > "$backup_dir/database.sql"
    
    # 备份Redis
    docker-compose exec -T redis redis-cli BGSAVE
    docker cp "$(docker-compose ps -q redis):/data/dump.rdb" "$backup_dir/"
    
    log_success "数据备份完成: $backup_dir"
}

# 恢复数据
restore_data() {
    log_warning "这将覆盖现有数据"
    read -p "确定要继续吗？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "可用的备份目录："
        ls -d backup_* 2>/dev/null || echo "没有找到备份目录"
        read -p "请输入备份目录名称: " backup_dir
        
        if [ -d "$backup_dir" ]; then
            log_info "恢复数据..."
            
            # 恢复数据目录
            if [ -d "$backup_dir/data" ]; then
                rm -rf data
                cp -r "$backup_dir/data" .
            fi
            
            # 恢复数据库
            if [ -f "$backup_dir/database.sql" ]; then
                docker-compose exec -T postgres psql -U voimid -d voimid < "$backup_dir/database.sql"
            fi
            
            log_success "数据恢复完成"
        else
            log_error "备份目录不存在: $backup_dir"
        fi
    else
        log_info "取消恢复操作"
    fi
}

# 主菜单
show_menu() {
    echo "Edge-VoMID 部署管理脚本"
    echo "=========================="
    echo "1. 完整部署 (检查依赖 + 构建 + 启动)"
    echo "2. 启动服务"
    echo "3. 停止服务"
    echo "4. 重启服务"
    echo "5. 检查服务状态"
    echo "6. 查看日志"
    echo "7. 备份数据"
    echo "8. 恢复数据"
    echo "9. 清理数据"
    echo "0. 退出"
    echo "=========================="
}

# 主函数
main() {
    case "${1:-menu}" in
        "deploy")
            check_dependencies
            create_directories
            generate_configs
            build_images
            start_services
            check_services
            show_access_info
            ;;
        "start")
            start_services
            check_services
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            stop_services
            start_services
            check_services
            ;;
        "status")
            check_services
            ;;
        "logs")
            show_logs
            ;;
        "backup")
            backup_data
            ;;
        "restore")
            restore_data
            ;;
        "clean")
            clean_data
            ;;
        "menu"|*)
            show_menu
            read -p "请选择操作 (0-9): " choice
            case $choice in
                1) main deploy ;;
                2) main start ;;
                3) main stop ;;
                4) main restart ;;
                5) main status ;;
                6) main logs ;;
                7) main backup ;;
                8) main restore ;;
                9) main clean ;;
                0) exit 0 ;;
                *) log_error "无效选择" ;;
            esac
            ;;
    esac
}

# 执行主函数
main "$@"
