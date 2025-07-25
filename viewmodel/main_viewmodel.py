import logging
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QAbstractTableModel, Qt
from PySide6.QtGui import QColor
import os

from model.translation_job import TranslationJob, JobStatus
from datetime import datetime

logger = logging.getLogger(__name__)

class JobTableModel(QAbstractTableModel):
    def __init__(self, parent=None, jobs=[]):
        super().__init__(parent)
        self._jobs = jobs
        self._headers = ["작업 이름", "표시 이름", "상태", "생성 시간", "업데이트 시간", "소스 파일", "출력 파일", "오류"]

    def rowCount(self, parent):
        return len(self._jobs)

    def columnCount(self, parent):
        return len(self._headers)

    def data(self, index, role):
        if not index.isValid():
            return None
        
        job = self._jobs[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return job.job_name
            if col == 1: return job.display_name
            if col == 2: return job.status.value
            if col == 3: return job.creation_time.strftime("%Y-%m-%d %H:%M:%S")
            if col == 4: return job.update_time.strftime("%Y-%m-%d %H:%M:%S")
            if col == 5: return os.path.basename(job.source_file_path)
            if col == 6: return job.output_file_path
            if col == 7: return job.error_message
        
        if role == Qt.BackgroundRole:
            if job.status == JobStatus.FAILED:
                return QColor("red")
            if job.status == JobStatus.SUCCEEDED:
                return QColor("lightgreen")

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None
    
    def update_jobs(self, jobs):
        self.beginResetModel()
        self._jobs = jobs
        self.endResetModel()


class MainViewModel(QObject):
    # --- Signals ---
    status_message_changed = Signal(str)
    is_loading_changed = Signal(bool)
    
    def __init__(self, config_manager, gemini_api_service, file_service):
        super().__init__()
        
        # --- Model Services ---
        self.config_manager = config_manager
        self.gemini_api = gemini_api_service
        self.file_service = file_service
        
        # --- Properties ---
        self._batch_jobs = []
        self._new_source_file_path = ""
        self._is_loading = False
        self._status_message = "준비 완료"
        
        self.jobs_model = JobTableModel(jobs=self._batch_jobs)

        # --- Timer for auto-refresh ---
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_jobs)
        self.refresh_timer.start(30000) # 30초마다

    # --- Property Getters/Setters ---
    @property
    def is_loading(self):
        return self._is_loading

    @is_loading.setter
    def is_loading(self, value):
        self._is_loading = value
        self.is_loading_changed.emit(value)

    @property
    def status_message(self):
        return self._status_message

    @status_message.setter
    def status_message(self, value):
        self._status_message = value
        self.status_message_changed.emit(value)

    # --- Commands (Slots) ---
    @Slot()
    def select_source_file(self, file_path):
        self._new_source_file_path = file_path
        message = f"Selected file: {os.path.basename(file_path)}"
        self.status_message = message
        logger.info(message)

    @Slot()
    def add_job(self):
        if not self._new_source_file_path:
            self.status_message = "오류: 먼저 번역할 파일을 선택하세요."
            logger.warning("Add job failed: No source file selected.")
            return
        
        self.is_loading = True
        self.status_message = f"'{os.path.basename(self._new_source_file_path)}' 작업 추가 중..."
        logger.info(f"Attempting to add job for file: {self._new_source_file_path}")
        
        try:
            job = self.gemini_api.create_batch_job(self._new_source_file_path)
            self.status_message = f"작업 생성 성공: {job.name}"
            logger.info(f"Successfully created job: {job.name}")
            
            # Convert the new job to our data model
            new_translation_job = TranslationJob(
                job_name=job.name,
                display_name=job.display_name,
                status=self._convert_status(job.state.name),
                creation_time=job.create_time,
                update_time=job.update_time,
            )
            
            # Add the new job to the top of the list and update the UI immediately
            self._batch_jobs.insert(0, new_translation_job)
            self.jobs_model.update_jobs(self._batch_jobs)
            
        except Exception as e:
            self.status_message = f"오류: 작업 추가 실패 - {e}"
            logger.error(f"Failed to create job for file '{self._new_source_file_path}': {e}", exc_info=True)
        finally:
            self.is_loading = False

    @Slot()
    def load_jobs(self):
        self.is_loading = True
        self.status_message = "작업 목록을 새로고침하는 중..."
        logger.info("Refreshing job list...")
        try:
            jobs_from_api = self.gemini_api.list_batch_jobs()
            
            # The result from the SDK is now a direct list.
            jobs_list = jobs_from_api
            logger.info(f"API returned {len(jobs_list)} jobs. Type: {type(jobs_from_api)}")
            if len(jobs_list) > 0:
                # Log details for each job at DEBUG level
                logger.debug("--- Fetched Batch Jobs ---")
                for job in jobs_list:
                    logger.debug(f"  - Name: {job.name}, Display: {job.display_name}, State: {job.state.name}")
                logger.debug("--------------------------")
            # --- End Debugging ---

            self._batch_jobs = [
                TranslationJob(
                    job_name=j.name,
                    display_name=j.display_name,
                    status=self._convert_status(j.state.name),
                    creation_time=j.create_time,
                    update_time=j.update_time,
                ) for j in jobs_list # Use the converted list from the page
            ]
            self.jobs_model.update_jobs(self._batch_jobs)
            self.status_message = f"작업 목록 새로고침 완료. 총 {len(self._batch_jobs)}개 작업."
            logger.info(f"Job list UI updated. Found {len(self._batch_jobs)} jobs.")
        except Exception as e:
            self.status_message = f"오류: 작업 목록 로드 실패 - {e}"
            logger.error(f"Failed to load job list: {e}", exc_info=True)
        finally:
            self.is_loading = False

    @Slot(int)
    def delete_job(self, row_index):
        if 0 <= row_index < len(self._batch_jobs):
            job_to_delete = self._batch_jobs[row_index]
            self.is_loading = True
            self.status_message = f"'{job_to_delete.display_name}' 작업 삭제 중..."
            logger.info(f"Attempting to delete job: {job_to_delete.job_name}")
            try:
                self.gemini_api.delete_batch_job(job_to_delete.job_name)
                self.status_message = "작업 삭제 성공."
                logger.info(f"Successfully deleted job: {job_to_delete.job_name}")
                self.load_jobs()
            except Exception as e:
                self.status_message = f"오류: 작업 삭제 실패 - {e}"
                logger.error(f"Failed to delete job '{job_to_delete.job_name}': {e}", exc_info=True)
            finally:
                self.is_loading = False

    @Slot(int)
    def download_result(self, row_index, save_path):
        if 0 <= row_index < len(self._batch_jobs):
            job_to_download = self._batch_jobs[row_index]
            
            # Get the full job object from the API to ensure we have the latest data
            try:
                full_job_obj = self.gemini_api.client.batches.get(name=job_to_download.job_name)
                normalized_state = full_job_obj.state.name.replace("JOB_STATE_", "")
            except Exception as e:
                self.status_message = f"오류: 작업 정보를 가져올 수 없습니다 - {e}"
                logger.error(f"Failed to get job details for '{job_to_download.job_name}': {e}", exc_info=True)
                return

            if normalized_state != "SUCCEEDED":
                self.status_message = "오류: '성공' 상태인 작업만 결과를 다운로드할 수 있습니다."
                logger.warning(f"Download result for job '{job_to_download.job_name}' failed: Job status is '{normalized_state}', not 'SUCCEEDED'.")
                return

            self.is_loading = True
            self.status_message = f"'{job_to_download.display_name}' 결과 다운로드 및 처리 중..."
            logger.info(f"Attempting to download and process result for job: {job_to_download.job_name}")
            try:
                self.gemini_api.download_and_process_results(full_job_obj, save_path)
                self.status_message = f"결과 저장 완료: {save_path}"
                logger.info(f"Successfully downloaded and saved result for job '{job_to_download.job_name}' to '{save_path}'.")
            except Exception as e:
                self.status_message = f"오류: 결과 처리 실패 - {e}"
                logger.error(f"Failed to download and process result for job '{job_to_download.job_name}': {e}", exc_info=True)
            finally:
                self.is_loading = False

    def _convert_status(self, api_status_str):
        """Converts API status string to JobStatus enum."""
        # Handle the new, unsupported 'BATCH_STATE_RUNNING' status explicitly.
        if api_status_str == 'BATCH_STATE_RUNNING':
            return JobStatus.RUNNING
            
        # The API might return "JOB_STATE_SUCCEEDED" or just "SUCCEEDED"
        normalized_status = api_status_str.replace("JOB_STATE_", "")
        try:
            return JobStatus[normalized_status]
        except KeyError:
            logger.warning(f"Unknown job status received from API: '{api_status_str}'")
            return JobStatus.UNKNOWN
