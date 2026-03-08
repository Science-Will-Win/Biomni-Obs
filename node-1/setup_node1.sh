#!/bin/bash

# 에러 발생 시 스크립트 중단
set -e

# --- [설정 변수] ---
# 워크스페이스를 /raid/sww 로 고정
WORKSPACE_DIR="/raid/sww"
BIOMNI_REPO_URL="https://github.com/Science-Will-Win/Biomni.git"
WEB_REPO_URL="https://github.com/Science-Will-Win/Biomni-Web.git"
WEB_BRANCH="aigen"

echo "============================================"
echo "🚀 Node-1 Setup Script Started..."
echo "============================================"

# 1. 필수 패키지 존재 여부 확인 (sudo 방지)
echo "1️⃣  Checking dependencies (Git, Curl)..."
for cmd in git curl; do
  if ! command -v $cmd &> /dev/null; then
    echo "❌ 에러: '$cmd' 명령어를 찾을 수 없습니다. 서버 관리자에게 설치를 요청하세요."
    exit 1
  fi
done
echo "✅ Git and Curl are ready."

# Node.js & npm 설치 (NVM을 사용하여 sudo 없이 유저 권한으로 안전하게 설치)
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js via NVM (No sudo required)..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    
    # NVM 환경 변수 즉시 적용
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    nvm install 20
    nvm use 20
else
    echo "✅ Node.js is already installed."
fi

# 2. Docker 설치 여부 확인 (설치는 sudo가 필요하므로 체크만 진행)
if ! command -v docker &> /dev/null; then
    echo "❌ 에러: Docker가 설치되어 있지 않습니다. 서버 관리자에게 설치 및 권한 부여를 요청하세요."
    exit 1
else
    echo "✅ Docker is already installed."
fi

# 3. 작업 디렉토리 설정 및 이동
echo "2️⃣  Setting up workspace at $WORKSPACE_DIR..."
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

# 4. 리포지토리 클론
echo "3️⃣  Cloning repositories into $WORKSPACE_DIR..."
if [ ! -d "Biomni" ]; then
    git clone "$BIOMNI_REPO_URL" Biomni
else
    echo "   Biomni repo already exists. Pulling latest..."
    cd Biomni && git pull && cd ..
fi

# 클론 로직 수정 (없을 때는 clone, 있을 때는 pull)
if [ ! -d "Biomni-Web" ]; then
    echo "   Cloning Biomni-Web ($WEB_BRANCH branch)..."
    git clone -b "$WEB_BRANCH" "$WEB_REPO_URL" Biomni-Web
else
    echo "   Biomni-Web repo already exists. Pulling latest from $WEB_BRANCH..."
    cd Biomni-Web && git fetch origin && git checkout "$WEB_BRANCH" && git pull origin "$WEB_BRANCH" && cd ..
fi

# 5. 환경 설정
echo "4️⃣  Configuring environment..."
cd Biomni-Web

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

# 6. Docker Base Image 빌드 및 Compose 실행
echo "5️⃣  Building Base Image and Starting Backend (Docker)..."

# 윈도우 줄바꿈(CRLF) 찌꺼기 제거 및 권한 부여
sed -i 's/\r$//' backend/entrypoint.sh 2>/dev/null || true
chmod +x backend/entrypoint.sh

# [추가된 부분] Dockerfile.base를 사용하여 biomni-base 이미지 먼저 빌드
echo "   Building Docker base image (biomni-base:latest)..."
docker build --no-cache -t biomni-base:latest -f backend/Dockerfile.base backend/

# sudo 없이 유저 권한으로 캐시를 100% 무시하고 깨끗하게 빌드 후 실행
echo "   Building main Docker image with --no-cache..."
docker compose build --no-cache
docker compose up -d

# 프론트엔드 패키지 설치 로직 누락 방지 (기존 스크립트 참고)
echo "6️⃣  Installing Frontend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    cd ..
fi

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
echo "👉 외부 접속을 위해 브라우저에서 서버의 IP 주소(포트 5173)로 접속하세요."
echo "============================================"