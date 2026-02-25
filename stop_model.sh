#!/bin/bash

cd /raid/sww || exit

if [ -f sglang_server.pid ]; then
    PID=$(cat sglang_server.pid)
    echo "🛑 모델 서버 프로세스(PID: $PID)를 종료합니다..."
    kill -9 $PID
    rm sglang_server.pid
    echo "✅ 서버가 성공적으로 종료되었습니다. 할당되었던 GPU가 비워졌습니다."
else
    echo "⚠️ 실행 중인 서버 기록(sglang_server.pid)을 찾을 수 없습니다."
    echo "만약 프로세스가 계속 살아있다면 'nvidia-smi'로 확인 후 직접 종료하세요."
fi