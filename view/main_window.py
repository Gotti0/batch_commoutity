import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTableView, QHeaderView, QStatusBar, QLabel,
    QFileDialog
)
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("소설 번역기")
        self.setGeometry(100, 100, 800, 600)

        # --- 메인 위젯 및 레이아웃 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 파일 선택 섹션 ---
        top_layout = QHBoxLayout()
        self.settings_button = QPushButton("설정")
        self.settings_button.setToolTip("애플리케이션 설정을 변경합니다 (API 키, 모델 등).")
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setToolTip("서버로부터 작업 목록을 즉시 새로고침합니다.")
        top_layout.addWidget(self.settings_button)
        top_layout.addWidget(self.refresh_button)
        top_layout.addStretch(1)

        file_selection_layout = QHBoxLayout()
        self.source_file_path_edit = QLineEdit()
        self.source_file_path_edit.setPlaceholderText("번역할 소설 (.txt) 파일을 선택하세요...")
        self.source_file_path_edit.setToolTip("번역할 텍스트 파일의 경로입니다.")
        self.browse_button = QPushButton("찾아보기")
        self.browse_button.setToolTip("로컬 파일 시스템에서 번역할 파일을 선택합니다.")
        file_selection_layout.addWidget(self.source_file_path_edit)
        file_selection_layout.addWidget(self.browse_button)
        
        main_layout.addLayout(top_layout)
        main_layout.addLayout(file_selection_layout)

        # --- 작업 추가 버튼 ---
        self.add_job_button = QPushButton("새 번역 작업 추가")
        self.add_job_button.setToolTip("선택된 파일을 사용하여 새 번역 작업을 생성하고 목록에 추가합니다.")
        main_layout.addWidget(self.add_job_button)

        # --- 작업 목록 테이블 ---
        self.jobs_table_view = QTableView()
        self.jobs_table_view.setToolTip("생성된 번역 작업의 목록입니다. 마우스 오른쪽 버튼을 클릭하여 추가 작업을 수행할 수 있습니다.")
        self.jobs_table_view.setAlternatingRowColors(True)
        self.jobs_table_view.setSelectionBehavior(QTableView.SelectRows)
        self.jobs_table_view.horizontalHeader().setStretchLastSection(True)
        self.jobs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        main_layout.addWidget(self.jobs_table_view)

        self.jobs_table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.jobs_table_view.customContextMenuRequested.connect(self.show_jobs_table_context_menu)

        # --- 상태 표시줄 ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("준비 완료")
        self.status_bar.addWidget(self.status_label)

    def show_jobs_table_context_menu(self, position):
        pass # This will be connected in main.py

    def get_selected_job_row(self):
        indexes = self.jobs_table_view.selectionModel().selectedRows()
        if indexes:
            return indexes[0].row()
        return -1

    def get_save_file_path(self, job_display_name):
        """파일 저장 대화상자를 열어 사용자가 저장 위치를 선택하도록 합니다."""
        default_name = f"{job_display_name}_translated.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "번역 결과 저장",
            default_name,
            "Text Files (*.txt);;All Files (*)"
        )
        return file_path

    def get_selected_file_path(self):
        """파일 대화상자를 열어 사용자가 파일을 선택하도록 합니다."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "번역할 파일 선택",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        return file_path

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
