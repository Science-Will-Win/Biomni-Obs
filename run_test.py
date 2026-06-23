import json
import requests
import os
import sys
import re
import time
import logging
import uuid

# API 엔드포인트 설정 (원본과 동일)
API_URL = "http://localhost:8003/api/chat"
SESSION_DELETE_URL = "http://localhost:8003/api/session"
FEEDBACK_URL = "http://localhost:8003/api/feedback"

MAX_ATTEMPTS = 3

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

def setup_logger():
    # 단일 테스트이므로 콘솔에만 즉각적으로 로그를 출력하도록 단순화
    logger = logging.getLogger("SingleTestLogger")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

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
        logger.error("입력된 프롬프트가 없습니다.")
        return None
        
    logger.info(f"▶️ [ID: {instance_id}] 처리 시작... (Task: {task_name})")
    
    unique_session_id = f"test_{instance_id}_{uuid.uuid4().hex[:6]}"
    payload = {"message": prompt, "session_id": unique_session_id, "mode": "plan"}
    
    is_finally_correct = False
    final_trace_id = ""
    final_answer_text = ""
    final_messages = [] 
    final_status = "success"
    final_error_message = ""
    
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = requests.post(API_URL, json=payload, stream=True)
                response.raise_for_status() 
                
                content_type = response.headers.get('Content-Type', '')
                
                # ▼ 여기서 변수를 미리 초기화합니다 ▼
                current_answer = ""
                
                if 'text/event-stream' in content_type:
                    buffer = ""
                    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            buffer += chunk
                            while '\n\n' in buffer:
                                event_text, buffer = buffer.split('\n\n', 1)
                                
                                for line in event_text.split('\n'):
                                    if line.startswith("data: "):
                                        data_str = line[6:]
                                        if data_str.strip() == "[DONE]":
                                            continue
                                            
                                        try:
                                            data_json = json.loads(data_str)
                                            
                                            if data_json.get("type") == "error":
                                                raise Exception(data_json.get("error"))
                                                
                                            if "trace_id" in data_json:
                                                final_trace_id = data_json["trace_id"]
                                            
                                            # 🚀 핵심 추가: 토큰이 들어오면 계속 이어 붙입니다.
                                            if data_json.get("type") == "token" and "token" in data_json:
                                                current_answer += data_json["token"]
                                            
                                            # (만약 백엔드가 친절하게 최종 답을 따로 보내준다면 덮어씁니다)
                                            refined = data_json.get('refined_data', {})
                                            if refined.get("final_answer"):
                                                current_answer = refined["final_answer"]
                                            elif "final_answer" in data_json:
                                                current_answer = data_json["final_answer"]
                                                
                                        except json.JSONDecodeError:
                                            pass
                else:
                    # 스트리밍이 아닌 일반 JSON 응답인 경우
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
                    send_feedback(task_name, True, current_answer, logger, instance_id)
                    break
                else:
                    logger.info(f"  ❌ [ID: {instance_id} | 시도 {attempt}] 오답 | 실제: '{original_answer}' | AI요약: '{display_ans}'")
                    if attempt >= MAX_ATTEMPTS:
                        logger.info(f"  → [ID: {instance_id}] 최대 재시도 도달. 다음으로 넘어갑니다.")
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
            logger.info(f"  └─ 세션 정리 완료 ({unique_session_id})")
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

def run_single(input_file, target_instance_id):
    logger = setup_logger()
    
    if not os.path.exists(input_file):
        logger.error(f"오류: '{input_file}' 파일을 찾을 수 없습니다.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 문자열로 변환하여 안전하게 비교
    target_item = next((item for item in data if str(item.get('instance_id')) == str(target_instance_id)), None)

    if not target_item:
        logger.error(f"오류: {input_file} 내부에서 instance_id={target_instance_id} 인 항목을 찾을 수 없습니다.")
        return

    logger.info(f"💡 데이터 탐색 성공! instance_id={target_instance_id} 테스트를 시작합니다.")
    
    start_time = time.time()
    result = process_single_item(target_item, logger)
    end_time = time.time()
    
    print("\n" + "="*50)
    print("🎯 테스트 결과 요약")
    print("="*50)
    print(f"- 소요 시간 : {end_time - start_time:.2f} 초")
    print(f"- Trace ID  : {result.get('trace_id', 'N/A')}")
    print(f"- 정답 여부 : {'✅ 맞음' if result.get('is_correct') else '❌ 틀림'}")
    print(f"- 최종 상태 : {result.get('status')}")
    
    if result.get("error_message"):
        print(f"- 에러 메시지: {result.get('error_message')}")
        
    print("\n[전체 결과 JSON 반환값]")
    # 결과 JSON을 이쁘게 출력
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python test_single_instance.py <입력할_JSON_파일명> <테스트할_instance_id>")
        print("예시: python test_single_instance.py data.json 0")
        sys.exit(1)
        
    input_filename = sys.argv[1]
    target_id = sys.argv[2]
    run_single(input_filename, target_id)