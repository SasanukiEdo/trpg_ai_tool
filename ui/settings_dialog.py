# ui/settings_dialog.py の内容

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QPushButton, QLabel, QMessageBox, QHBoxLayout
)
from PyQt5.QtCore import Qt

# デフォルト設定を読み込むために config_manager をインポート
# core パッケージの一つ上の階層からインポートする必要がある
import sys
import os

# プロジェクトルートを Python パスに追加 (より堅牢な方法)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.config_manager import DEFAULT_GLOBAL_CONFIG, DEFAULT_PROJECT_SETTINGS # <<< DEFAULT_PROJECT_SETTINGS も追加
from core.api_key_manager import save_api_key, get_api_key, delete_api_key


# --- 設定ダイアログ ---
class SettingsDialog(QDialog):
    def __init__(self, current_combined_config, parent=None): # 引数名を変更して分かりやすく
        super().__init__(parent)
        self.setWindowTitle("設定")
        # ★★★ current_combined_config をそのままコピーして使う ★★★
        self.config_to_edit = current_combined_config.copy()
        layout = QFormLayout(self)

        # APIキー管理UI (変更なし、ただし update_api_key_status_label は初回呼び出しが必要)
        self.api_key_status_label = QLabel()
        self.update_api_key_status_label()
        api_key_layout = QHBoxLayout()
        self.api_key_input_for_save = QLineEdit()
        self.api_key_input_for_save.setPlaceholderText("新しいAPIキーを入力して保存")
        self.api_key_input_for_save.setEchoMode(QLineEdit.Password)
        self.save_api_key_button = QPushButton("APIキーをOSに保存/更新")
        self.save_api_key_button.clicked.connect(self._save_api_key_to_os)
        self.delete_api_key_button = QPushButton("保存されたAPIキーを削除")
        self.delete_api_key_button.clicked.connect(self._delete_api_key_from_os)
        api_key_layout.addWidget(self.api_key_input_for_save)
        api_key_layout.addWidget(self.save_api_key_button)
        api_key_layout.addWidget(self.delete_api_key_button)
        layout.addRow("APIキー管理:", api_key_layout)
        layout.addRow("現在のAPIキー状態:", self.api_key_status_label)

        # --- ★★★ プロジェクト表示名 (読み取り専用または編集可能にするか検討) ★★★ ---
        self.project_display_name_label = QLineEdit(self.config_to_edit.get("project_display_name", DEFAULT_PROJECT_SETTINGS.get("project_display_name", "")))
        # self.project_display_name_label.setReadOnly(True) # 表示のみなら
        layout.addRow("プロジェクト表示名:", self.project_display_name_label)
        # -----------------------------------------------------------------

        # デフォルトモデル (プロジェクト固有モデルとして扱う)
        available_models = ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-pro"] # これは共通でOK
        self.model_combo = QComboBox()
        self.model_combo.addItems(available_models)
        # ★★★ config_to_edit から model を取得、なければ DEFAULT_PROJECT_SETTINGS を参照 ★★★
        current_model = self.config_to_edit.get("model", DEFAULT_PROJECT_SETTINGS.get("model", ""))
        if current_model in available_models: self.model_combo.setCurrentText(current_model)
        elif available_models: self.model_combo.setCurrentIndex(0)
        layout.addRow("プロジェクトモデル:", self.model_combo) # ラベルも変更

        # メインシステムプロンプト (プロジェクト固有)
        # ★★★ config_to_edit から main_system_prompt を取得、なければ DEFAULT_PROJECT_SETTINGS を参照 ★★★
        self.system_prompt_input = QTextEdit(self.config_to_edit.get("main_system_prompt", DEFAULT_PROJECT_SETTINGS.get("main_system_prompt", "")))
        self.system_prompt_input.setMinimumHeight(150)
        layout.addRow("メインシステムプロンプト:", self.system_prompt_input)

        # --- ★★★ グローバル設定: デフォルトモデル (新規プロジェクト作成時のため) ★★★ ---
        self.global_default_model_combo = QComboBox()
        self.global_default_model_combo.addItems(available_models)
        current_global_default_model = self.config_to_edit.get("default_model", DEFAULT_GLOBAL_CONFIG.get("default_model", ""))
        if current_global_default_model in available_models: self.global_default_model_combo.setCurrentText(current_global_default_model)
        elif available_models: self.global_default_model_combo.setCurrentIndex(0)
        layout.addRow("新規プロジェクト用デフォルトモデル:", self.global_default_model_combo)
        # ----------------------------------------------------------------------

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        self.setMinimumWidth(600) # 幅を少し広げる

    # ... (update_api_key_status_label, _save_api_key_to_os, _delete_api_key_from_os は変更なし)

    def accept(self):
        # ★★★ 設定項目を self.config_to_edit に反映 ★★★
        self.config_to_edit["project_display_name"] = self.project_display_name_label.text() # 表示名を更新
        self.config_to_edit["model"] = self.model_combo.currentText() # プロジェクトモデル
        self.config_to_edit["main_system_prompt"] = self.system_prompt_input.toPlainText()
        self.config_to_edit["default_model"] = self.global_default_model_combo.currentText() # グローバルデフォルトモデル

        # active_project は MainWindow 側で管理されるので、ここでは変更しない
        # self.config_to_edit["active_project"] = ...
        super().accept()

    def get_config(self):
        return self.config_to_edit # 編集された設定全体を返す


    def update_api_key_status_label(self):
        """APIキーがOSに保存されているか確認し、ラベルを更新"""
        if get_api_key(): # キーが取得できれば保存されている
            self.api_key_status_label.setText("<font color='green'>OSに保存済み</font>")
        else:
            self.api_key_status_label.setText("<font color='red'>未保存 (または取得失敗)</font>")

    def _save_api_key_to_os(self):
        """入力されたAPIキーをOSの資格情報ストアに保存する"""
        key_to_save = self.api_key_input_for_save.text()
        if not key_to_save:
            # 空の場合は削除を促すか、何もしないか、確認ダイアログを出す
            reply = QMessageBox.question(self, "APIキー削除確認",
                                       "APIキーが入力されていません。保存されているAPIキーを削除しますか？",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, msg = delete_api_key()
                QMessageBox.information(self, "APIキー削除", msg)
            else:
                return # 何もしない
        else:
            success, msg = save_api_key(key_to_save)
            if success:
                QMessageBox.information(self, "APIキー保存", msg)
                self.api_key_input_for_save.clear() # 保存後は入力欄をクリア
            else:
                QMessageBox.warning(self, "APIキー保存エラー", msg)
        self.update_api_key_status_label() # 状態表示を更新

    def _delete_api_key_from_os(self):
        """OSに保存されたAPIキーを削除する"""
        reply = QMessageBox.question(self, "APIキー削除確認",
                                   "OSに保存されているAPIキーを削除しますか？この操作は元に戻せません。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, msg = delete_api_key()
            QMessageBox.information(self, "APIキー削除", msg)
            self.update_api_key_status_label() # 状態表示を更新
        

    def accept(self):
        # 保存ボタンが押されたら、入力内容をconfigに反映
        self.config["model"] = self.model_combo.currentText()
        self.config["main_system_prompt"] = self.system_prompt_input.toPlainText()
        super().accept() # ダイアログを閉じる

    def get_config(self):
        # 更新された設定を返す
        return self.config

