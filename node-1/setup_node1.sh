#!/bin/bash

# 에러 발생 시 스크립트 중단
set -e

# --- [설정 변수] ---
WORKSPACE_DIR="$HOME/Science_Will_Win"
BIOMNI_REPO_URL="https://github.com/Science-Will-Win/Biomni.git"
WEB_REPO_URL="https://github.com/Science-Will-Win/Biomni-Web.git"

echo "============================================"
echo "🚀 Node-1 Setup Script Started..."
echo "============================================"

# 1. 시스템 업데이트 및 필수 패키지 설치
echo "1️⃣  Installing dependencies..."
sudo apt-get update -y
sudo apt-get install -y git curl

# 2. Docker 설치 (이미 설치되어 있으면 건너뜀)
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    # 현재 사용자를 docker 그룹에 추가 (재로그인 필요 없이 적용되도록 newgrp 사용 시도)
    sudo usermod -aG docker $USER
else
    echo "✅ Docker is already installed."
fi

# 3. 작업 디렉토리 생성
echo "2️⃣  Setting up workspace at $WORKSPACE_DIR..."
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

# 4. 리포지토리 클론 (나란히 배치)
echo "3️⃣  Cloning repositories..."

# Biomni 원본 클론
if [ ! -d "Biomni" ]; then
    git clone "$BIOMNI_REPO_URL" Biomni
else
    echo "   Biomni repo already exists. Pulling latest..."
    cd Biomni && git pull && cd ..
fi

# Biomni-Web 클론
if [ ! -d "Biomni-Web" ]; then
    git clone "$WEB_REPO_URL" Biomni-Web
else
    echo "   Biomni-Web repo already exists. Pulling latest..."
    cd Biomni-Web && git pull && cd ..
fi

# 5. 환경 설정
echo "4️⃣  Configuring environment..."
cd Biomni-Web

# 데이터 폴더 생성
mkdir -p biomni_data

# .env 파일 생성 (없을 경우)
if [ ! -f ".env" ]; then
    echo "   Creating .env file template..."
    cat <<EOF > .env
# [API Keys - PLEASE UPDATE THESE]
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com

# [Paths]
BIOMNI_DATA_PATH=/app/data
PYTHONPATH=/app/biomni_repo
EOF
    echo "⚠️  WARNING: A dummy .env file has been created."
    echo "⚠️  YOU MUST EDIT '.env' WITH REAL API KEYS BEFORE RUNNING!"
fi

# 6. Docker Compose 실행
echo "5️⃣  Building and Starting Containers..."

# 권한 문제 방지를 위해 sudo 사용 (사용자가 그룹에 확실히 추가되기 전일 수 있음)
if groups | grep -q "docker"; then
    docker compose up -d --build
else
    echo "   Running with sudo..."
    sudo docker compose up -d --build
fi

echo "============================================"
echo "✅ Setup Complete!"
echo "--------------------------------------------"
echo "👉 Action Required: Edit the .env file with your API keys:"
echo "   nano $WORKSPACE_DIR/Biomni-Web/.env"
echo ""
echo "👉 After editing, restart the containers:"
echo "   cd $WORKSPACE_DIR/Biomni-Web"
echo "   docker compose down && docker compose up -d"
echo "============================================"