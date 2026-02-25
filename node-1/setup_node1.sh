#!/bin/bash

# 에러 발생 시 스크립트 중단
set -e
cp ./.env /raid/sww/.env
cd /raid/sww

# --- [설정 변수] ---
WORKSPACE_DIR="$(pwd)"
BIOMNI_REPO_URL="https://github.com/Science-Will-Win/Biomni.git"
WEB_REPO_URL="https://github.com/Science-Will-Win/Biomni-Web.git"

echo "============================================"
echo "🚀 Node-1 Setup Script Started..."
echo "============================================"

# 1. 필수 명령어(git, curl) 확인
echo "1️⃣  Checking essential tools (Git, Curl)..."
for cmd in git curl; do
  if ! command -v $cmd &> /dev/null; then
    echo "❌ 에러: '$cmd' 명령어를 찾을 수 없습니다. 서버 관리자에게 설치를 요청하세요."
    exit 1
  fi
done
echo "✅ Git and Curl are ready."

# 2. Node.js & npm 설치 (NVM을 사용해 사용자 권한으로 설치)
if ! command -v node &> /dev/null; then
    echo "📦 NVM(Node Version Manager)을 사용하여 Node.js를 설치합니다..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    
    # 설치된 NVM을 현재 쉘 스크립트에 바로 적용
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    nvm install 20
    nvm use 20
else
    echo "✅ Node.js is already installed."
fi

# 3. Docker 존재 여부 확인 (설치는 관리자 권한이 필요하므로 체크만)
if ! command -v docker &> /dev/null; then
    echo "❌ 에러: Docker가 설치되어 있지 않습니다. 서버 관리자에게 Docker 설치 및 docker 그룹 권한을 요청하세요."
    exit 1
else
    echo "✅ Docker is available."
fi

# 4. 작업 디렉토리 설정
echo "2️⃣  Setting up workspace at $WORKSPACE_DIR..."
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

# 5. 리포지토리 클론
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

# 6. 환경 설정
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

# 7. Docker Compose 실행 (sudo 없이 실행)
echo "5️⃣  Building and Starting Backend (Docker)..."

# [추가된 부분] 윈도우식 줄바꿈(CRLF)을 리눅스식(LF)으로 변환하여 오류 방지
echo "   Fixing line endings for entrypoint.sh..."
sed -i 's/\r$//' backend/entrypoint.sh

# 실행 권한 부여
chmod +x backend/entrypoint.sh

# 현재 사용자가 docker 그룹에 속해있다고 가정하고 실행
docker compose up -d --build

# 8. 프론트엔드 패키지 설치
echo "6️⃣  Installing Frontend dependencies..."
cd frontend
# 스크립트 내에서 NVM을 로드했으므로 npm 사용 가능
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
echo "👉 외부 접속을 위해 브라우저에서 서버의 IP 주소(포트 5173)로 접속하세요."
echo "============================================"