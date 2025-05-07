# ui/settings_dialog.py

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QPushButton, QLabel, QMessageBox, QHBoxLayout # QHBoxLayout を追加
)
from PyQt5.QtCore import Qt

# --- coreモジュールインポート ---
from core.config_manager import DEFAULT_GLOBAL_CONFIG, DEFAULT_PROJECT_SETTINGS
from core.api_key_manager import save_api_key, get_api_key, delete_api_key

class SettingsDialog(QDialog):
    # --- ★★★ __init__ で global_config と project_settings を別々に受け取る ★★★ ---
    def __init__(self, current_global_config, current_project_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        # 受け取った設定を編集用にコピー
        self.global_config_edit = current_global_config.copy()
        self.project_settings_edit = current_project_settings.copy() if current_project_settings else DEFAULT_PROJECT_SETTINGS.copy()

        layout = QFormLayout(self)

        # --- ★★★ グローバル設定から利用可能なモデルリストを取得 ★★★ ---
        available_models_from_config = self.global_config_edit.get("available_models", ["gemini-1.5-pro-latest"])
        # ---------------------------------------------------------

        # --- APIキー管理 (変更なし) ---
        self.api_key_status_label = QLabel()
        self.update_api_key_status_label()
        api_key_row_layout = QHBoxLayout() # ボタンなどを横に並べる
        self.api_key_input_for_save = QLineEdit()
        self.api_key_input_for_save.setPlaceholderText("新しいAPIキーを入力して保存")
        self.api_key_input_for_save.setEchoMode(QLineEdit.Password)
        self.save_api_key_button = QPushButton("APIキーをOSに保存/更新")
        self.save_api_key_button.clicked.connect(self._save_api_key_to_os)
        self.delete_api_key_button = QPushButton("保存されたAPIキーを削除")
        self.delete_api_key_button.clicked.connect(self._delete_api_key_from_os)
        api_key_row_layout.addWidget(self.api_key_input_for_save)
        api_key_row_layout.addWidget(self.save_api_key_button)
        api_key_row_layout.addWidget(self.delete_api_key_button)
        layout.addRow("APIキー管理:", api_key_row_layout)
        layout.addRow("現在のAPIキー状態:", self.api_key_status_label)

        # --- プロジェクト固有設定 ---
        layout.addRow(QLabel("--- 現在のプロジェクト設定 ---"))
        # プロジェクト表示名 (編集可能に)
        self.project_display_name_input = QLineEdit(
            self.project_settings_edit.get("project_display_name", DEFAULT_PROJECT_SETTINGS.get("project_display_name"))
        )
        layout.addRow("プロジェクト表示名:", self.project_display_name_input)

        # プロジェクト使用モデル
        self.project_model_combo = QComboBox()
        self.project_model_combo.addItems(available_models_from_config)
        # ----------------------------------------
        current_project_model = self.project_settings_edit.get("model", DEFAULT_PROJECT_SETTINGS.get("model"))
        if current_project_model in available_models_from_config: self.project_model_combo.setCurrentText(current_project_model)
        elif available_models_from_config: self.project_model_combo.setCurrentIndex(0)
        layout.addRow("プロジェクト使用モデル:", self.project_model_combo)

        # メインシステムプロンプト (プロジェクト固有)
        self.project_system_prompt_input = QTextEdit(
            self.project_settings_edit.get("main_system_prompt", DEFAULT_PROJECT_SETTINGS.get("main_system_prompt"))
        )
        self.project_system_prompt_input.setMinimumHeight(150)
        layout.addRow("メインシステムプロンプト:", self.project_system_prompt_input)

        # グローバル設定
        layout.addRow(QLabel("--- アプリケーション全体設定 ---"))
        # 新規プロジェクト作成時のデフォルトモデル (グローバル設定)
        self.global_default_model_combo = QComboBox()
        # --- ★★★ 利用可能なモデルリストを使用 ★★★ ---
        self.global_default_model_combo.addItems(available_models_from_config)
        # ----------------------------------------
        current_global_default_model = self.global_config_edit.get("default_model", DEFAULT_GLOBAL_CONFIG.get("default_model"))
        if current_global_default_model in available_models_from_config: self.global_default_model_combo.setCurrentText(current_global_default_model)
        elif available_models_from_config: self.global_default_model_combo.setCurrentIndex(0)
        layout.addRow("新規プロジェクト用デフォルトモデル:", self.global_default_model_combo)

        # ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        self.setMinimumWidth(600)

    def update_api_key_status_label(self):
        if get_api_key(): self.api_key_status_label.setText("<font color='green'>OSに保存済み</font>")
        else: self.api_key_status_label.setText("<font color='red'>未保存 (または取得失敗)</font>")

    def _save_api_key_to_os(self):
        key_to_save = self.api_key_input_for_save.text()
        if not key_to_save:
            reply = QMessageBox.question(self, "APIキー削除確認",
                                       "APIキーが入力されていません。保存されているAPIキーを削除しますか？",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes: success, msg = delete_api_key()
            else: return
        else:
            success, msg = save_api_key(key_to_save)
            if success: self.api_key_input_for_save.clear()
            else: QMessageBox.warning(self, "APIキー保存エラー", msg)
        QMessageBox.information(self, "APIキー操作完了", msg)
        self.update_api_key_status_label()

    def _delete_api_key_from_os(self):
        reply = QMessageBox.question(self, "APIキー削除確認",
                                   "OSに保存されているAPIキーを削除しますか？この操作は元に戻せません。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, msg = delete_api_key()
            QMessageBox.information(self, "APIキー削除", msg)
            self.update_api_key_status_label()

    def accept(self):
        # 編集された値を各設定オブジェクトに反映
        # グローバル設定
        self.global_config_edit["default_model"] = self.global_default_model_combo.currentText()
        # active_project は MainWindow で管理するのでここでは変更しない

        # プロジェクト設定
        self.project_settings_edit["project_display_name"] = self.project_display_name_input.text()
        self.project_settings_edit["model"] = self.project_model_combo.currentText()
        self.project_settings_edit["main_system_prompt"] = self.project_system_prompt_input.toPlainText()
        super().accept()

    def get_updated_configs(self):
        """編集されたグローバル設定とプロジェクト設定をタプルで返す"""
        return self.global_config_edit, self.project_settings_edit
