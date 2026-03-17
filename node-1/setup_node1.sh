#!/bin/bash

set -e

WORKSPACE_DIR="/raid/sww"
WEB_REPO_URL="https://github.com/Science-Will-Win/Biomni-Web.git"
WEB_BRANCH="aigen"
# 현재 스크립트가 실행된 경로 (node-1 폴더)
NODE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "🚀 Node-1 Setup Script Started..."
echo "============================================"

# Node.js & npm 설치
if ! command -v node &> /dev/null; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 20 && nvm use 20
fi

# 작업 디렉토리 설정
mkdir -p "$WORKSPACE_DIR/models"
cd "$WORKSPACE_DIR"

# 1. node-1의 docker-compose.yml을 워크스페이스로 복사
cp "$NODE_DIR/docker-compose.yml" ./docker-compose.yml

# 2. .env 파일 준비
if [ ! -f ".env" ] && [ -f "$NODE_DIR/.env.example" ]; then
    cp "$NODE_DIR/.env.example" ./.env
fi

# 3. Docker 백엔드 실행 (Hub 이미지 다운로드 후 바로 실행)
echo "🐳 Starting Backend Docker Containers..."
docker compose pull
docker compose up -d

# 4. 프론트엔드 구동을 위해 Biomni-Web만 클론 (Biomni는 불필요!)
if [ ! -d "Biomni-Web" ]; then
    git clone -b "$WEB_BRANCH" "$WEB_REPO_URL" Biomni-Web
else
    cd Biomni-Web && git fetch origin && git checkout "$WEB_BRANCH" && git pull origin "$WEB_BRANCH" && cd ..
fi

# 5. 프론트엔드 실행
echo "🌐 Starting Frontend..."
cd Biomni-Web/frontend
npm install
npx kill-port 5173 >/dev/null 2>&1 || true
nohup npm run dev -- --host > frontend_run.log 2>&1 &

echo "============================================"
echo "✅ All Done! System is running."
echo "👉 Frontend: http://<서버_IP>:5173"
echo "============================================"