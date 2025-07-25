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