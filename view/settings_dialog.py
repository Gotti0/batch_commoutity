import json
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QDialogButtonBox, QLabel, QTextEdit, QDoubleSpinBox,
    QSpinBox
)
from PySide6.QtGui import QValidator, QIntValidator

# A custom QSpinBox to handle group separators during keyboard input
class CustomSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setGroupSeparatorShown(True)

    def validate(self, text: str, pos: int) -> QValidator.State:
        """Override to validate text with group separators."""
        # Remove separators before calling the base validation
        text_no_sep = text.replace(self.locale().groupSeparator(), '')
        return super().validate(text_no_sep, pos)

    def valueFromText(self, text: str) -> int:
        """Override to get value from text with group separators."""
        # Remove separators before calling the base method to get the value
        text_no_sep = text.replace(self.locale().groupSeparator(), '')
        return super().valueFromText(text_no_sep)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Form Layout for settings
        form_layout = QFormLayout()

        self.source_lang_edit = QLineEdit()
        self.source_lang_edit.setToolTip("번역할 원본 언어의 코드 (예: en, de, fr)")
        self.target_lang_edit = QLineEdit()
        self.target_lang_edit.setToolTip("번역 결과물의 언어 코드 (예: ko, ja, zh)")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setToolTip("Google AI Studio에서 발급받은 API 키를 입력하세요.")
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setToolTip("번역에 사용할 Gemini 모델의 이름 (예: gemini-1.5-pro)")
        self.system_instruction_edit = QTextEdit()
        self.system_instruction_edit.setToolTip("모델에 번역을 지시할 기본 명령어 (프롬프트)")
        
        self.chunk_size_edit = QLineEdit()
        self.chunk_size_edit.setToolTip("API 요청 시 한 번에 보낼 텍스트의 최대 글자 수 (100 ~ 100000)")
        self.chunk_size_edit.setValidator(QIntValidator(100, 100000, self))

        self.temperature_spinbox = QDoubleSpinBox()
        self.temperature_spinbox.setToolTip("모델 응답의 창의성 조절 (높을수록 다양, 낮을수록 결정적)")
        self.temperature_spinbox.setRange(0.0, 2.0)
        self.temperature_spinbox.setSingleStep(0.1)
        self.top_p_spinbox = QDoubleSpinBox()
        self.top_p_spinbox.setToolTip("모델이 고려할 단어 후보의 범위 조절 (핵심 어휘만 사용하려면 낮게 설정)")
        self.top_p_spinbox.setRange(0.0, 1.0)
        self.top_p_spinbox.setSingleStep(0.05)

        self.thinking_budget_edit = QLineEdit()
        self.thinking_budget_edit.setToolTip("모델의 생각 시간 예산 (0 ~ 1024)")
        self.thinking_budget_edit.setValidator(QIntValidator(0, 1024, self))

        self.prefill_edit = QTextEdit()
        self.prefill_edit.setToolTip("Prefill (JSON 형식)")

        form_layout.addRow(QLabel("소스 언어:"), self.source_lang_edit)
        form_layout.addRow(QLabel("타겟 언어:"), self.target_lang_edit)
        form_layout.addRow(QLabel("API 키:"), self.api_key_edit)
        form_layout.addRow(QLabel("모델 이름:"), self.model_name_edit)
        form_layout.addRow(QLabel("시스템 명령어:"), self.system_instruction_edit)
        form_layout.addRow(QLabel("Chunk 크기:"), self.chunk_size_edit)
        form_layout.addRow(QLabel("Temperature:"), self.temperature_spinbox)
        form_layout.addRow(QLabel("Top P:"), self.top_p_spinbox)
        form_layout.addRow(QLabel("Thinking Budget:"), self.thinking_budget_edit)
        form_layout.addRow(QLabel("Prefill (JSON):"), self.prefill_edit)

        layout.addLayout(form_layout)

        # OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_settings(self):
        """Returns the settings from the dialog fields."""
        return {
            "source_language": self.source_lang_edit.text(),
            "target_language": self.target_lang_edit.text(),
            "gemini_api_key": self.api_key_edit.text(),
            "model_name": self.model_name_edit.text(),
            "system_instruction": self.system_instruction_edit.toPlainText(),
            "chunk_size": int(self.chunk_size_edit.text() or 0),
            "temperature": self.temperature_spinbox.value(),
            "top_p": self.top_p_spinbox.value(),
            "thinking_budget": int(self.thinking_budget_edit.text() or 0),
            "prefill_cached_history": self.prefill_edit.toPlainText() # Keep as string here
        }

    def set_settings(self, config):
        """Populates the dialog fields with the given config."""
        self.source_lang_edit.setText(config.get("source_language", "en"))
        self.target_lang_edit.setText(config.get("target_language", "ko"))
        self.api_key_edit.setText(config.get("gemini_api_key", ""))
        self.model_name_edit.setText(config.get("model_name", "gemini-1.5-pro"))
        self.system_instruction_edit.setPlainText(config.get("system_instruction", ""))
        self.chunk_size_edit.setText(str(config.get("chunk_size", 5000)))
        self.temperature_spinbox.setValue(config.get("temperature", 1.0))
        self.top_p_spinbox.setValue(config.get("top_p", 0.95))
        self.thinking_budget_edit.setText(str(config.get("thinking_budget", 128)))
        
        prefill_data = config.get("prefill_cached_history", [])
        self.prefill_edit.setPlainText(json.dumps(prefill_data, indent=4, ensure_ascii=False))
