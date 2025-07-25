from pathlib import Path

class FileService:
    def read_text(self, file_path):
        """텍스트 파일을 읽어 내용을 반환합니다."""
        return Path(file_path).read_text(encoding='utf-8')

    def write_text(self, file_path, content):
        """내용을 텍스트 파일에 씁니다."""
        Path(file_path).write_text(content, encoding='utf-8')
