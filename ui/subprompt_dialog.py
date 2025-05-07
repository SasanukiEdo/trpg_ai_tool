# ui/subprompt_dialog.py の内容

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QLabel, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt # 必要であれば

# --- ★★★ config_manager からグローバル設定を読み込むために追加 ★★★ ---
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path: sys.path.insert(0, project_root)
from core.config_manager import load_global_config
# --------------------------------------------------------------------

# --- サブプロンプト編集/追加ダイアログ ---
class SubPromptEditDialog(QDialog):

    MODEL_PLACEHOLDER_TEXT = "（プロジェクト設定に従う）"

    def __init__(self, initial_data=None, parent=None, is_editing=False, current_category=None):
        super().__init__(parent)
        self.is_editing = is_editing # ★ is_editing をインスタンス変数として保持 (任意)
        self.current_category = current_category # ★ カテゴリ名も保持 (任意)

        # --- ★★★ グローバル設定から利用可能なモデルリストを取得 ★★★ ---
        global_config = load_global_config()
        self.available_models = global_config.get("available_models", ["gemini-1.5-pro-latest"]) # フォールバック
        # ---------------------------------------------------------

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

         # --- ★★★ モデル選択コンボボックスの修正 ★★★ ---
        self.model_combo = QComboBox()
        # 最初に「プロジェクト設定のモデルを使用」の選択肢を追加
        self.model_placeholder_text = "(プロジェクト設定のモデルを使用)"
        self.model_combo.addItem(self.model_placeholder_text)
        self.model_combo.addItems(self.available_models) # グローバル設定のリストを使用

        current_model_in_data = initial_data.get("model", "")
        if current_model_in_data and current_model_in_data in self.available_models:
            self.model_combo.setCurrentText(current_model_in_data)
        else: # データにモデルがないか、リストにない場合はプレースホルダーを選択
            self.model_combo.setCurrentText(self.model_placeholder_text)
        layout.addRow("使用モデル:", self.model_combo)
        # -------------------------------------------

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        self.setMinimumWidth(450)

    def get_data(self):
        name = self.name_input.text().strip()
        prompt = self.prompt_input.toPlainText().strip()
        selected_model_text = self.model_combo.currentText()

        # --- ★★★ モデルがプレースホルダーなら空文字列を保存 ★★★ ---
        model_to_save = ""
        if selected_model_text != self.model_placeholder_text:
            model_to_save = selected_model_text
        # -------------------------------------------------

        return {
            "name": name,
            "prompt": prompt,
            "model": model_to_save # 空白または選択されたモデル名
        }


    def accept(self):
        # 名前の重複チェック (編集時かつ名前が変更された場合、または新規追加時)
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前を入力してください。")
            return

        # MainWindow からサブプロンプトのリストを取得して重複チェックする方が望ましいが、
        # ここでは SubPromptEditDialog 単体で完結させるため、一旦省略。
        # 必要であれば、MainWindow のインスタンスを渡してチェック機能を実装する。

        super().accept()
