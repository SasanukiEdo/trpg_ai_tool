# ui/subprompt_dialog.py の内容

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QLabel, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt # 必要であれば

# --- サブプロンプト編集/追加ダイアログ ---
class SubPromptEditDialog(QDialog):
    def __init__(self, categories, current_category=None, subprompt_data=None, parent=None):
        # ... (クラスの中身はそのまま貼り付け) ...
        # (変更点なし)
        super().__init__(parent)
        self.is_edit_mode = subprompt_data is not None
        self.original_name = subprompt_data['name'] if self.is_edit_mode else None
        self.original_category = current_category if self.is_edit_mode else None

        self.setWindowTitle("サブプロンプトを編集" if self.is_edit_mode else "サブプロンプトを追加")

        layout = QFormLayout(self)

        # カテゴリ選択 (既存 + 新規入力)
        self.category_combo = QComboBox()
        self.category_combo.addItems(sorted(categories)) # 既存カテゴリを追加
        self.category_combo.addItem("< 新規カテゴリ >") # 新規入力用
        self.category_combo.setEditable(False) # 通常は選択のみ
        self.new_category_input = QLineEdit() # 新規カテゴリ入力用
        self.new_category_input.setPlaceholderText("新しいカテゴリ名を入力")
        self.new_category_input.setVisible(False) # 初期状態は非表示
        self.category_combo.currentIndexChanged.connect(self.toggle_new_category_input)

        category_layout = QHBoxLayout()
        category_layout.addWidget(self.category_combo)
        category_layout.addWidget(self.new_category_input)
        layout.addRow("カテゴリ:", category_layout)

        initial_category = current_category
        if self.is_edit_mode and self.original_category:
            initial_category = self.original_category
        if initial_category and initial_category in categories:
            self.category_combo.setCurrentText(initial_category)
        elif categories: # デフォルトや編集対象カテゴリがない場合、最初のカテゴリを選択
            self.category_combo.setCurrentIndex(0)


        # サブプロンプト名
        self.name_input = QLineEdit(subprompt_data['name'] if self.is_edit_mode else "")
        layout.addRow("名前:", self.name_input)

        # サブプロンプト内容
        self.content_input = QTextEdit(subprompt_data['content'] if self.is_edit_mode else "")
        self.content_input.setMinimumHeight(150)
        layout.addRow("内容:", self.content_input)

        # --- オプション設定 ---
        options_label = QLabel("--- オプション (空欄の場合はデフォルト設定を使用) ---")
        layout.addRow(options_label)

        # モデル (ComboBox + 空欄許可)
        available_models = ["", "gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-pro"] # 必要に応じて追加
        self.model_combo = QComboBox()
        self.model_combo.addItems(available_models)
        if self.is_edit_mode and subprompt_data.get('model'):
            # モデル名がリストにない場合も考慮（リストになければ空欄を選択）
            model_to_set = subprompt_data.get('model')
            if model_to_set in available_models:
                 self.model_combo.setCurrentText(model_to_set)
            else:
                 self.model_combo.setCurrentIndex(0) # 空欄を選択
        layout.addRow("優先モデル:", self.model_combo)

        # APIキー (Password + 空欄許可)
        self.api_key_input = QLineEdit(subprompt_data.get('api_key', '') if self.is_edit_mode else "")
        self.api_key_input.setPlaceholderText("このサブプロンプト専用のAPIキー (任意)")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        layout.addRow("優先APIキー:", self.api_key_input)

        # OK / Cancel ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setMinimumWidth(450) # ダイアログの最小幅を設定

    def toggle_new_category_input(self, index):
        """カテゴリコンボボックスの選択に応じて新規カテゴリ入力欄の表示/非表示を切り替え"""
        is_new_category = self.category_combo.currentText() == "< 新規カテゴリ >"
        self.new_category_input.setVisible(is_new_category)
        if not is_new_category:
            self.new_category_input.clear() # 非表示になる際に内容をクリア

    def get_data(self):
        """ダイアログの入力内容を辞書として返す"""
        category_text = self.category_combo.currentText()
        if category_text == "< 新規カテゴリ >":
            category = self.new_category_input.text().strip()
        else:
            category = category_text

        name = self.name_input.text().strip()
        content = self.content_input.toPlainText().strip()
        model = self.model_combo.currentText() if self.model_combo.currentText() else None # 空文字はNoneに
        api_key = self.api_key_input.text() if self.api_key_input.text() else None # 空文字はNoneに

        if not category:
            QMessageBox.warning(self, "入力エラー", "カテゴリが選択または入力されていません。")
            return None
        if not name:
            QMessageBox.warning(self, "入力エラー", "サブプロンプトの名前が入力されていません。")
            return None
        if not content:
            QMessageBox.warning(self, "入力エラー", "サブプロンプトの内容が入力されていません。")
            return None

        return {
            "category": category,
            "name": name,
            "data": {
                "content": content,
                "model": model,
                "api_key": api_key
            },
            "original_name": self.original_name, # 編集モードの場合の元の名前
            "original_category": self.original_category # 編集モードの場合の元のカテゴリ
        }

    def accept(self):
        """OKボタンが押されたときの処理"""
        if self.get_data() is not None:
            super().accept()
        else:
            pass # エラーメッセージは get_data 内で表示
