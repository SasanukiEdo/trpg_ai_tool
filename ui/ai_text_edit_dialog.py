# ui/ai_text_edit_dialog.py

"""AIの支援を受けてテキストを編集するためのインタラクティブなダイアログを提供します。

このダイアログは、ユーザーがAIへの指示を入力し、AIに提案を依頼し、
AIからの提案を確認・編集して最終的なテキストを決定する一連の操作を
一つのウィンドウ内で行えるように設計されています。

主なUI要素:
    - AIへの指示入力エリア (QTextEdit)
    - AIに提案を依頼するボタン (QPushButton)
    - AIの提案表示/編集エリア (QTextEdit)
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QPushButton,
    QApplication, QSizePolicy, QSplitter, QWidget # QWidget を追加
)
from PyQt5.QtCore import Qt

class AIAssistedEditDialog(QDialog):
    """AIによるテキスト編集支援機能を提供するダイアログクラス。

    ユーザーがAIへの指示を編集し、AIに提案を要求できます。
    AIの提案はダイアログ内に表示され、ユーザーはそれを編集して
    最終的なテキストとして採用できます。

    Attributes:
        instruction_edit (QTextEdit): AIへの指示を入力・編集するためのテキストエリア。
        request_ai_button (QPushButton): AIに提案を依頼するためのボタン。
                                         このボタンのクリックシグナルは、
                                         ダイアログの呼び出し元で接続・処理されます。
        suggestion_edit (QTextEdit): AIからの提案を表示し、ユーザーが編集できるテキストエリア。
        processing_label (QLabel): AIが処理中であることを示すラベル（任意）。
    """

    def __init__(self,
                 initial_instruction_text: str,
                 current_item_description: str, # AI提案時にコンテキストとして利用される可能性あり
                 parent: QWidget | None = None,
                 window_title: str = "AIによるテキスト編集支援"):
        """AIAssistedEditDialogのコンストラクタ。

        Args:
            initial_instruction_text (str): AIへの指示入力エリアに初期表示するテキスト。
                                            通常はプロンプトテンプレートなど。
            current_item_description (str): 現在編集対象となっているアイテムの説明文。
                                            AIへの指示を組み立てる際のコンテキストとして利用されることを想定。
                                            （現在は直接ダイアログ内で使われていないが、将来的な拡張のため保持）
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
            window_title (str, optional): ダイアログのウィンドウタイトル。
                                          デフォルトは "AIによるテキスト編集支援"。
        """
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setMinimumSize(700, 650) # ダイアログの最小サイズ

        # self.current_item_description = current_item_description # 現在は未使用だが将来用

        layout = QVBoxLayout(self)

        # --- 上下分割スプリッター ---
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # --- 上部: AIへの指示入力エリア ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.addWidget(QLabel("AIへの指示 (編集して「提案を依頼」ボタンを押してください):"))
        self.instruction_edit = QTextEdit()
        self.instruction_edit.setPlainText(initial_instruction_text)
        self.instruction_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout.addWidget(self.instruction_edit)
        splitter.addWidget(top_widget)

        # --- 中間: AI提案依頼ボタン ---
        self.request_ai_button = QPushButton("AIに提案を依頼する")
        # self.request_ai_button.clicked は呼び出し元 (例: DetailWindow) で接続される
        layout.insertWidget(1, self.request_ai_button) # スプリッターとOK/Cancelボタンの間に配置

        # --- 下部: AIの提案表示/編集エリア ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.addWidget(QLabel("AIの提案 (必要に応じて編集してください):"))
        self.suggestion_edit = QTextEdit()
        self.suggestion_edit.setPlaceholderText(
            "「AIに提案を依頼する」ボタンを押すと、ここにAIの提案が表示されます。"
        )
        self.suggestion_edit.setReadOnly(False) # ユーザーが編集可能
        self.suggestion_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_layout.addWidget(self.suggestion_edit)
        splitter.addWidget(bottom_widget)

        # スプリッターの初期サイズを設定 (おおよそ上下均等)
        # self.height() はまだ正しくない場合があるので、固定値や割合で設定した方が安定することも
        splitter.setSizes([300, 300]) # 例: 上部300px, 下部300px

        # OK / Cancel ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # AI処理中を示すラベル (任意)
        self.processing_label = QLabel("AIが処理中です...")
        self.processing_label.setAlignment(Qt.AlignCenter)
        self.processing_label.setVisible(False) # 初期状態は非表示
        layout.addWidget(self.processing_label)


    def get_instruction_text(self) -> str:
        """AIへの指示入力エリアの現在のテキストを取得します。

        Returns:
            str: AIへの指示テキスト。
        """
        return self.instruction_edit.toPlainText()

    def set_suggestion_text(self, text: str):
        """AIの提案表示/編集エリアにテキストを設定します。

        通常、AIからの応答を受信した後に呼び出されます。

        Args:
            text (str): AIの提案テキスト。
        """
        self.suggestion_edit.setPlainText(text)

    def get_final_text(self) -> str:
        """最終的にユーザーが採用するテキスト（AIの提案エリアの現在の内容）を取得します。

        ダイアログが `Accepted` で閉じられた後に呼び出されることを想定しています。

        Returns:
            str: ユーザーが編集・確認した最終的なテキスト。
        """
        return self.suggestion_edit.toPlainText()

    def show_processing_message(self, show: bool = True):
        """AI処理中メッセージの表示/非表示を切り替えます。

        処理中は「AIに提案を依頼」ボタンを無効化します。

        Args:
            show (bool, optional): Trueなら処理中メッセージを表示、
                                   Falseなら非表示にします。デフォルトは True。
        """
        self.processing_label.setVisible(show)
        self.request_ai_button.setEnabled(not show) # 処理中はボタンを無効化
        QApplication.processEvents() # UIの更新を即時反映させるため

# テスト用のコードは、このダイアログの利用方法が DetailWindow 側に依存するため、
# ここでは単純な表示テストのみに留めるか、コメントアウトします。
if __name__ == '__main__':
    """AIAssistedEditDialog の基本的な表示テスト。"""
    import sys
    app = QApplication(sys.argv)

    sample_instruction = (
        "現在の説明:\n"
        "勇敢な戦士、レベル5。\n\n"
        "ユーザーの指示:\n"
        "[ここに具体的な指示を記述してください]"
    )
    sample_description = "勇敢な戦士、レベル5。"

    # このダイアログは通常、DetailWindow などから呼び出され、
    # request_ai_button.clicked シグナルが接続されてAI処理が実行されます。
    # ここではダイアログの表示と基本的なUI要素の確認のみ行います。
    dialog = AIAssistedEditDialog(sample_instruction, sample_description)

    # テスト用にダミーのAI提案ボタン処理
    def _dummy_ai_request():
        dialog.show_processing_message(True)
        print("Dummy AI Request: Instruction Text:")
        print(dialog.get_instruction_text())
        # ダミーのAI応答を少し遅れて設定するシミュレーション
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (
            dialog.set_suggestion_text("これはAIからのダミー提案です。\n戦士はレベル6になりました。"),
            dialog.show_processing_message(False)
        ))
    dialog.request_ai_button.clicked.connect(_dummy_ai_request)


    if dialog.exec_() == QDialog.Accepted:
        print("\nDialog Accepted. Final Text:")
        print(dialog.get_final_text())
    else:
        print("\nDialog Cancelled.")

    sys.exit(app.exec_())

