import json
import os
import logging
import urllib.request
from google import genai
from google.genai import types

from .job_tracker import JobTracker

logger = logging.getLogger(__name__)

class GeminiApiService:
    def __init__(self, config_manager):
        self.config = config_manager
        self.client = None
        self.job_tracker = JobTracker()
        api_key = self.config.get('gemini_api_key')
        if api_key and api_key != "YOUR_GEMINI_API_KEY":
            self.client = genai.Client(api_key=api_key)

    def _prepare_requests(self, source_file, model_id):
        """ConfigManager의 설정을 사용하여 요청 파일을 생성합니다."""
        requests_file = "temp_requests.jsonl"

        system_instruction = {"parts": [{"text": self.config.get('system_instruction')}]}
        prefill = self.config.get('prefill_cached_history', [])
        generation_config = {
            'temperature': self.config.get('temperature', 1.0),
            'top_p': self.config.get('top_p', 0.95),
            'thinkingConfig': {'thinking_budget': self.config.get('thinking_budget', 128) },
        }
        chunk_size = self.config.get('chunk_size', 5000)

        with open(source_file, 'r', encoding='utf-8') as f_in:
            content = f_in.read()

        chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]

        with open(requests_file, 'w', encoding='utf-8') as f_out:
            for i, chunk in enumerate(chunks):
                request_contents = prefill + [{'role': 'user', 'parts': [{'text': chunk}]}]
                request = {
                    "model": f"models/{model_id}",
                    "contents": request_contents,
                    "system_instruction": system_instruction,
                    "generation_config": generation_config,
                    "safety_settings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    ]
                }
                f_out.write(json.dumps({"key": f"chunk_{i+1}", "request": request}, ensure_ascii=False) + '\n')

        return requests_file

    def create_batch_job(self, source_file_path):
        """소스 파일로부터 배치 번역 작업을 생성하고 실행합니다."""
        if not self.client:
            raise ValueError("API client is not initialized. Check your API key.")

        model_id = self.config.get('model_name', 'gemini-1.5-pro')
        requests_file = self._prepare_requests(source_file_path, model_id)

        try:
            # 1. 파일 업로드
            logger.info(f"Uploading request file ('{requests_file}') to the File API.")
            uploaded_file = self.client.files.upload(
                file=requests_file,
                config=types.UploadFileConfig(mime_type='application/json')
            )
            logger.info(f"File uploaded successfully: {uploaded_file.name}")

            # 2. 배치 작업 생성
            logger.info("Creating the batch translation job.")
            model_name = f"models/{model_id}"
            batch_job = self.client.batches.create(
                model=model_name,
                src=uploaded_file.name,
                config={'display_name': f'translation-{os.path.basename(source_file_path)}'}
            )
            logger.info(f"Batch job created successfully: {batch_job.name}")
            return batch_job

        except Exception as e:
            logger.error(f"An error occurred during batch job creation: {e}", exc_info=True)
            # Re-raise the exception to be caught by the ViewModel
            raise e
        finally:
            # 3. 임시 파일 삭제
            if os.path.exists(requests_file):
                # os.remove(requests_file) # 디버깅을 위해 임시 주석 처리
                logger.info(f"Debugging: Temporary request file '{requests_file}' was not deleted.")

    def list_batch_jobs(self):
        if not self.client:
            return []
        # Add page_size to the config as per the example
        return self.client.batches.list(config={'page_size': 50})

    def download_and_process_results(self, job, save_path):
        """Downloads, parses, and saves the final text file for a given job."""
        if not self.client:
            raise ValueError("API client is not initialized.")

        logger.info(f"Starting result processing for job: {job.name}")

        # 1. Get the result file name
        if not (hasattr(job, 'dest') and hasattr(job.dest, 'file_name')):
            raise ValueError(f"Could not find destination file name for job '{job.name}'.")
        
        result_file_name = job.dest.file_name
        logger.info(f"Results are stored in file: {result_file_name}")

        # 2. Download the result file content
        try:
            logger.info("Downloading result file...")
            file_content_bytes = self.client.files.download(file=result_file_name)
            file_content = file_content_bytes.decode('utf-8')
            logger.info("Result file downloaded successfully.")
        except Exception as e:
            logger.error(f"Error downloading result file '{result_file_name}': {e}", exc_info=True)
            raise e

        # 3. Parse the results
        translations = {}
        max_key = 0
        logger.info("Parsing downloaded content...")
        for line in file_content.splitlines():
            if not line:
                continue
            
            try:
                parsed_response = json.loads(line)
                key_num = int(parsed_response['key'].split('_')[1])
                max_key = max(max_key, key_num)
                
                if 'response' in parsed_response and parsed_response['response'].get('candidates'):
                    candidate = parsed_response['response']['candidates'][0]
                    finish_reason = candidate.get('finish_reason', 'UNKNOWN')
                    
                    if finish_reason == "SAFETY":
                        full_response_str = json.dumps(parsed_response, indent=2, ensure_ascii=False)
                        translations[key_num] = f"[번역 차단됨 (SAFETY) - 전체 응답 객체:]\n{full_response_str}"
                        logger.error(f"Chunk {key_num} processing failed/blocked: Finish reason was SAFETY.")
                    else:
                        translations[key_num] = candidate.get('content', {}).get('parts', [{}])[0].get('text', '[번역 내용 없음]')
                
                elif 'response' in parsed_response:
                    full_response_str = json.dumps(parsed_response, indent=2, ensure_ascii=False)
                    feedback = parsed_response['response'].get('prompt_feedback', {})
                    translations[key_num] = f"[번역 차단됨 (Candidates 없음) - 전체 응답 객체:]\n{full_response_str}"
                    logger.error(f"Chunk {key_num} processing failed/blocked: 'candidates' list is empty. Feedback: {feedback}")
                
                else:
                    full_response_str = json.dumps(parsed_response, indent=2, ensure_ascii=False)
                    error_message = parsed_response.get('error', {}).get('message', '알 수 없는 오류')
                    translations[key_num] = f"[번역 실패 (No Response) - 전체 응답 객체:]\n{full_response_str}"
                    logger.error(f"Chunk {key_num} processing failed/blocked: {error_message}")

            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
                key_str = f"'{line.split(',')[0]}'" if ',' in line else "Unknown Key"
                max_key += 1
                translations[max_key] = f"[결과 라인 파싱 오류 - 원본 라인:]\n{line}"
                logger.warning(f"Exception while parsing result line for key {key_str}: {e}")

        # 4. Save the final processed text
        logger.info(f"Saving processed results to '{save_path}'")
        full_text = []
        for i in range(1, max_key + 1):
            full_text.append(translations.get(i, f"[문단 {i} 결과 누락]\n\n"))
        
        # Use the FileService to write the final text
        from .file_service import FileService
        FileService().write_text(save_path, "\n\n".join(full_text))
        
        logger.info("All processing finished successfully.")

    def delete_batch_job(self, job_name):
        if not self.client:
            raise ValueError("API client is not initialized.")
        self.client.batches.delete(name=job_name)
