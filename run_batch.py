import json
import requests
import os
import sys
import re
import time
import logging
import uuid
import concurrent.futures
import threading

# 백엔드 서버 주소
API_URL = "http://localhost:8002/api/chat"
SESSION_DELETE_URL = "http://localhost:8002/api/session"
MAX_ATTEMPTS = 3     # 최대 재시도 횟수
MAX_WORKERS = 5      # 🚀 동시에 병렬로 실행할 문제 개수 (서버 GPU/CPU 사양에 맞춰 조절하세요. 5~10 권장)

# 🚀 다중 스레드 환경에서 파일 쓰기 충돌을 막기 위한 Lock
file_lock = threading.Lock()

def is_correct(original, generated):
    if not original or not generated:
        return False
        
    orig = str(original).strip().lower()
    gen = str(generated).strip()

    sol_match = re.search(r'<solution>(.*?)</solution>', gen, re.DOTALL | re.IGNORECASE)
    content = sol_match.group(1).strip() if sol_match else re.sub(r'<think>.*?</think>', '', gen, flags=re.DOTALL | re.IGNORECASE).strip()

    content = re.sub(r'(?i)(?:#+\s*)?references?\s*:?.*', '', content, flags=re.DOTALL)
    content = re.sub(r'(?i)참고\s*문헌.*', '', content, flags=re.DOTALL)
    content = content.strip()

    conclusion_match = re.search(r'(?i)(?:#+\s*)?(?:conclusion|final answer|결론)(.*)', content, flags=re.DOTALL)
    if conclusion_match:
        target_text = conclusion_match.group(1).strip()
    else:
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        target_text = " ".join(paragraphs[-2:]) if paragraphs else content

    target_text = target_text.lower()
    
    tokens = re.findall(r'[a-z0-9_-]+', target_text)
    if not tokens:
        return False

    if len(orig) == 1 and orig.isalnum():
        if re.search(fr'\b(?:is|answer|method|option|choice)\s*[:\*]*\s*{orig}\b', target_text):
            return True
        if tokens[0] == orig or tokens[-1] == orig:
            return True
        return False
    else:
        pattern = r'\b' + re.escape(orig) + r'\b'
        if re.search(pattern, target_text):
            return True
        return False

def setup_logger(log_file):
    logger = logging.getLogger("BatchLogger")
    logger.setLevel(logging.INFO)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# 🚀 단일 데이터 처리를 담당하는 함수 (스레드 워커가 개별적으로 실행)
def process_single_item(item, logger):
    instance_id = item.get('instance_id', 'unknown')
    task_instance_id = item.get('task_instance_id', "")
    task_name = item.get('task_name', "")
    original_answer = item.get('answer', "")
    prompt = item.get('prompt', "")
    
    if not prompt:
        return None
        
    logger.info(f"▶️ [ID: {instance_id}] 처리 시작... (Task: {task_name})")
    
    # 🚀 병렬 처리를 위해 각 스레드(문제)마다 고유한 세션 ID 할당 (서로 컨텍스트가 섞이는 것 완벽 방지)
    unique_session_id = f"batch_{instance_id}_{uuid.uuid4().hex[:6]}"
    payload = {"message": prompt, "session_id": unique_session_id}
    
    is_finally_correct = False
    final_trace_id = ""
    final_answer_text = ""
    final_messages = [] 
    final_status = "success"
    final_error_message = ""
    
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = requests.post(API_URL, json=payload)
                response.raise_for_status() 
                
                response_data = response.json()
                
                refined = response_data.get('refined_data', {})
                current_answer = refined.get("final_answer") or response_data.get('final_answer') or response_data.get('response', '')
                final_trace_id = refined.get("trace_id") or response_data.get("trace_id", "")
                
                match_success = is_correct(original_answer, current_answer)
                is_finally_correct = match_success
                final_answer_text = current_answer
                final_messages = refined.get("messages", [])
                
                final_status = "success"
                final_error_message = ""
                
                sol_match = re.search(r'<solution>(.*?)</solution>', current_answer, re.DOTALL | re.IGNORECASE)
                sol_text = sol_match.group(1).strip() if sol_match else re.sub(r'<think>.*?</think>', '', current_answer, flags=re.DOTALL | re.IGNORECASE).strip()
                lines = [line.strip() for line in sol_text.split('\n') if line.strip()]
                display_ans = lines[-1] if lines else sol_text
                
                if len(display_ans) > 70:
                    display_ans = "..." + display_ans[-67:]
                
                if match_success:
                    logger.info(f"  ✅ [ID: {instance_id} | 시도 {attempt}] 정답 확인! | 실제: '{original_answer}' | AI요약: '{display_ans}'")
                    break
                else:
                    logger.info(f"  ❌ [ID: {instance_id} | 시도 {attempt}] 오답 | 실제: '{original_answer}' | AI요약: '{display_ans}'")
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(1)
                    else:
                        logger.info(f"  → [ID: {instance_id}] 최대 재시도 도달. 다음으로 넘어갑니다.")
                        
            except Exception as e:
                logger.warning(f"  ⚠️ [ID: {instance_id} | 시도 {attempt}] API 오류 발생: {e}")
                final_status = "error"
                final_error_message = str(e)
                if attempt < MAX_ATTEMPTS:
                    time.sleep(2)
                else:
                    logger.error(f"  ❌ [ID: {instance_id}] 에러로 인해 최대 재시도 초과.")
    
    finally:
        # 🚀 메모리 누수 방지: 처리가 완전히 끝난 후 백엔드에 세션(에이전트) 삭제 요청
        try:
            requests.delete(f"{SESSION_DELETE_URL}/{unique_session_id}", timeout=5)
        except Exception:
            pass

    return {
        "instance_id": instance_id,
        "task_instance_id": task_instance_id,
        "task_name": task_name,
        "original_answer": original_answer,
        "status": final_status,
        "is_correct": is_finally_correct,
        "error_message": final_error_message,
        "trace_id": final_trace_id,
        "final_answer": final_answer_text,
        "messages": final_messages
    }


def run_batch(input_file):
    if not os.path.exists(input_file):
        print(f"오류: '{input_file}' 파일을 찾을 수 없습니다.")
        return

    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}_results.json"
    log_file = f"{base_name}_run.log"

    logger = setup_logger(log_file)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = []
    total_items = len(data)
    processed_count = 0
    
    logger.info(f"[{input_file}] 총 {total_items}개의 데이터 병렬 처리를 시작합니다... (워커 수: {MAX_WORKERS})")
    logger.info("======================================================")

    # 🚀 ThreadPoolExecutor를 이용한 병렬 처리 스케줄링
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 모든 항목을 스레드 풀에 맵핑하여 제출
        future_to_item = {
            executor.submit(process_single_item, item, logger): item 
            for item in data if item.get('prompt')
        }
        
        # 🚀 처리가 완료되는 순서대로 결과 수집
        for future in concurrent.futures.as_completed(future_to_item):
            processed_count += 1
            try:
                result_item = future.result()
                if result_item is not None:
                    # 🚀 여러 스레드가 동시에 파일에 쓰는 것을 방지하기 위해 Lock 획득
                    with file_lock:
                        results.append(result_item)
                        # 중간 결과 덮어쓰기 저장
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=4)
                            
                logger.info(f"🔄 전체 진행률: {processed_count}/{total_items} 완료")
            except Exception as e:
                logger.error(f"스레드 실행 중 치명적 오류 발생: {e}")

    logger.info("======================================================")
    logger.info("모든 병렬 처리가 완료되었습니다!")
    logger.info(f"최종 결과 파일: '{output_file}'")
    logger.info(f"실행 로그 파일: '{log_file}'")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python run_batch.py <입력할_JSON_파일명>")
        sys.exit(1)
        
    input_filename = sys.argv[1]
    run_batch(input_filename)