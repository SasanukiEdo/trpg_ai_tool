# ui/ai_text_edit_dialog.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt

class AITextEditDialog(QDialog):
    def __init__(self, original_text, ai_suggestion_text, parent=None, window_title="AIによる編集提案"):
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setMinimumSize(500, 400) # ダイアログの最小サイズ

        layout = QVBoxLayout(self)

        # 編集のヒント (任意)
        # layout.addWidget(QLabel("AIからの提案です。必要に応じて編集してください。"))

        self.text_edit = QTextEdit()
        if ai_suggestion_text:
            self.text_edit.setPlainText(ai_suggestion_text)
        else:
            # AIの提案がない場合は元のテキストを表示（更新指示用）
            self.text_edit.setPlainText(original_text if original_text else "")
            if not ai_suggestion_text and original_text: # AI提案がなく元テキストがある場合のみプレースホルダー設定
                 self.text_edit.setPlaceholderText("AIの提案がありませんでした。こちらで編集してください。")


        layout.addWidget(self.text_edit)

        # OK / Cancel ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_text(self):
        """編集されたテキストを返す"""
        return self.text_edit.toPlainText()

    @staticmethod
    def get_ai_edited_text(parent, original_text, ai_suggestion_text, title="AIによる編集提案"):
        """
        ダイアログを表示し、編集されたテキストまたはNoneを返すスタティックメソッド。
        """
        dialog = AITextEditDialog(original_text, ai_suggestion_text, parent, window_title=title)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_text()
        return None

if __name__ == '__main__':
    # テスト用
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    original = "これは元のテキストです。\nいくつかの特徴があります。"
    suggestion = "AIが提案した新しいテキストです。\n変更が加えられています。\nどうでしょうか？"
    # edited_text = AITextEditDialog.get_ai_edited_text(None, original, suggestion)
    # if edited_text is not None:
    #     print("編集後のテキスト:\n", edited_text)
    # else:
    #     print("キャンセルされました。")

    # AI提案がない場合のテスト
    edited_text_no_suggestion = AITextEditDialog.get_ai_edited_text(None, original, None, title="AI提案なしテスト")
    if edited_text_no_suggestion is not None:
        print("AI提案なし、編集後のテキスト:\n", edited_text_no_suggestion)
    else:
        print("AI提案なし、キャンセルされました。")

    sys.exit(app.exec_())
