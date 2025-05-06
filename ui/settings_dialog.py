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
from core.config_manager import DEFAULT_CONFIG
from core.api_key_manager import save_api_key, get_api_key, delete_api_key # <<< 追加


# --- 設定ダイアログ ---
class SettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.config = current_config.copy() # 編集用の一時コピー

        layout = QFormLayout(self)

        # --- APIキー関連UIの変更 ---
        self.api_key_status_label = QLabel() # APIキーの状態表示用
        self.update_api_key_status_label() # 初期状態をセット

        api_key_layout = QHBoxLayout()
        self.api_key_input_for_save = QLineEdit() # 保存時のみ使用する一時的な入力欄
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
        # --------------------------

        # 利用可能なモデルをリストアップ（将来的にはAPIから取得したい）
        available_models = ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-pro"] # 必要に応じて追加
        self.model_combo = QComboBox()
        self.model_combo.addItems(available_models)


        # デフォルトモデルも DEFAULT_CONFIG から取得するように修正
        current_model = self.config.get("model", DEFAULT_CONFIG.get("model", ""))
        if current_model in available_models:
            self.model_combo.setCurrentText(current_model)
        elif available_models: # 現在の設定値がリストにない場合、先頭を選択
             self.model_combo.setCurrentIndex(0)
        layout.addRow("デフォルトモデル:", self.model_combo)

        self.system_prompt_input = QTextEdit(self.config.get("main_system_prompt", DEFAULT_CONFIG.get("main_system_prompt", "")))
        self.system_prompt_input.setMinimumHeight(150) # 高さを確保
        layout.addRow("メインシステムプロンプト:", self.system_prompt_input)

        # OK / Cancel ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setMinimumWidth(500) # 最小幅


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

