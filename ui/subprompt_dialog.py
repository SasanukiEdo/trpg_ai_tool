# ui/subprompt_dialog.py

"""サブプロンプトの新規作成および編集を行うためのダイアログを提供します。

このダイアログ (`SubPromptEditDialog`) は、ユーザーがサブプロンプトの名前、
プロンプト本文、および使用するAIモデル（任意）を指定できるようにします。
利用可能なAIモデルのリストは、グローバル設定から取得されます。
"""

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QMessageBox, QWidget
)
from PyQt5.QtCore import Qt

import sys
import os
# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.config_manager import load_global_config # 利用可能モデルリスト取得用

class SubPromptEditDialog(QDialog):
    """サブプロンプトの作成または編集を行うダイアログクラス。

    ユーザーはサブプロンプトの名前、プロンプト本文、および使用するAIモデルを
    このダイアログを通じて設定します。モデル選択では、プロジェクト設定のモデルを
    使用するオプションも提供されます。

    Attributes:
        name_input (QLineEdit): サブプロンプトの名前を入力するフィールド。
        prompt_input (QTextEdit): サブプロンプトの本文を入力するテキストエリア。
        model_combo (QComboBox): 使用するAIモデルを選択するコンボボックス。
    """
    
    def __init__(self,
                 initial_data: dict | None = None,
                 parent: QWidget | None = None, # QWidgetをインポートしていないので型ヒント修正
                 is_editing: bool = False,
                 current_category: str | None = None):
        """SubPromptEditDialogのコンストラクタ。

        Args:
            initial_data (dict | None, optional):
                編集時にダイアログに初期表示するサブプロンプトのデータ。
                キーとして 'name', 'prompt', 'model' を含む辞書を想定。
                新規作成時は None または空の辞書。デフォルトは None。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
            is_editing (bool, optional):
                ダイアログが編集モードであるかを示すフラグ。
                Trueなら編集モード、Falseなら新規作成モード。デフォルトは False。
            current_category (str | None, optional):
                現在操作対象となっているサブプロンプトのカテゴリ名。
                ウィンドウタイトルに表示するために使用。デフォルトは None。
            reference_tags_input (QLineEdit): 参照先タグを入力するフィールド。
        """
        super().__init__(parent)
        self.is_editing = is_editing
        """bool: ダイアログが編集モードか新規作成モードかを示すフラグ。"""
        # self.current_category = current_category # 現在はウィンドウタイトル以外では未使用

        # グローバル設定から利用可能なモデルリストを取得
        global_config = load_global_config()
        self.available_models = global_config.get(
            "available_models",
            ["gemini-1.5-pro-latest"] # フォールバック用の最小限のリスト
        )
        """list[str]: 利用可能なAIモデル名のリスト。"""

        if initial_data is None:
            initial_data = {"name": "", "prompt": "", "model": "", "reference_tags": []} # 新規作成時のデフォルト
        self.initial_name = initial_data.get("name", "") if is_editing else ""
        """str: 編集モードの場合の、編集開始前のサブプロンプト名。名前変更時の重複チェックなどに使用可能。"""


        _display_category = f" ({current_category})" if current_category else ""
        if self.is_editing:
            self.setWindowTitle(f"サブプロンプト編集{_display_category} - {self.initial_name}")
        else:
            self.setWindowTitle(f"サブプロンプト追加{_display_category}")

        layout = QFormLayout(self)

        self.name_input = QLineEdit(initial_data.get("name", ""))
        layout.addRow("名前:", self.name_input)

        self.prompt_input = QTextEdit(initial_data.get("prompt", "").replace("\n", "<br>"))
        self.prompt_input.setMinimumHeight(150)
        layout.addRow("プロンプト:", self.prompt_input)

        self.model_combo = QComboBox()
        self.model_placeholder_text = "(プロジェクト設定のモデルを使用)"
        """str: モデルコンボボックスで「プロジェクト設定モデル使用」を示すテキスト。"""
        self.model_combo.addItem(self.model_placeholder_text)
        self.model_combo.addItems(self.available_models)

        current_model_in_data = initial_data.get("model", "")
        if current_model_in_data and current_model_in_data in self.available_models:
            self.model_combo.setCurrentText(current_model_in_data)
        else: # データにモデルがない(空文字列含む)か、リストにない場合はプレースホルダーを選択
            self.model_combo.setCurrentText(self.model_placeholder_text)
        layout.addRow("使用モデル:", self.model_combo)

        # --- ★★★ 参照先タグ入力フィールドを追加 ★★★ ---
        self.reference_tags_input = QLineEdit(", ".join(initial_data.get("reference_tags", [])))
        self.reference_tags_input.setPlaceholderText("例: ギルド, 魔法アイテム")
        layout.addRow("参照先タグ (カンマ区切り):", self.reference_tags_input)
        # --- ★★★ --------------------------------- ★★★ ---

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        self.setMinimumWidth(450)

    def get_data(self) -> dict[str, str | list[str]]:
        """ダイアログで編集されたサブプロンプトのデータを取得します。

        このメソッドは、ダイアログが `Accepted` で閉じられた後に呼び出されることを想定しています。
        モデル選択で「プロジェクト設定のモデルを使用」が選ばれている場合、
        'model' の値は空文字列になります。

        Returns:
            dict[str, str | list[str]]: キー 'name', 'prompt', 'model', 'reference_tags' を持つ辞書。
                                       'reference_tags' は文字列のリスト。
        """
        name = self.name_input.text().strip()
        prompt = self.prompt_input.toPlainText().strip()
        selected_model_text = self.model_combo.currentText()

        model_to_save = "" # デフォルトは空文字列（プロジェクト設定モデル使用）
        if selected_model_text != self.model_placeholder_text:
            model_to_save = selected_model_text
        
        # --- ★★★ 参照先タグデータを取得 ★★★ ---
        reference_tags_str = self.reference_tags_input.text().strip()
        reference_tags_list = [tag.strip() for tag in reference_tags_str.split(',') if tag.strip()]
        # --- ★★★ -------------------------- ★★★ ---

        return {
            "name": name,
            "prompt": prompt,
            "model": model_to_save,
            "reference_tags": reference_tags_list # ★ 追加
        }

    def accept(self):
        """OKボタンが押されたときの処理。入力値の基本的な検証を行います。

        名前が空でないかを確認します。
        より高度な検証（例: 名前の重複チェック）は、
        このダイアログの呼び出し元で行うことを推奨します。
        """
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前を入力してください。")
            # self.name_input.setFocus() # フォーカスを名前入力に戻す (任意)
            return # acceptを中止

        # ここで MainWindow が持つ現在のカテゴリ内のサブプロンプト名リストと照合し、
        # 重複チェックを行うことも可能だが、ダイアログの責務としては必須ではない。
        # (is_editing が True で self.initial_name と name が異なる場合、または
        #  is_editing が False の場合にチェック)

        super().accept() # QDialog.Accepted を発行

if __name__ == '__main__':
    """SubPromptEditDialog の基本的な表示テスト。"""
    # QApplicationのインスタンスが外部で作成済みであるという前提
    # from PyQt5.QtWidgets import QApplication # ここでインポートすると二重になる可能性
    # app = QApplication(sys.argv) # MainWindowなどから実行時は不要

    # テスト用のダミーデータ
    test_initial_data_new = {"model": "gemini-1.5-pro-latest"} # 新規作成時、特定のモデルを初期選択させたい場合
    test_initial_data_edit = {
        "name": "既存プロンプト",
        "prompt": "これは編集対象のプロンプトです。",
        "model": "gemini-1.5-flash-latest"
    }

    print("--- SubPromptEditDialog テスト ---")

    # 新規作成モードのテスト
    print("\n1. 新規作成モード:")
    dialog_new = SubPromptEditDialog(
        initial_data=test_initial_data_new,
        current_category="テストカテゴリ1"
    )
    if dialog_new.exec_() == QDialog.Accepted:
        print("  新規作成ダイアログ: OK")
        print(f"  取得データ: {dialog_new.get_data()}")
    else:
        print("  新規作成ダイアログ: Cancel")

    # 編集モードのテスト
    print("\n2. 編集モード:")
    dialog_edit = SubPromptEditDialog(
        initial_data=test_initial_data_edit,
        is_editing=True,
        current_category="テストカテゴリ2"
    )
    if dialog_edit.exec_() == QDialog.Accepted:
        print("  編集ダイアログ: OK")
        print(f"  取得データ: {dialog_edit.get_data()}")
    else:
        print("  編集ダイアログ: Cancel")

    # モデルが空（プレースホルダ選択）の場合のテスト
    print("\n3. モデル空選択テスト:")
    dialog_model_empty = SubPromptEditDialog(
        initial_data={"name": "モデル空", "prompt":"テスト", "model":""},
        current_category="テストカテゴリ3"
    )
    if dialog_model_empty.exec_() == QDialog.Accepted:
        print("  モデル空ダイアログ: OK")
        print(f"  取得データ: {dialog_model_empty.get_data()}") # modelが "" になるはず
    else:
        print("  モデル空ダイアログ: Cancel")

    print("\n--- テスト完了 (QApplicationインスタンスがなければここで終了) ---")
    # sys.exit(app.exec_()) # MainWindowなどから実行時は不要

