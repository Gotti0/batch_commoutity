소설 번역기 MVVM 아키텍처 (최종 완성본)
1. 개요
이 문서는 Gemini 배치 API를 활용하는 소설 번역기 GUI 애플리케이션의 최종 아키텍처를 기술합니다. 본 아키텍처는 MVVM(Model-View-ViewModel) 패턴을 기반으로, 직관적인 사용자 경험, 높은 유지보수성, 그리고 향후 기능 확장에 유연하게 대응할 수 있는 구조를 목표로 설계되었습니다.

모든 기능은 단일 메인 윈도우에 통합되어 사용자 워크플로우를 간소화하며, 백그라운드에서 실행되는 자동 새로고침 기능은 실시간에 가까운 작업 상태 모니터링을 제공합니다. 특히, ConfigManager를 통해 모든 사용자 설정을 중앙에서 관리하여 유연성과 커스터마이징을 극대화합니다.

2. 아키텍처 다이어그램
ConfigManager가 애플리케이션의 모든 설정값을 관리하고, 각 서비스는 명확히 정의된 역할을 수행합니다.

graph TD
    subgraph "View (화면)"
        A[MainWindow] -- 사용자 액션 (파일 선택, 추가, 삭제 등) --> B_VM;
        B_VM -- 데이터 바인딩 (작업 목록, 상태 등) --> A;
    end

    subgraph "ViewModel (뷰모델)"
        B_VM[MainViewModel] -- 데이터/명령 요청 --> M;
        M -- 데이터/상태 제공 --> B_VM;
        T[Timer] -- "주기적 호출" --> B_VM_LoadCmd[LoadJobsCommand];
    end

    subgraph "Model (핵심 로직 및 데이터)"
        M -- 사용 --> S_Config[ConfigManager];
        S_Gemini -- 설정 주입 --> S_Config;
        M -- 사용 --> S_Gemini[GeminiApiService];
        M -- 사용 --> S_File[FileService];
        M -- 사용 --> S_Result[ResultProcessingService];
        M -- 포함 --> DM_Job[TranslationJob];
    end

    subgraph "External Services (외부 서비스)"
        S_Gemini -- HTTP 요청 --> E_API[Gemini Batch API];
        S_File -- 파일 입출력 --> E_FS[로컬 파일 시스템];
    end

3. 핵심 원칙: MVVM (Model-View-ViewModel)
View: 사용자 인터페이스(UI)의 구조와 모양만을 정의합니다. 모든 사용자 입력은 Command를 통해 ViewModel으로 전달됩니다.

ViewModel: View를 위한 상태와 로직을 관리합니다. Model로부터 데이터를 받아와 View가 표시하기 좋은 형태로 가공하고, View의 요청에 따라 Model의 비즈니스 로직을 실행합니다.

Model: 애플리케이션의 핵심 데이터와 비즈니스 로직(API 통신, 파일 처리, 데이터 구조 등)을 포함하며, UI와 완전히 독립적입니다.

4. 컴포넌트별 상세 설명
4.1. Model
애플리케이션의 두뇌 역할을 하며, 실제 모든 작업이 일어나는 곳입니다.

Services (서비스 계층)

ConfigManager.py: config.json 파일에서 모든 사용자 정의 값을 읽고, 쓰고, 관리합니다.

코드 스니펫 예시:

# ConfigManager.py
import json
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path='config.json'):
        self.path = Path(config_path)
        self.config = {}
        self.load()

    def load(self):
        """설정 파일에서 설정을 로드합니다."""
        if self.path.exists():
            with open(self.path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            # 기본 설정 값으로 초기화
            self.config = self._get_default_config()
            self.save()

    def save(self):
        """현재 설정을 파일에 저장합니다."""
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        """설정 값을 가져옵니다."""
        return self.config.get(key, default)

    def set(self, key, value):
        """설정 값을 변경하고 저장합니다."""
        self.config[key] = value
        self.save()

    def _get_default_config(self):
        return {
            "api_key": "",
            "model_name": "gemini-1.5-pro",
            "system_instruction": "Translate the following text to Korean.",
            "prefill_cached_history": [],
            "temperature": 1.0,
            "top_p": 0.95,
            "thinking_budget": 128,
            "chat_prompts": {},
            "chunk_size": 5000  # 5000자 단위로 분할
        }

GeminiApiService.py: ConfigManager로부터 설정을 주입받아 API와 통신합니다.

코드 스니펫 예시:

# GeminiApiService.py
import json
import os
from google import genai
from google.genai import types

class GeminiApiService:
    def __init__(self, config_manager):
        self.config = config_manager
        self.client = genai.Client(api_key=self.config.get('api_key'))

    def create_batch_job(self, source_file_path):
        """소스 파일로부터 배치 번역 작업을 생성하고 실행합니다."""
        model_id = self.config.get('model_name')
        requests_file = self._prepare_requests(source_file_path, model_id)

        uploaded_file = self.client.files.upload(
            file=requests_file,
            config=types.UploadFileConfig(mime_type='application/json')
        )

        batch_job = self.client.batches.create(
            model=f"models/{model_id}",
            src=uploaded_file.name,
            config={'display_name': f'translation-{os.path.basename(source_file_path)}'}
        )
        os.remove(requests_file) # 임시 파일 삭제
        return batch_job

    def _prepare_requests(self, source_file, model_id):
        """ConfigManager의 설정을 사용하여 요청 파일을 생성합니다."""
        requests_file = "temp_requests.jsonl"

        system_instruction = {"parts": [{"text": self.config.get('system_instruction')}]}
        prefill = self.config.get('prefill_cached_history')
        generation_config = {
            'temperature': self.config.get('temperature'),
            'top_p': self.config.get('top_p'),
        }
        chunk_size = self.config.get('chunk_size')

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
                    "generation_config": generation_config
                }
                f_out.write(json.dumps({"key": f"chunk_{i+1}", "request": request}, ensure_ascii=False) + '\n')

        return requests_file

FileService.py: 로컬 파일 시스템 작업을 처리합니다.

코드 스니펫 예시:

# FileService.py
from pathlib import Path

class FileService:
    def read_text(self, file_path):
        """텍스트 파일을 읽어 내용을 반환합니다."""
        return Path(file_path).read_text(encoding='utf-8')

    def write_text(self, file_path, content):
        """내용을 텍스트 파일에 씁니다."""
        Path(file_path).write_text(content, encoding='utf-8')

ResultProcessingService.py: 다운로드된 API 결과를 가공합니다. (이전 버전과 동일)

Data Models (데이터 모델)

TranslationJob.py: 하나의 번역 작업을 나타내는 데이터 클래스입니다.

코드 스니펫 예시:

# TranslationJob.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class JobStatus(Enum):
    PENDING = "대기 중"
    RUNNING = "실행 중"
    SUCCEEDED = "성공"
    FAILED = "실패"
    CANCELLED = "취소됨"
    UNKNOWN = "알 수 없음"

@dataclass
class TranslationJob:
    job_name: str
    display_name: str
    status: JobStatus = JobStatus.UNKNOWN
    creation_time: datetime = field(default_factory=datetime.now)
    update_time: datetime = field(default_factory=datetime.now)
    source_file_path: str = ""
    output_file_path: str = ""
    error_message: str = ""

4.2. View & ViewModel
MainWindow (View): UI 요소들의 집합입니다. 각 요소는 MainViewModel의 속성 및 커맨드에 바인딩됩니다.

'파일 찾아보기' 버튼: SelectSourceFileCommand에 바인딩됩니다.

'새 작업 추가' 버튼: AddJobCommand에 바인딩됩니다.

작업 목록 그리드: MainViewModel의 BatchJobs 속성에 바인딩됩니다. 각 행의 '삭제' 버튼은 DeleteJobCommand에, '다운로드' 버튼은 DownloadResultCommand에 바인딩됩니다.

MainViewModel.py: MainWindow의 모든 로직을 처리하는 중앙 제어 타워입니다.

코드 스니펫 예시 (개념적):

# MainViewModel.py (개념적 코드)
# 실제 구현은 PyQt, Tkinter 등의 프레임워크에 따라 달라짐

class MainViewModel:
    def __init__(self, model):
        self.model = model # ConfigManager, GeminiApiService 등이 포함된 모델 객체

        # --- Properties (View와 바인딩될 속성) ---
        self.batch_jobs = [] # List[TranslationJob]
        self.new_source_file_path = ""
        self.is_loading = False
        self.status_message = "준비 완료"

        # --- Commands (View에서 호출될 메서드) ---
        self.add_job_command = self.add_job
        self.delete_job_command = self.delete_job
        # ... 기타 커맨드

        # --- 자동 새로고침 타이머 설정 ---
        self.setup_timer(interval_seconds=30, callback=self.load_jobs)

    def add_job(self):
        # 1. is_loading = True, status_message 변경
        # 2. self.model.gemini_api.create_batch_job(self.new_source_file_path) 호출
        # 3. 즉시 load_jobs() 호출하여 목록 갱신
        # 4. is_loading = False, status_message 변경
        pass

    def load_jobs(self):
        # 1. is_loading = True
        # 2. self.model.gemini_api.list_batch_jobs() 호출
        # 3. 반환된 결과로 self.batch_jobs 목록 업데이트 (UI 자동 갱신)
        # 4. is_loading = False
        pass

    # ... 기타 커맨드 구현 ...

5. 데이터 흐름 시나리오
앱 시작: ConfigManager가 config.json 파일에서 모든 설정을 로드합니다.

서비스 초기화: MainViewModel이 ConfigManager의 인스턴스를 GeminiApiService 등에 주입하여 초기화합니다.

작업 생성: 사용자가 '새 작업 추가'를 클릭하면, GeminiApiService는 ConfigManager로부터 모델명, 시스템 프롬프트, 온도 등 모든 필요한 설정을 가져와 API 요청을 구성합니다.

자동 새로고침: 백그라운드 타이머가 주기적으로 load_jobs를 호출하여 작업 목록을 최신 상태로 유지하고, UI에 자동으로 반영합니다.

6. 기대 효과
중앙화된 설정 관리: 모든 설정이 ConfigManager를 통해 관리되므로, 설정 추가/변경이 용이하고 코드 전체의 일관성이 유지됩니다.

높은 유연성 및 커스터마이징: 사용자는 config.json 파일을 직접 수정하거나 UI를 통해 프롬프트, 모델, API 파라미터 등을 자유롭게 변경하여 번역 품질을 제어할 수 있습니다.

유지보수성 향상: API 스펙 변경이나 새로운 설정 항목 추가 시 ConfigManager와 관련 서비스만 수정하면 되므로 유지보수가 간편해집니다.