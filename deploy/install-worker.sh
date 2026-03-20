#!/bin/bash
# AI Spider Worker 一键安装脚本
# 用法: curl -sSL http://MASTER_HOST:8901/api/v1/deploy/install-script | bash -s -- --master http://MASTER_HOST:8901 --token DEPLOY_TOKEN

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}✅ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# 检查root
if [ "$(id -u)" -ne 0 ]; then
    log_error "请使用 root 用户运行此脚本 (sudo bash ...)"
    exit 1
fi

# 参数解析
MASTER_URL=""
DEPLOY_TOKEN=""
CONCURRENCY=3
INSTALL_DIR="/opt/ai-spider-worker"
PYTHON_CMD=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --master)      MASTER_URL="$2"; shift 2;;
        --token)       DEPLOY_TOKEN="$2"; shift 2;;
        --concurrency) CONCURRENCY="$2"; shift 2;;
        --dir)         INSTALL_DIR="$2"; shift 2;;
        *) shift;;
    esac
done

if [ -z "$MASTER_URL" ]; then
    log_error "请指定 --master URL"
    echo "用法: bash install-worker.sh --master http://MASTER_HOST:8901 --token TOKEN"
    exit 1
fi

if [ -z "$DEPLOY_TOKEN" ]; then
    log_error "请指定 --token DEPLOY_TOKEN"
    exit 1
fi

echo ""
echo "🕷️  AI Spider Worker 安装程序"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Master:   $MASTER_URL"
echo "  安装目录: $INSTALL_DIR"
echo "  并发数:   $CONCURRENCY"
echo ""

# ── 1. 检测系统 ──
OS_TYPE=""
detect_os() {
    if [ -f /etc/redhat-release ]; then
        OS_TYPE="rhel"
        log_info "检测到 CentOS/RHEL 系统"
    elif [ -f /etc/debian_version ]; then
        OS_TYPE="debian"
        log_info "检测到 Ubuntu/Debian 系统"
    else
        log_warn "未识别的系统，将尝试通用安装"
        OS_TYPE="unknown"
    fi
}

# ── 2. 安装Python 3.11 ──
install_python() {
    # 检查常见路径
    for p in /www/python311/bin/python3.11 /usr/bin/python3.11 /usr/local/bin/python3.11; do
        if [ -x "$p" ]; then
            PYTHON_CMD="$p"
            log_info "Python 3.11 已安装: $PYTHON_CMD"
            return
        fi
    done

    if command -v python3.11 &>/dev/null; then
        PYTHON_CMD=$(which python3.11)
        log_info "Python 3.11 已安装: $PYTHON_CMD"
        return
    fi

    log_warn "Python 3.11 未找到，正在安装..."

    case "$OS_TYPE" in
        rhel)
            yum install -y python3.11 python3.11-pip 2>/dev/null || {
                log_warn "默认源安装失败，尝试 EPEL..."
                yum install -y epel-release 2>/dev/null || true
                yum install -y python3.11 python3.11-pip 2>/dev/null || {
                    log_warn "EPEL 安装失败，尝试从源码编译..."
                    install_python_from_source
                    return
                }
            }
            ;;
        debian)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -qq
            apt-get install -y -qq software-properties-common 2>/dev/null || true
            # Try direct install first (Debian 12+ / Ubuntu 23.04+)
            apt-get install -y -qq python3.11 python3.11-venv python3-pip 2>/dev/null || {
                log_warn "直接安装失败，尝试 deadsnakes PPA..."
                add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
                apt-get update -qq
                apt-get install -y -qq python3.11 python3.11-venv python3.11-distutils 2>/dev/null || {
                    log_warn "PPA 安装失败，尝试从源码编译..."
                    install_python_from_source
                    return
                }
            }
            ;;
        *)
            install_python_from_source
            return
            ;;
    esac

    PYTHON_CMD=$(which python3.11 2>/dev/null || echo "")
    if [ -z "$PYTHON_CMD" ]; then
        log_error "Python 3.11 安装失败"
        exit 1
    fi
    log_info "Python 3.11 安装完成: $PYTHON_CMD"
}

install_python_from_source() {
    log_warn "从源码编译 Python 3.11（可能需要几分钟）..."
    local build_deps=""
    if [ "$OS_TYPE" = "rhel" ]; then
        yum groupinstall -y "Development Tools" 2>/dev/null || true
        yum install -y openssl-devel bzip2-devel libffi-devel zlib-devel wget 2>/dev/null || true
    elif [ "$OS_TYPE" = "debian" ]; then
        apt-get install -y -qq build-essential libssl-dev zlib1g-dev libffi-dev wget 2>/dev/null || true
    fi
    cd /tmp
    wget -q https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
    tar xzf Python-3.11.9.tgz
    cd Python-3.11.9
    ./configure --enable-optimizations --prefix=/usr/local 2>&1 | tail -1
    make -j$(nproc) 2>&1 | tail -1
    make altinstall 2>&1 | tail -1
    cd /tmp && rm -rf Python-3.11.9*
    PYTHON_CMD=/usr/local/bin/python3.11
    if [ ! -x "$PYTHON_CMD" ]; then
        log_error "源码编译 Python 3.11 失败"
        exit 1
    fi
    log_info "Python 3.11 编译完成: $PYTHON_CMD"
}

# ── 3. 确保pip可用 ──
ensure_pip() {
    if ! $PYTHON_CMD -m pip --version &>/dev/null; then
        log_warn "pip 未找到，正在安装..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
    fi
    log_info "pip 版本: $($PYTHON_CMD -m pip --version 2>&1 | head -1)"
}

# ── 4. 下载Worker代码 ──
setup_worker() {
    # 如果已存在，备份
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "安装目录已存在，备份旧文件..."
        mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)" 2>/dev/null || true
    fi

    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    log_info "从 Master 下载 Worker 包..."
    local http_code
    http_code=$(curl -sSL -w "%{http_code}" -o worker-package.tar.gz \
        "$MASTER_URL/api/v1/deploy/worker-package?token=$DEPLOY_TOKEN")

    if [ "$http_code" != "200" ]; then
        log_error "下载失败 (HTTP $http_code)，请检查 token 是否有效"
        rm -f worker-package.tar.gz
        exit 1
    fi

    tar xzf worker-package.tar.gz
    rm -f worker-package.tar.gz
    log_info "Worker 代码已下载"

    # 安装依赖
    log_info "安装 Python 依赖..."
    $PYTHON_CMD -m pip install -q -r requirements-worker.txt 2>&1 | tail -3

    # 安装 playwright 浏览器
    log_info "安装 Playwright 浏览器（可能需要几分钟）..."
    $PYTHON_CMD -m playwright install chromium 2>&1 | tail -3
    $PYTHON_CMD -m playwright install-deps 2>&1 | tail -3 || true

    log_info "依赖安装完成"
}

# ── 5. 创建systemd服务 ──
create_service() {
    log_info "创建 systemd 服务..."

    cat > /etc/systemd/system/ai-spider-worker.service << SVCEOF
[Unit]
Description=AI Spider Worker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_CMD worker.py --master $MASTER_URL --concurrency $CONCURRENCY
Restart=always
RestartSec=5
Environment=PYTHONPATH=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
SVCEOF

    systemctl daemon-reload
    systemctl enable ai-spider-worker
    systemctl start ai-spider-worker
    log_info "服务已创建并启动"
}

# ── 6. 验证 ──
verify() {
    sleep 3
    if systemctl is-active ai-spider-worker >/dev/null 2>&1; then
        log_info "Worker 已启动并注册到 Master"
        echo "  状态: $(systemctl status ai-spider-worker --no-pager 2>&1 | grep Active)"
    else
        log_error "启动失败，查看日志:"
        journalctl -u ai-spider-worker -n 10 --no-pager 2>&1 || true
        echo ""
        log_warn "可以手动启动: cd $INSTALL_DIR && $PYTHON_CMD worker.py --master $MASTER_URL"
    fi
}

# ── 执行 ──
detect_os
install_python
ensure_pip
setup_worker
create_service
verify

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 安装完成！"
echo ""
echo "管理命令:"
echo "  systemctl status ai-spider-worker   # 查看状态"
echo "  systemctl restart ai-spider-worker  # 重启"
echo "  systemctl stop ai-spider-worker     # 停止"
echo "  journalctl -u ai-spider-worker -f   # 查看日志"
