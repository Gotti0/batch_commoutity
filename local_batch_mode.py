# -*- coding: utf-8 -*-
"""
Gemini API - Batch Mode (Local Environment Version)

이 스크립트는 Google Gemini API의 배치 모드를 로컬 환경에서 실행하는 방법을 보여줍니다.
Colab/Jupyter 노트북 환경에 특화된 코드를 제거하고, 로컬 실행에 맞게 수정되었습니다.

실행 전 필요한 라이브러리를 설치하세요:
pip install google-genai python-dotenv requests

또한, 프로젝트 루트 디렉터리에 .env 파일을 만들고 다음과 같이 API 키를 추가해야 합니다:
GEMINI_API_KEY="YOUR_API_KEY"
"""

import os
import json
import time
import base64
import requests
import logging
from dotenv import load_dotenv

# --- 로깅 설정 ---
log_file_path = 'batch_mode.log'
# 스크립트 실행 시 로그 파일 초기화
with open(log_file_path, 'w'):
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# google.genai 라이브러리 임포트
try:
    from google import genai
    from google.genai import types
except ImportError:
    logger.error("google-genai 라이브러리가 설치되지 않았습니다.")
    logger.error("터미널에서 'pip install google-genai'를 실행하여 설치해주세요.")
    exit()

# --- 1. 설정 (Setup) ---

# .env 파일에서 환경 변수 로드
load_dotenv()

# API 키 설정
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    logger.error("GEMINI_API_KEY가 설정되지 않았습니다.")
    logger.error(".env 파일에 GEMINI_API_KEY를 추가해주세요.")
    exit()

logger.info("API 키를 성공적으로 불러왔습니다.")

# API 클라이언트 초기화
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'api_version': 'v1alpha'})

# 사용할 모델 선택
MODEL_ID = "gemini-2.5-flash"
logger.info(f"사용할 모델: {MODEL_ID}")


# --- 2. 파일 기반 배치 작업 생성 ---
logger.info("\n--- 파일 기반 배치 작업 예제 시작 ---")
try:
    # 2.1. 입력 파일 준비 및 업로드
    requests_data_file = [
        {"key": "request_1", "request": {"contents": [{"parts": [{"text": "Explain how AI works in a few words"}]}]}},
        {"key": "request_2", "request": {"contents": [{"parts": [{"text": "Explain how quantum computing works in a few words"}]}]}}
    ]
    json_file_path = 'batch_requests.jsonl'

    logger.info(f"입력용 JSONL 파일 생성: {json_file_path}")
    with open(json_file_path, 'w') as f:
        for req in requests_data_file:
            f.write(json.dumps(req) + '\n')

    logger.info(f"File API에 파일 업로드 중: {json_file_path}")
    uploaded_batch_requests = client.files.upload(
        file=json_file_path,
        config=types.UploadFileConfig(
            display_name='batch-input-file-local',
            mime_type='application/json'
        )
    )
    logger.info(f"파일 업로드 완료: {uploaded_batch_requests.name}")

    # 2.2. 배치 작업 생성
    logger.info("배치 작업 생성 중...")
    batch_job_from_file = client.batches.create(
        model=MODEL_ID,
        src=uploaded_batch_requests.name,
        config={'display_name': 'my-batch-job-from-file-local'}
    )
    logger.info(f"파일 기반 배치 작업 생성 완료: {batch_job_from_file.name}")

    # 2.3. 작업 상태 모니터링
    job_name_file = batch_job_from_file.name
    logger.info(f"작업 상태 폴링 시작: {job_name_file}")
    while True:
        batch_job = client.batches.get(name=job_name_file)
        if batch_job.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            break
        logger.info(f"작업이 아직 완료되지 않았습니다. 현재 상태: {batch_job.state.name}. 10초 후 다시 확인합니다...")
        time.sleep(10)

    logger.info(f"작업 완료. 최종 상태: {batch_job.state.name}")
    if batch_job.state.name == 'JOB_STATE_FAILED':
        logger.error(f"오류: {batch_job.error}")

    # 2.4. 결과 검색 및 파싱
    if batch_job.state.name == 'JOB_STATE_SUCCEEDED':
        result_file_name = batch_job.dest.file_name
        logger.info(f"결과가 파일에 저장되었습니다: {result_file_name}")

        logger.info("결과 파일 다운로드 및 파싱 중...")
        file_content_bytes = client.files.download(file=result_file_name)
        file_content = file_content_bytes.decode('utf-8')

        for line in file_content.splitlines():
            if line:
                parsed_response = json.loads(line)
                logger.info(f"\n{json.dumps(parsed_response, indent=2)}")
                logger.info("-" * 20)
    else:
        logger.warning("작업이 성공적으로 완료되지 않았습니다.")

except Exception as e:
    logger.error(f"파일 기반 배치 작업 중 오류 발생: {e}", exc_info=True)

logger.info("--- 파일 기반 배치 작업 예제 종료 ---\n")


# --- 3. 인라인 요청으로 배치 작업 생성 ---
logger.info("\n--- 인라인 요청 배치 작업 예제 시작 ---")
try:
    # 3.1. 인라인 작업 생성 및 모니터링
    inline_requests_list = [
        {'contents': [{'parts': [{'text': 'Write a short poem about a cloud.'}]}]},
        {'contents': [{'parts': [{'text': 'Write a short poem about a cat.'}]}]}
    ]

    logger.info("인라인 배치 작업 생성 중...")
    batch_job_inline = client.batches.create(
        model=MODEL_ID,
        src=inline_requests_list,
        config={'display_name': 'my-batch-job-inline-local'}
    )
    logger.info(f"인라인 배치 작업 생성 완료: {batch_job_inline.name}")

    job_name_inline = batch_job_inline.name
    logger.info(f"작업 상태 폴링 시작: {job_name_inline}")
    while True:
        batch_job_inline = client.batches.get(name=job_name_inline)
        if batch_job_inline.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            break
        logger.info(f"작업이 아직 완료되지 않았습니다. 현재 상태: {batch_job_inline.state.name}. 10초 후 다시 확인합니다...")
        time.sleep(10)

    logger.info(f"작업 완료. 최종 상태: {batch_job_inline.state.name}")
    if batch_job_inline.state.name == 'JOB_STATE_FAILED':
        logger.error(f"오류: {batch_job_inline.error}")

    # 3.2. 인라인 결과 검색 및 출력
    if batch_job_inline.state.name == 'JOB_STATE_SUCCEEDED':
        logger.info("인라인 결과:")
        for i, inline_response in enumerate(batch_job_inline.dest.inlined_responses):
            logger.info(f"\n--- 응답 {i+1} ---")
            if inline_response.response:
                try:
                    logger.info(inline_response.response.text)
                except (AttributeError, ValueError):
                    logger.info(inline_response.response)
            elif inline_response.error:
                logger.error(f"오류: {inline_response.error}")
    else:
        logger.warning("작업이 성공적으로 완료되지 않았습니다.")

except Exception as e:
    logger.error(f"인라인 배치 작업 중 오류 발생: {e}", exc_info=True)

logger.info("--- 인라인 요청 배치 작업 예제 종료 ---\n")


# --- 4. 작업 관리 ---
logger.info("\n--- 작업 관리 예제 시작 ---")
try:
    # 4.1. 최근 배치 작업 목록 조회
    logger.info("최근 배치 작업 목록 조회:\n")
    batches = client.batches.list(config={'page_size': 10})
    for b in batches.page:
        logger.info(f"작업 이름: {b.name}")
        logger.info(f"  - 표시 이름: {b.display_name}")
        logger.info(f"  - 상태: {b.state.name}")
        logger.info(f"  - 생성 시간: {b.create_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if b.dest and not b.dest.file_name:
            logger.info("  - 유형: 인라인")
        elif b.dest:
            logger.info(f"  - 유형: 파일 기반 (출력: {b.dest.file_name})")
        logger.info("-" * 20)
except Exception as e:
    logger.error(f"작업 목록을 가져오는 중 오류 발생: {e}", exc_info=True)

logger.info("--- 작업 관리 예제 종료 ---\n")


# --- 5. 멀티모달 입력 예제 ---
logger.info("\n--- 멀티모달 입력 예제 시작 ---")
try:
    # 5.1. 이미지 파일 다운로드
    image_url = "https://storage.googleapis.com/generativeai-downloads/images/jetpack.jpg"
    image_path = "jetpack.jpg"
    logger.info(f"예제 이미지 다운로드 중: {image_url}")
    response = requests.get(image_url)
    response.raise_for_status()
    with open(image_path, 'wb') as f:
        f.write(response.content)
    logger.info(f"이미지 저장 완료: {image_path}")

    # 5.2. 이미지 파일 업로드
    logger.info(f"이미지 파일 업로드 중: {image_path}")
    image_file = client.files.upload(file=image_path)
    logger.info(f"이미지 파일 업로드 완료: {image_file.name}")

    # 5.3. 멀티모달 요청 데이터 생성
    multimodal_requests_data = [
        {"key": "request_1_text", "request": {"contents": [{"parts": [{"text": "Explain how AI works in a few words"}]}]}},
        {
            "key": "request_2_image",
            "request": {
                "contents": [{
                    "parts": [
                        {"text": "What is in this image? Describe it in detail."},
                        {"file_data": {"file_uri": image_file.uri, "mime_type": image_file.mime_type}}
                    ]
                }]
            }
        }
    ]

    multimodal_json_path = 'batch_requests_with_image.jsonl'
    logger.info(f"멀티모달 입력용 JSONL 파일 생성: {multimodal_json_path}")
    with open(multimodal_json_path, 'w') as f:
        for req in multimodal_requests_data:
            f.write(json.dumps(req) + '\n')

    # 5.4. 멀티모달 배치 작업 생성 (파일 업로드 및 작업 생성)
    logger.info(f"JSONL 파일 업로드 중: {multimodal_json_path}")
    batch_input_file_mm = client.files.upload(
        file=multimodal_json_path,
        config=types.UploadFileConfig(mime_type='application/json')
    )
    logger.info(f"JSONL 파일 업로드 완료: {batch_input_file_mm.name}")

    logger.info("멀티모달 배치 작업 생성 중...")
    batch_job_mm = client.batches.create(
        model=MODEL_ID,
        src=batch_input_file_mm.name,
        config={'display_name': 'my-batch-job-with-image-local'}
    )
    logger.info(f"멀티모달 배치 작업 생성 완료: {batch_job_mm.name}")
    logger.info("이제 해당 작업의 상태를 모니터링하고 결과를 확인할 수 있습니다.")

except requests.exceptions.RequestException as e:
    logger.error(f"이미지 다운로드 중 오류 발생: {e}", exc_info=True)
except Exception as e:
    logger.error(f"멀티모달 처리 중 오류 발생: {e}", exc_info=True)

logger.info("--- 멀티모달 입력 예제 종료 ---\n")


# --- 6. 멀티모달 출력 (이미지 생성) 예제 ---
logger.info("\n--- 멀티모달 출력 (이미지 생성) 예제 시작 ---")
try:
    # 6.1. 이미지 생성 요청 데이터 생성
    image_gen_requests = [
        {"key": "image_req_1", "request": {"contents": [{"parts": [{"text": "A big letter A surrounded by animals starting with the A letter"}]}], 'generation_config': {'response_modalities': ['TEXT', 'IMAGE']}}},
        {"key": "image_req_2", "request": {"contents": [{"parts": [{"text": "A big letter B surrounded by animals starting with the B letter"}]}], 'generation_config': {'response_modalities': ['TEXT', 'IMAGE']}}},
    ]

    image_gen_json_path = 'batch_image_gen_requests.jsonl'
    logger.info(f"이미지 생성 요청 JSONL 파일 생성: {image_gen_json_path}")
    with open(image_gen_json_path, 'w') as f:
        for req in image_gen_requests:
            f.write(json.dumps(req) + '\n')

    # 6.2. 이미지 생성 배치 작업 생성
    logger.info(f"JSONL 파일 업로드 중: {image_gen_json_path}")
    batch_input_file_img_gen = client.files.upload(
        file=image_gen_json_path,
        config=types.UploadFileConfig(mime_type='application/json')
    )
    logger.info(f"JSONL 파일 업로드 완료: {batch_input_file_img_gen.name}")

    logger.info("이미지 생성 배치 작업 생성 중...")
    batch_multimodal_job = client.batches.create(
        model="gemini-2.0-flash-preview-image-generation",
        src=batch_input_file_img_gen.name,
        config={'display_name': 'my-batch-image-gen-job-local'}
    )
    logger.info(f"이미지 생성 배치 작업 생성 완료: {batch_multimodal_job.name}")

    # 6.3. 이미지 생성 작업 상태 모니터링
    job_name_img_gen = batch_multimodal_job.name
    logger.info(f"작업 상태 폴링 시작: {job_name_img_gen}")
    while True:
        batch_job_img_gen = client.batches.get(name=job_name_img_gen)
        if batch_job_img_gen.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            break
        logger.info(f"작업이 아직 완료되지 않았습니다. 현재 상태: {batch_job_img_gen.state.name}. 10초 후 다시 확인합니다...")
        time.sleep(10)

    logger.info(f"작업 완료. 최종 상태: {batch_job_img_gen.state.name}")

    # 6.4. 이미지 생성 결과 처리
    if batch_job_img_gen.state.name == 'JOB_STATE_SUCCEEDED':
        result_file_name_img = batch_job_img_gen.dest.file_name
        logger.info(f"결과가 파일에 저장되었습니다: {result_file_name_img}")

        logger.info("결과 파일 다운로드 및 파싱 중...")
        file_content_bytes_img = client.files.download(file=result_file_name_img)
        file_content_img = file_content_bytes_img.decode('utf-8')

        image_count = 0
        for line in file_content_img.splitlines():
            if line:
                parsed_response = json.loads(line)
                for part in parsed_response['response']['candidates'][0]['content']['parts']:
                    if part.get('text'):
                        logger.info(f"생성된 텍스트: {part['text']}")
                    elif part.get('inlineData'):
                        image_count += 1
                        mime_type = part['inlineData']['mimeType']
                        image_data = base64.b64decode(part['inlineData']['data'])
                        
                        file_extension = mime_type.split('/')[-1]
                        image_filename = f"generated_image_{image_count}.{file_extension}"
                        with open(image_filename, "wb") as f:
                            f.write(image_data)
                        logger.info(f"이미지 저장 완료: {image_filename}")
    else:
        logger.warning("이미지 생성 작업이 성공적으로 완료되지 않았습니다.")
        if batch_job_img_gen.error:
            logger.error(f"오류: {batch_job_img_gen.error}")

except Exception as e:
    logger.error(f"이미지 생성 배치 작업 중 오류 발생: {e}", exc_info=True)

logger.info("--- 멀티모달 출력 (이미지 생성) 예제 종료 ---")