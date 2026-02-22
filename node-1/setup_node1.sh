#!/bin/bash

# 에러 발생 시 스크립트 중단
set -e

# --- [설정 변수] ---
WORKSPACE_DIR="$(pwd)"
BIOMNI_REPO_URL="https://github.com/Science-Will-Win/Biomni.git"
WEB_REPO_URL="https://github.com/Science-Will-Win/Biomni-Web.git"

echo "============================================"
echo "🚀 Node-1 Setup Script Started..."
echo "============================================"

# 1. 시스템 업데이트 및 필수 패키지 설치
echo "1️⃣  Installing dependencies (Git, Curl, Node.js)..."
sudo apt-get update -y
sudo apt-get install -y git curl

# Node.js & npm 설치 (프론트엔드용)
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "✅ Node.js is already installed."
fi

# 2. Docker 설치 (이미 설치되어 있으면 건너뜀)
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker $USER
else
    echo "✅ Docker is already installed."
fi

# 3. 작업 디렉토리 확인
echo "2️⃣  Setting up workspace at $WORKSPACE_DIR..."
cd "$WORKSPACE_DIR"

# 4. 리포지토리 클론
echo "3️⃣  Cloning repositories..."
if [ ! -d "Biomni" ]; then
    git clone "$BIOMNI_REPO_URL" Biomni
else
    echo "   Biomni repo already exists. Pulling latest..."
    cd Biomni && git pull && cd ..
fi

if [ ! -d "Biomni-Web" ]; then
    git clone "$WEB_REPO_URL" Biomni-Web
else
    echo "   Biomni-Web repo already exists. Pulling latest..."
    cd Biomni-Web && git pull && cd ..
fi

# 5. 환경 설정
echo "4️⃣  Configuring environment..."
cd Biomni-Web
mkdir -p biomni_data

# .env 파일 복사 또는 생성
if [ -f "$WORKSPACE_DIR/.env" ]; then
    echo "   Found .env in the workspace directory. Copying to Biomni-Web..."
    cp "$WORKSPACE_DIR/.env" ./.env
    echo "✅ .env file successfully copied."
elif [ ! -f ".env" ]; then
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
fi

# 6. Docker Compose 실행 (백엔드)
echo "5️⃣  Building and Starting Backend (Docker)..."
# entrypoint.sh 권한 부여 (Permission denied 방지)
chmod +x backend/entrypoint.sh

if groups | grep -q "docker"; then
    docker compose up -d --build
else
    echo "   Running with sudo..."
    sudo docker compose up -d --build
fi

# 7. 프론트엔드 패키지 설치
echo "6️⃣  Installing Frontend dependencies..."
cd frontend
npm install
cd ..

echo "============================================"
echo "✅ Setup Complete!"
echo "--------------------------------------------"
echo "🔥 [How to Start the Frontend] 🔥"
echo "백엔드(Docker)는 백그라운드에서 실행 중입니다."
echo "UI(프론트엔드)를 띄우려면 새로운 터미널에서 다음 명령어를 실행하세요:"
echo ""
echo "   cd $WORKSPACE_DIR/Biomni-Web/frontend"
echo "   npm run dev -- --host"
echo ""
echo "👉 외부 접속을 위해 브라우저에서 노드의 IP 주소(포트 5173)로 접속하세요."
echo "============================================"