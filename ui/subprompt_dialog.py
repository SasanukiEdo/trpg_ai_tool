# ui/subprompt_dialog.py の内容

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QLabel, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt # 必要であれば

# --- サブプロンプト編集/追加ダイアログ ---
class SubPromptEditDialog(QDialog):
    def __init__(self, initial_data=None, parent=None, is_editing=False, current_category=None):
        super().__init__(parent)
        self.is_editing = is_editing # ★ is_editing をインスタンス変数として保持 (任意)
        self.current_category = current_category # ★ カテゴリ名も保持 (任意)

        if initial_data is None:
            initial_data = {"name": "", "prompt": "", "model": ""} # デフォルトモデルは呼び出し元で設定済みの想定

        if self.is_editing:
            self.setWindowTitle(f"サブプロンプト編集 ({current_category} - {initial_data.get('name', '')})")
        else:
            self.setWindowTitle(f"サブプロンプト追加 ({current_category})")
    # -----------------------------------------------

        layout = QFormLayout(self)

        self.name_input = QLineEdit(initial_data.get("name", ""))
        if self.is_editing:
             # 編集時は名前フィールドを読み取り専用にするか、
             # 名前変更を許可する場合は MainWindow 側で古いキーの削除など適切な処理が必要
             # ここでは一旦編集可能にしておくが、 MainWindow.add_or_edit_subprompt で対応済み
             pass
        layout.addRow("名前:", self.name_input)

        self.prompt_input = QTextEdit(initial_data.get("prompt", ""))
        self.prompt_input.setMinimumHeight(150)
        layout.addRow("プロンプト:", self.prompt_input)

        # モデル選択 (ここでも MainWindow のプロジェクト設定やグローバル設定のデフォルトモデルを参照できると良い)
        available_models = ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-pro"] # これは共通
        self.model_combo = QComboBox()
        self.model_combo.addItems(available_models)
        current_model_in_data = initial_data.get("model", "")
        if current_model_in_data in available_models:
            self.model_combo.setCurrentText(current_model_in_data)
        elif available_models: # データにモデルがない場合や不正な場合はリストの先頭
            self.model_combo.setCurrentIndex(0)
        layout.addRow("使用モデル:", self.model_combo)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        self.setMinimumWidth(450)

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "prompt": self.prompt_input.toPlainText().strip(),
            "model": self.model_combo.currentText()
        }


    def accept(self):
        """OKボタンが押されたときの処理"""
        if self.get_data() is not None:
            super().accept()
        else:
            pass # エラーメッセージは get_data 内で表示
