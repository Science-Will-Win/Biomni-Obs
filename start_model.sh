#!/bin/bash

# 1. 인자 2개(GPU 번호 2개)가 모두 입력되었는지 확인
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "❌ 에러: 두 개의 GPU 번호를 입력해 주세요."
    echo "사용법: ./start_model.sh <첫번째_GPU> <두번째_GPU>"
    echo "예시: ./start_model.sh 7 8"
    exit 1
fi

GPU1=$1
GPU2=$2
TARGET_GPUS="${GPU1},${GPU2}"

# 2. 작업 디렉토리 이동
cd /raid/sww || exit

# Conda 환경 불러오기 및 활성화
source /usr/local/miniconda3/etc/profile.d/conda.sh
conda activate sglang_env

# 3. HF_HOME 강제 설정 (공유 폴더 권한 문제 우회)
export HF_HOME=/raid/sww/.cache/huggingface_cache
echo "✅ 모델 캐시 경로를 개인 폴더로 설정했습니다: $HF_HOME"
export TRITON_CACHE_DIR=/raid/sww/.triton  # 이 줄을 추가하세요!
echo "✅ 모델 캐시 및 Triton 캐시 경로를 설정했습니다."
export TMPDIR=/raid/sww/tmp
export TEMP=/raid/sww/tmp
export TMP=/raid/sww/tmp

echo "✅ 캐시 및 임시 폴더 경로를 /raid 쪽으로 설정했습니다."

# 4. 모델 서버 백그라운드 실행 (입력받은 GPU 2개 적용, tp 2 적용)
echo "🚀 ${TARGET_GPUS}번 GPU를 사용하여 Biomni-R0 모델 서버를 시작합니다..."

nohup env CUDA_VISIBLE_DEVICES=$TARGET_GPUS python -m sglang.launch_server \
  --model-path biomni/Biomni-R0-32B-Preview \
  --port 30000 \
  --host 0.0.0.0 \
  --mem-fraction-static 0.9 \
  --tp 2 \
  --trust-remote-code \
  --context-length 131072 \
  --json-model-override-args '{"rope_scaling":{"rope_type":"yarn","factor":1.0,"original_max_position_embeddings":32768}, "max_position_embeddings": 131072}' \
  > sglang_server.log 2>&1 &

# 5. 종료를 위해 PID(프로세스 ID) 저장
echo $! > sglang_server.pid
echo "✅ 서버가 백그라운드에서 실행 중입니다. (PID: $(cat sglang_server.pid))"
echo "🔍 실시간 로그 확인: tail -f /raid/sww/sglang_server.log"