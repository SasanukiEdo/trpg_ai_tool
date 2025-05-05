# ui/settings_dialog.py の内容

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox
)
# デフォルト設定を読み込むために config_manager をインポート
# core パッケージの一つ上の階層からインポートする必要がある
import sys
import os
# プロジェクトルートを Python パスに追加 (より堅牢な方法)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from core.config_manager import DEFAULT_CONFIG


# --- 設定ダイアログ ---
class SettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.config = current_config.copy() # 編集用の一時コピー

        layout = QFormLayout(self)

        self.api_key_input = QLineEdit(self.config.get("api_key", ""))
        self.api_key_input.setEchoMode(QLineEdit.Password) # 見えないように
        layout.addRow("Gemini APIキー:", self.api_key_input)

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

        self.setMinimumWidth(400) # 最小幅

    def accept(self):
        # 保存ボタンが押されたら、入力内容をconfigに反映
        self.config["api_key"] = self.api_key_input.text()
        self.config["model"] = self.model_combo.currentText()
        self.config["main_system_prompt"] = self.system_prompt_input.toPlainText()
        super().accept() # ダイアログを閉じる

    def get_config(self):
        # 更新された設定を返す
        return self.config

