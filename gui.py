# -*- coding: utf-8 -*-
"""
Gemini API - Batch Mode (GUI Version)

local_batch_mode.py 스크립트에 Tkinter GUI를 추가한 버전입니다.
각 배치 작업을 버튼으로 실행하고, 실시간 로그와 결과를 GUI에서 확인할 수 있습니다.

사전 준비:
1. pip install google-genai python-dotenv requests Pillow
2. .env 파일에 GEMINI_API_KEY="YOUR_API_KEY" 설정
"""

import os
import json
import time
import base64
import requests
import logging
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from dotenv import load_dotenv
from PIL import Image, ImageTk

# google.genai 라이브러리 임포트
try:
    from google import genai
    from google.genai import types
except ImportError:
    messagebox.showerror("오류", "google-genai 라이브러리가 설치되지 않았습니다.\n'pip install google-genai'를 실행해주세요.")
    exit()

# --- 로깅 설정 ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

class BatchLogic:
    """Gemini API 배치 작업 로직을 처리하는 클래스"""
    def __init__(self, logger):
        self.logger = logger
        self.client = None
        self.model_id = "gemini-2.5-flash"
        self.image_gen_model_id = "gemini-2.0-flash-preview-image-generation"

    def initialize_client(self):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error("GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")
            return False
        
        try:
            self.client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
            self.logger.info("Gemini API 클라이언트가 성공적으로 초기화되었습니다.")
            self.logger.info(f"기본 모델: {self.model_id}")
            return True
        except Exception as e:
            self.logger.error(f"API 클라이언트 초기화 중 오류 발생: {e}", exc_info=True)
            return False

    def _monitor_job(self, job_name):
        self.logger.info(f"작업 상태 폴링 시작: {job_name}")
        while True:
            job = self.client.batches.get(name=job_name)
            if job.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
                self.logger.info(f"작업 완료. 최종 상태: {job.state.name}")
                if job.state.name == 'JOB_STATE_FAILED':
                    self.logger.error(f"오류: {job.error}")
                return job
            self.logger.info(f"작업 진행 중... 현재 상태: {job.state.name}. 10초 후 다시 확인합니다.")
            time.sleep(10)

    def run_file_based_job(self):
        try:
            requests_data = [
                {"key": "req_1", "request": {"contents": [{"parts": [{"text": "Explain AI in a few words"}]}]}},
                {"key": "req_2", "request": {"contents": [{"parts": [{"text": "Explain quantum computing simply"}]}]}}
            ]
            json_path = 'batch_requests.jsonl'
            self.logger.info(f"입력용 JSONL 파일 생성: {json_path}")
            with open(json_path, 'w') as f:
                for req in requests_data: f.write(json.dumps(req) + '\n')

            self.logger.info(f"File API에 파일 업로드 중: {json_path}")
            uploaded_file = self.client.files.upload(file=json_path, config=types.UploadFileConfig(mime_type='application/json'))
            self.logger.info(f"파일 업로드 완료: {uploaded_file.name}")

            self.logger.info("배치 작업 생성 중...")
            job = self.client.batches.create(model=self.model_id, src=uploaded_file.name, config={'display_name': 'gui-file-job'})
            self.logger.info(f"배치 작업 생성 완료: {job.name}")

            completed_job = self._monitor_job(job.name)
            if completed_job.state.name == 'JOB_STATE_SUCCEEDED':
                result_file = completed_job.dest.file_name
                self.logger.info(f"결과 파일 다운로드 및 파싱 중: {result_file}")
                content = self.client.files.download(file=result_file).decode('utf-8')
                for line in content.splitlines():
                    if line: self.logger.info(f"\n{json.dumps(json.loads(line), indent=2)}")
        except Exception as e:
            self.logger.error(f"파일 기반 작업 중 오류: {e}", exc_info=True)

    def run_inline_job(self):
        try:
            requests_list = [
                {'contents': [{'parts': [{'text': 'Write a short poem about a cloud.'}]}]},
                {'contents': [{'parts': [{'text': 'Write a short poem about a cat.'}]}]}
            ]
            self.logger.info("인라인 배치 작업 생성 중...")
            job = self.client.batches.create(model=self.model_id, src=requests_list, config={'display_name': 'gui-inline-job'})
            self.logger.info(f"인라인 배치 작업 생성 완료: {job.name}")

            completed_job = self._monitor_job(job.name)
            if completed_job.state.name == 'JOB_STATE_SUCCEEDED':
                self.logger.info("인라인 결과:")
                for i, resp in enumerate(completed_job.dest.inlined_responses):
                    self.logger.info(f"\n--- 응답 {i+1} ---")
                    if resp.response: self.logger.info(resp.response.text)
                    elif resp.error: self.logger.error(f"오류: {resp.error}")
        except Exception as e:
            self.logger.error(f"인라인 작업 중 오류: {e}", exc_info=True)

    def run_multimodal_input_job(self):
        try:
            img_url = "https://storage.googleapis.com/generativeai-downloads/images/jetpack.jpg"
            img_path = "jetpack.jpg"
            self.logger.info(f"예제 이미지 다운로드: {img_url}")
            response = requests.get(img_url)
            response.raise_for_status()
            with open(img_path, 'wb') as f: f.write(response.content)
            
            self.logger.info(f"이미지 파일 업로드: {img_path}")
            img_file = self.client.files.upload(file=img_path)
            self.logger.info(f"이미지 파일 업로드 완료: {img_file.name}")

            requests_data = [
                {"key": "req_img", "request": {"contents": [{"parts": [
                    {"text": "What is in this image? Describe it."},
                    {"file_data": {"file_uri": img_file.uri, "mime_type": img_file.mime_type}}
                ]}]}}
            ]
            json_path = 'batch_multimodal_requests.jsonl'
            with open(json_path, 'w') as f: f.write(json.dumps(requests_data[0]) + '\n')

            uploaded_file = self.client.files.upload(file=json_path, config=types.UploadFileConfig(mime_type='application/json'))
            job = self.client.batches.create(model=self.model_id, src=uploaded_file.name, config={'display_name': 'gui-multimodal-job'})
            self.logger.info(f"멀티모달 배치 작업 생성 완료: {job.name}")
            
            completed_job = self._monitor_job(job.name)
            if completed_job.state.name == 'JOB_STATE_SUCCEEDED':
                result_file = completed_job.dest.file_name
                self.logger.info(f"결과 파일 다운로드 및 파싱 중: {result_file}")
                content = self.client.files.download(file=result_file).decode('utf-8')
                for line in content.splitlines():
                    if line: self.logger.info(f"\n{json.dumps(json.loads(line), indent=2)}")
        except Exception as e:
            self.logger.error(f"멀티모달 입력 작업 중 오류: {e}", exc_info=True)

    def run_image_generation_job(self, image_callback):
        try:
            requests_data = [
                {"key": "img_req_1", "request": {"contents": [{"parts": [{"text": "A photorealistic image of a cat wearing a wizard hat"}]}], 'generation_config': {'response_modalities': ['TEXT', 'IMAGE']}}},
                {"key": "img_req_2", "request": {"contents": [{"parts": [{"text": "A beautiful watercolor painting of a sunset over a lake"}]}], 'generation_config': {'response_modalities': ['TEXT', 'IMAGE']}}},
            ]
            json_path = 'batch_image_gen_requests.jsonl'
            with open(json_path, 'w') as f:
                for req in requests_data: f.write(json.dumps(req) + '\n')

            uploaded_file = self.client.files.upload(file=json_path, config=types.UploadFileConfig(mime_type='application/json'))
            job = self.client.batches.create(model=self.image_gen_model_id, src=uploaded_file.name, config={'display_name': 'gui-image-gen-job'})
            self.logger.info(f"이미지 생성 배치 작업 생성 완료: {job.name}")

            completed_job = self._monitor_job(job.name)
            if completed_job.state.name == 'JOB_STATE_SUCCEEDED':
                result_file = completed_job.dest.file_name
                self.logger.info(f"결과 파일 다운로드 및 파싱 중: {result_file}")
                content = self.client.files.download(file=result_file).decode('utf-8')
                
                img_count = 0
                for line in content.splitlines():
                    if not line: continue
                    parsed = json.loads(line)
                    for part in parsed['response']['candidates'][0]['content']['parts']:
                        if part.get('text'): self.logger.info(f"생성된 텍스트: {part['text']}")
                        elif part.get('inlineData'):
                            img_count += 1
                            img_data = base64.b64decode(part['inlineData']['data'])
                            img_filename = f"generated_image_{int(time.time())}_{img_count}.png"
                            with open(img_filename, "wb") as f: f.write(img_data)
                            self.logger.info(f"이미지 저장 완료: {img_filename}")
                            image_callback(img_filename) # GUI에 이미지 표시 요청
        except Exception as e:
            self.logger.error(f"이미지 생성 작업 중 오류: {e}", exc_info=True)

    def list_recent_jobs(self):
        try:
            self.logger.info("--- 최근 배치 작업 목록 조회 및 결과 처리 시작 ---")
            batches = self.client.batches.list(config={'page_size': 10})
            
            found_jobs = False
            for b in batches.page:
                found_jobs = True
                self.logger.info(f"\n[작업 발견] 이름: {b.name} | 상태: {b.state.name}")

                # 작업이 성공적으로 완료된 경우에만 결과 처리 로직 실행
                if b.state.name == 'JOB_STATE_SUCCEEDED':
                    self.logger.info("-> [성공] 작업을 처리합니다.")
                    
                    # 파일 기반 작업 결과 처리
                    if b.dest and b.dest.file_name:
                        self.logger.info(f"  -> 파일 기반 결과입니다. (파일: {b.dest.file_name})")
                        try:
                            content_bytes = self.client.files.download(file=b.dest.file_name)
                            content = content_bytes.decode('utf-8')
                            self.logger.info("  -> 결과 내용:")
                            for line in content.splitlines():
                                if line:
                                    parsed_response = json.loads(line)
                                    # 보기 좋게 출력
                                    self.logger.info(f"    {json.dumps(parsed_response, indent=2)}")
                        except Exception as e:
                            self.logger.error(f"  -> 파일 결과 처리 중 오류 발생: {e}", exc_info=True)
                    
                    # 인라인 작업 결과 처리
                    elif b.dest and not b.dest.file_name:
                        self.logger.info("  -> 인라인 결과입니다. 상세 정보를 가져옵니다...")
                        try:
                            # list() 호출은 인라인 결과를 포함하지 않으므로 get()으로 상세 정보 조회
                            full_job = self.client.batches.get(name=b.name)
                            if full_job.dest and full_job.dest.inlined_responses:
                                self.logger.info("  -> 결과 내용:")
                                for i, resp in enumerate(full_job.dest.inlined_responses):
                                    self.logger.info(f"    --- 응답 {i+1} ---")
                                    if resp.response:
                                        try:
                                            self.logger.info(f"    {resp.response.text}")
                                        except (AttributeError, ValueError):
                                            self.logger.info(f"    {resp.response}")
                                    elif resp.error:
                                        self.logger.error(f"    오류: {resp.error}")
                            else:
                                self.logger.warning("  -> 상세 정보에 인라인 결과가 없습니다.")
                        except Exception as e:
                            self.logger.error(f"  -> 인라인 결과 처리 중 오류 발생: {e}", exc_info=True)
                    else:
                        self.logger.warning("  -> 결과를 처리할 수 없는 유형의 작업입니다.")
                else:
                    self.logger.info(f"-> 상태가 '{b.state.name}'이므로 결과를 처리하지 않습니다.")
            
            if not found_jobs:
                self.logger.info("조회할 최근 작업이 없습니다.")
            
            self.logger.info("\n--- 최근 배치 작업 목록 조회 및 결과 처리 종료 ---")

        except Exception as e:
            self.logger.error(f"작업 목록 조회 중 오류 발생: {e}", exc_info=True)


class BatchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gemini 배치 작업 GUI")
        self.geometry("900x700")

        self.log_queue = queue.Queue()
        self.logger = self.setup_logging()
        self.logic = BatchLogic(self.logger)

        self.create_widgets()
        self.after(100, self.process_log_queue)
        
        self.logger.info("GUI가 시작되었습니다. .env 파일에서 API 키를 로드합니다.")
        if not self.logic.initialize_client():
            self.set_status("오류: API 키를 초기화할 수 없습니다. .env 파일을 확인하세요.", "red")
            for child in self.control_frame.winfo_children():
                child.config(state=tk.DISABLED)
        else:
            self.set_status("준비", "green")

    def setup_logging(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.addHandler(QueueHandler(self.log_queue))
        # 파일 핸들러 추가 (선택 사항)
        file_handler = logging.FileHandler('gui_batch_mode.log', 'w')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        return logger

    def create_widgets(self):
        # 제어 프레임
        self.control_frame = ttk.LabelFrame(self, text="작업 제어")
        self.control_frame.pack(padx=10, pady=10, fill="x")

        self.btn_file = ttk.Button(self.control_frame, text="파일 기반 작업 실행", command=lambda: self.start_job(self.logic.run_file_based_job))
        self.btn_file.grid(row=0, column=0, padx=5, pady=5)

        self.btn_inline = ttk.Button(self.control_frame, text="인라인 작업 실행", command=lambda: self.start_job(self.logic.run_inline_job))
        self.btn_inline.grid(row=0, column=1, padx=5, pady=5)

        self.btn_multi_in = ttk.Button(self.control_frame, text="멀티모달 입력 작업", command=lambda: self.start_job(self.logic.run_multimodal_input_job))
        self.btn_multi_in.grid(row=0, column=2, padx=5, pady=5)

        self.btn_img_gen = ttk.Button(self.control_frame, text="이미지 생성 작업", command=lambda: self.start_job(self.logic.run_image_generation_job, self.display_image))
        self.btn_img_gen.grid(row=0, column=3, padx=5, pady=5)
        
        self.btn_list = ttk.Button(self.control_frame, text="최근 작업 목록 조회", command=lambda: self.start_job(self.logic.list_recent_jobs))
        self.btn_list.grid(row=0, column=4, padx=5, pady=5)

        # 로그 프레임
        log_frame = ttk.LabelFrame(self, text="실행 로그")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 상태 표시줄
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, text, color="black"):
        self.status_var.set(text)
        self.status_bar.config(foreground=color)

    def process_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, message + '\n')
            self.log_text.config(state='disabled')
            self.log_text.see(tk.END)
        self.after(100, self.process_log_queue)

    def start_job(self, job_function, callback=None):
        self.toggle_buttons(tk.DISABLED)
        self.set_status(f"{job_function.__name__} 실행 중...", "blue")
        
        args = (callback,) if callback else ()
        thread = threading.Thread(target=self.run_threaded_job, args=(job_function, args), daemon=True)
        thread.start()

    def run_threaded_job(self, job_function, args):
        job_function(*args)
        self.after(0, self.on_job_complete, job_function.__name__)

    def on_job_complete(self, job_name):
        self.set_status("준비", "green")
        self.toggle_buttons(tk.NORMAL)
        self.logger.info(f"{job_name} 작업 완료.")

    def toggle_buttons(self, state):
        for child in self.control_frame.winfo_children():
            child.config(state=state)

    def display_image(self, image_path):
        self.after(0, self._create_image_window, image_path)

    def _create_image_window(self, image_path):
        try:
            win = tk.Toplevel(self)
            win.title(f"생성된 이미지: {os.path.basename(image_path)}")
            
            img = Image.open(image_path)
            img.thumbnail((600, 600)) # 이미지 크기 조정
            photo = ImageTk.PhotoImage(img)
            
            label = ttk.Label(win, image=photo)
            label.image = photo # 참조 유지
            label.pack(padx=10, pady=10)
        except Exception as e:
            self.logger.error(f"이미지 표시 중 오류: {e}", exc_info=True)


if __name__ == "__main__":
    app = BatchGUI()
    app.mainloop()
