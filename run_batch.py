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

# API 엔드포인트 설정
API_URL = "http://localhost:8003/api/chat"
SESSION_DELETE_URL = "http://localhost:8003/api/session"
FEEDBACK_URL = "http://localhost:8003/api/feedback"  # 새로 뚫은 피드백 목적지

MAX_ATTEMPTS = 3     
MAX_WORKERS = 20      

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

def get_missing_and_max_ids(existing_results):
    instance_ids = {item['instance_id'] for item in existing_results if 'instance_id' in item}
    if not instance_ids:
        return set(), [], -1
    max_id = max(instance_ids)
    expected_ids = set(range(max_id + 1))
    missing_ids = sorted(list(expected_ids - instance_ids))
    return instance_ids, missing_ids, max_id

# 🚀 피드백을 API로 쏘는 독립 함수 추가
def send_feedback(task_name, is_correct, answer, logger, instance_id):
    payload = {
        "task_name": task_name,
        "tool_name": "general_tool",
        "is_correct": is_correct,
        "answer": answer
    }
    try:
        res = requests.post(FEEDBACK_URL, json=payload, timeout=5)
        res.raise_for_status()
        logger.info(f"  └─ [ID: {instance_id}] GraphDB 피드백 기록 성공")
    except Exception as e:
        logger.error(f"  └─ ⚠️ [ID: {instance_id}] GraphDB 피드백 전송 실패: {e}")

def process_single_item(item, logger):
    instance_id = item.get('instance_id', 'unknown')
    task_instance_id = item.get('task_instance_id', "")
    task_name = item.get('task_name', "")
    original_answer = item.get('answer', "")
    prompt = item.get('prompt', "")
    
    if not prompt:
        return None
        
    logger.info(f"▶️ [ID: {instance_id}] 처리 시작... (Task: {task_name})")
    
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
                
                sol_match = re.search(r'<solution>(.*?)</solution>', current_answer, re.DOTALL | re.IGNORECASE)
                sol_text = sol_match.group(1).strip() if sol_match else re.sub(r'<think>.*?</think>', '', current_answer, flags=re.DOTALL | re.IGNORECASE).strip()
                lines = [line.strip() for line in sol_text.split('\n') if line.strip()]
                display_ans = lines[-1] if lines else sol_text
                
                if len(display_ans) > 70:
                    display_ans = "..." + display_ans[-67:]
                
                if match_success:
                    logger.info(f"  ✅ [ID: {instance_id} | 시도 {attempt}] 정답 확인! | 실제: '{original_answer}' | AI요약: '{display_ans}'")
                    # 🚀 정답 시 API 호출 (UPVOTE)
                    send_feedback(task_name, True, current_answer, logger, instance_id)
                    break
                else:
                    logger.info(f"  ❌ [ID: {instance_id} | 시도 {attempt}] 오답 | 실제: '{original_answer}' | AI요약: '{display_ans}'")
                    if attempt >= MAX_ATTEMPTS:
                        logger.info(f"  → [ID: {instance_id}] 최대 재시도 도달. 다음으로 넘어갑니다.")
                        # 🚀 오답 시 API 호출 (DOWNVOTE)
                        send_feedback(task_name, False, current_answer, logger, instance_id)
                    else:
                        time.sleep(1)
                        
            except Exception as e:
                logger.warning(f"  ⚠️ [ID: {instance_id} | 시도 {attempt}] API 오류 발생: {e}")
                final_status = "error"
                final_error_message = str(e)
                if attempt < MAX_ATTEMPTS:
                    time.sleep(2)
                else:
                    logger.error(f"  ❌ [ID: {instance_id}] 에러로 인해 최대 재시도 초과.")
    
    finally:
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
        
    valid_data = [item for item in data if item.get('prompt') and item.get('instance_id') is not None]
    absolute_total = len(valid_data)
    
    results = []
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            logger.info(f"✅ 기존 결과 파일('{output_file}')을 불러왔습니다. (현재 {len(results)}개 완료됨)")
        except json.JSONDecodeError:
            logger.warning(f"⚠️ 기존 결과 파일이 손상되었거나 비어 있습니다. 새로 시작합니다.")
            results = []

    existing_ids, missing_ids, max_id = get_missing_and_max_ids(results)
    
    if existing_ids:
        logger.info(f"📊 최대 instance_id: {max_id}")
        if missing_ids:
            logger.info(f"🔍 누락된 instance_id (우선 처리 대상): {missing_ids}")
            
    items_to_process = []
    for item in valid_data:
        iid = item.get('instance_id')
        if iid in missing_ids or iid > max_id:
            items_to_process.append(item)

    items_to_process.sort(key=lambda x: x.get('instance_id', 999999))
    items_to_run = len(items_to_process)
    
    if items_to_run == 0:
        logger.info(f"🎉 모든 데이터({absolute_total}/{absolute_total})가 이미 처리되었습니다! 종료합니다.")
        return

    processed_count = absolute_total - items_to_run

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_item = {
            executor.submit(process_single_item, item, logger): item 
            for item in items_to_process
        }
        
        for future in concurrent.futures.as_completed(future_to_item):
            processed_count += 1
            try:
                result_item = future.result()
                if result_item is not None:
                    with file_lock:
                        results.append(result_item)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=4)
                logger.info(f"🔄 전체 진행률: {processed_count}/{absolute_total} 완료")
            except Exception as e:
                logger.error(f"스레드 실행 중 치명적 오류 발생: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python run_batch.py <입력할_JSON_파일명>")
        sys.exit(1)
        
    input_filename = sys.argv[1]
    run_batch(input_filename)