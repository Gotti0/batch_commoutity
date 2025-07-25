import json
import os
import logging

logger = logging.getLogger(__name__)

class JobTracker:
    def __init__(self, tracker_file='job_tracker.json'):
        self.tracker_file = tracker_file
        self.jobs = self._load()

    def _load(self):
        if not os.path.exists(self.tracker_file):
            return {}
        try:
            with open(self.tracker_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning(f"Could not read or parse job tracker file: {self.tracker_file}")
            return {}

    def _save(self):
        try:
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump(self.jobs, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save job tracker file: {e}", exc_info=True)

    def add_job(self, job_name, source_file_path):
        """Adds a new job and its source file to the tracker."""
        self.jobs[job_name] = {'source_file': source_file_path}
        self._save()
        logger.info(f"Job '{job_name}' tracked with source '{source_file_path}'.")

    def get_source_file(self, job_name):
        """Gets the source file path for a given job name."""
        return self.jobs.get(job_name, {}).get('source_file')

    def remove_job(self, job_name):
        """Removes a job from the tracker."""
        if job_name in self.jobs:
            del self.jobs[job_name]
            self._save()
            logger.info(f"Job '{job_name}' removed from tracker.")
