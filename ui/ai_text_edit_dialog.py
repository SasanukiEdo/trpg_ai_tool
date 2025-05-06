# ui/ai_text_edit_dialog.py (置き換え後の内容)

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QPushButton,
    QApplication, QSizePolicy, QSplitter,
    QWidget # <<< QWidget をインポートリストに追加
)
from PyQt5.QtCore import Qt

class AIAssistedEditDialog(QDialog):
    def __init__(self, initial_instruction_text, current_item_description, parent=None, window_title="AIによるテキスト編集支援"):
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setMinimumSize(700, 650) # ダイアログサイズ調整

        self.current_item_description = current_item_description # AI提案時に利用

        layout = QVBoxLayout(self)

        # --- 上下分割スプリッター ---
        splitter = QSplitter(Qt.Vertical) # 上下に分割
        layout.addWidget(splitter)

        # --- 上部: AIへの指示入力エリア ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.addWidget(QLabel("AIへの指示 (編集して「提案を依頼」ボタンを押してください):"))
        self.instruction_edit = QTextEdit()
        self.instruction_edit.setPlainText(initial_instruction_text)
        self.instruction_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # 伸びるように
        top_layout.addWidget(self.instruction_edit)
        splitter.addWidget(top_widget)

        # --- 中間: AI提案依頼ボタン ---
        self.request_ai_button = QPushButton("AIに提案を依頼する")
        # self.request_ai_button.clicked.connect(...) # 接続は呼び出し元で行う
        layout.insertWidget(1, self.request_ai_button) # スプリッターとボタンの間に挿入

        # --- 下部: AIの提案表示/編集エリア ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.addWidget(QLabel("AIの提案 (必要に応じて編集してください):"))
        self.suggestion_edit = QTextEdit()
        self.suggestion_edit.setPlaceholderText("「AIに提案を依頼する」ボタンを押すと、ここにAIの提案が表示されます。")
        self.suggestion_edit.setReadOnly(False) # 初期は編集可能に
        self.suggestion_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # 伸びるように
        bottom_layout.addWidget(self.suggestion_edit)
        splitter.addWidget(bottom_widget)

        splitter.setSizes([self.height() // 2, self.height() // 2]) # 上下均等に分割 (おおよそ)

        # OK / Cancel ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # AI処理中を示すラベル（任意）
        self.processing_label = QLabel("AIが処理中です...")
        self.processing_label.setAlignment(Qt.AlignCenter)
        self.processing_label.setVisible(False) # 初期状態は非表示
        layout.addWidget(self.processing_label)


    def get_instruction_text(self):
        """AIへの指示テキストを返す"""
        return self.instruction_edit.toPlainText()

    def set_suggestion_text(self, text):
        """AIの提案テキストエリアに内容をセットする"""
        self.suggestion_edit.setPlainText(text)

    def get_final_text(self):
        """最終的に採用するテキスト (AIの提案エリアの内容) を返す"""
        return self.suggestion_edit.toPlainText()

    def show_processing_message(self, show=True):
        """AI処理中メッセージの表示/非表示を切り替え"""
        self.processing_label.setVisible(show)
        self.request_ai_button.setEnabled(not show) # 処理中はボタンを無効化
        QApplication.processEvents() # UI更新を即時反映


    @staticmethod
    def get_assisted_text(parent, initial_instruction, current_item_desc, title="AI支援編集"):
        """
        AI支援編集ダイアログを表示し、編集されたテキストまたはNoneを返す。
        このメソッド内でAI呼び出しのループは行わない。AI呼び出しは DetailWindow 側で行う。
        """
        dialog = AIAssistedEditDialog(initial_instruction, current_item_desc, parent, window_title=title)
        # request_ai_button のクリックシグナルは DetailWindow で接続して処理する
        # ここではダイアログの表示と結果取得のみに注力

        # このダイアログは、ユーザーが指示を編集し、AI提案を受け取り、
        # 最終的に提案を編集してOKを押す、という一連の操作を想定。
        # 「AIに提案を依頼」ボタンが押されたときの処理は、このダイアログの外側 (呼び出し元) で
        # dialog.get_instruction_text() を使って指示を取得し、AIに投げ、
        # dialog.set_suggestion_text() で結果をダイアログに表示する、という流れになる。

        # このスタティックメソッドは直接使わず、DetailWindow側でインスタンス化して使う方が良いかもしれない。
        # 今回は一旦残すが、DetailWindowでの実装を優先する。
        raise NotImplementedError("This static method is complex to use directly. Instantiate and manage from DetailWindow.")

# テスト用のコードは、このクラスの新しい使い方に合わせて書き直す必要があるため一旦コメントアウト
# if __name__ == '__main__':
#     app = QApplication([])
#     # ...
#     sys.exit(app.exec_())
