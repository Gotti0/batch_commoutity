import sys
import json
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox


from view.main_window import MainWindow
from view.settings_dialog import SettingsDialog
from viewmodel.main_viewmodel import MainViewModel
from model.config_manager import ConfigManager

from model.gemini_api_service import GeminiApiService
from model.file_service import FileService

import logging
from model.logger import setup_logger

def main():
    """Application entry point."""
    setup_logger()
    logging.info("==================================")
    logging.info("Application starting...")
    
    app = QApplication(sys.argv)

    # 1. Model 인스턴스 생성
    config_manager = ConfigManager('config.json')
    gemini_api_service = GeminiApiService(config_manager)
    file_service = FileService()

    # 2. ViewModel 인스턴스 생성 및 Model 주입
    view_model = MainViewModel(
        config_manager,
        gemini_api_service,
        file_service
    )

    # 3. View 인스턴스 생성
    main_window = MainWindow()

    # 4. View와 ViewModel 연결 (데이터 바인딩 및 커맨드 바인딩)
    
    # ViewModel -> View (데이터 바인딩)
    main_window.jobs_table_view.setModel(view_model.jobs_model)
    view_model.status_message_changed.connect(main_window.status_label.setText)
    
    def handle_loading_change(is_loading):
        main_window.setDisabled(is_loading)
        main_window.status_label.setText("처리 중..." if is_loading else view_model.status_message)
    view_model.is_loading_changed.connect(handle_loading_change)

    # View -> ViewModel (커맨드 바인딩)
    def open_file_dialog():
        path = main_window.get_selected_file_path()
        if path:
            main_window.source_file_path_edit.setText(path)
            view_model.select_source_file(path)
            
    main_window.browse_button.clicked.connect(open_file_dialog)
    main_window.add_job_button.clicked.connect(view_model.add_job)

    def open_settings_dialog():
        dialog = SettingsDialog(main_window)
        dialog.set_settings(config_manager.config)
        
        if dialog.exec():
            new_settings = dialog.get_settings()
            
            # --- Prefill JSON 파싱 ---
            try:
                prefill_text = new_settings.get("prefill_cached_history", "[]")
                new_settings["prefill_cached_history"] = json.loads(prefill_text)
            except json.JSONDecodeError:
                QMessageBox.critical(main_window, "오류", "Prefill 필드의 JSON 형식이 올바르지 않습니다.")
                return # 오류가 발생하면 저장하지 않고 함수 종료

            # The API key in the dialog is only updated if the user enters a new one.
            # If it's empty, we keep the old one.
            if not new_settings.get("gemini_api_key"):
                new_settings["gemini_api_key"] = config_manager.get("gemini_api_key")
            
            config_manager.save_config(new_settings)
            # Re-initialize the API client with the new key if it changed
            gemini_api_service.__init__(config_manager)
            view_model.status_message = "설정이 저장되었습니다."

    main_window.settings_button.clicked.connect(open_settings_dialog)
    main_window.refresh_button.clicked.connect(view_model.load_jobs)
    
    def show_context_menu(position):
        row = main_window.jobs_table_view.indexAt(position).row()
        if row < 0:
            return
            
        menu = QMenu()
        download_action = menu.addAction("결과 다운로드")
        delete_action = menu.addAction("작업 삭제")
        
        action = menu.exec(main_window.jobs_table_view.viewport().mapToGlobal(position))
        
        if action == download_action:
            job = view_model._batch_jobs[row]
            save_path = main_window.get_save_file_path(job.display_name)
            if save_path:
                view_model.download_result(row, save_path)
        elif action == delete_action:
            view_model.delete_job(row)

    main_window.jobs_table_view.customContextMenuRequested.connect(show_context_menu)

    # 5. 애플리케이션 시작
    main_window.show()
    
    # 초기 작업 목록 로드
    view_model.load_jobs()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    # Ensure UTF-8 encoding for all I/O
    if sys.stdout and sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr and sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
        
    main()
