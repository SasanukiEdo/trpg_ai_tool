# ui/settings_dialog.py

"""アプリケーションの設定を編集するためのダイアログを提供します。

このダイアログ (`SettingsDialog`) は、以下の設定項目を管理します:
    - APIキーの管理 (OS資格情報ストアへの保存・削除)
    - プロジェクト固有設定:
        - プロジェクト表示名
        - プロジェクト使用モデル
        - メインシステムプロンプト
    - アプリケーション全体設定 (グローバル設定):
        - 新規プロジェクト作成時のデフォルトAIモデル

利用可能なAIモデルのリストはグローバル設定から取得されます。
"""

from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QTextEdit, QComboBox,
    QPushButton, QLabel, QMessageBox, QHBoxLayout, QFrame, QWidget # QFrame を追加 (区切り線用)
)
from PyQt5.QtCore import Qt

# --- coreモジュールインポート ---
import sys
import os
# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.config_manager import DEFAULT_GLOBAL_CONFIG, DEFAULT_PROJECT_SETTINGS
from core.api_key_manager import save_api_key, get_api_key, delete_api_key

class SettingsDialog(QDialog):
    """アプリケーションの設定を編集するためのダイアログクラス。

    APIキー、プロジェクト固有設定、グローバル設定を編集し、
    対応する設定ファイルに保存する機能を提供します。

    Attributes:
        api_key_status_label (QLabel): OSに保存されたAPIキーの状態を表示するラベル。
        project_display_name_input (QLineEdit): プロジェクトの表示名を入力するフィールド。
        project_model_combo (QComboBox): プロジェクトで使用するAIモデルを選択するコンボボックス。
        project_system_prompt_input (QTextEdit): プロジェクトのメインシステムプロンプトを入力するエリア。
        global_default_model_combo (QComboBox): 新規プロジェクト作成時のデフォルトモデルを選択するコンボボックス。
    """

    def __init__(self,
                 current_global_config: dict,
                 current_project_settings: dict | None,
                 parent: QWidget | None = None): # QWidgetはインポート済み
        """SettingsDialogのコンストラクタ。

        Args:
            current_global_config (dict): 現在のグローバル設定の辞書。
            current_project_settings (dict | None):
                現在のプロジェクト固有設定の辞書。プロジェクトが未選択などの場合はNoneの可能性あり。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
        """
        super().__init__(parent)
        self.setWindowTitle("設定")
        # 受け取った設定を編集用にコピー
        self.global_config_edit = current_global_config.copy()
        self.project_settings_edit = (current_project_settings.copy()
                                      if current_project_settings
                                      else DEFAULT_PROJECT_SETTINGS.copy())
        """dict: 編集中のプロジェクト設定。コンストラクタで初期化される。"""

        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow) # フィールドを広げる

        # --- グローバル設定から利用可能なモデルリストを取得 ---
        self.available_models = self.global_config_edit.get(
            "available_models",
            DEFAULT_GLOBAL_CONFIG.get("available_models", ["gemini-1.5-pro-latest"])
        )
        """list[str]: `config.json` から読み込まれた、利用可能なAIモデル名のリスト。"""

        # --- APIキー管理セクション ---
        api_key_group_label = QLabel("<b>APIキー管理</b>")
        layout.addRow(api_key_group_label)

        self.api_key_status_label = QLabel()
        self.update_api_key_status_label() # 初期状態を設定
        layout.addRow("現在のAPIキー状態:", self.api_key_status_label)

        self.api_key_input_for_save = QLineEdit()
        self.api_key_input_for_save.setPlaceholderText("新しいGemini APIキーを入力")
        self.api_key_input_for_save.setEchoMode(QLineEdit.Password)
        layout.addRow("新規/更新APIキー:", self.api_key_input_for_save)

        api_buttons_layout = QHBoxLayout()
        self.save_api_key_button = QPushButton("APIキーをOSに保存/更新")
        self.save_api_key_button.clicked.connect(self._save_api_key_to_os)
        api_buttons_layout.addWidget(self.save_api_key_button)
        self.delete_api_key_button = QPushButton("保存されたAPIキーを削除")
        self.delete_api_key_button.clicked.connect(self._delete_api_key_from_os)
        api_buttons_layout.addWidget(self.delete_api_key_button)
        api_buttons_layout.addStretch() # ボタンを左寄せ
        layout.addRow(api_buttons_layout) # QFormLayoutは2列なので、空ラベルを追加するか、直接addWidgetする
        # layout.addRow("", api_buttons_layout) # 左側に空ラベルを置く場合

        # --- プロジェクト固有設定セクション ---
        layout.addRow(self._create_separator_line()) # 区切り線
        project_settings_label = QLabel("<b>現在のプロジェクト設定</b>")
        layout.addRow(project_settings_label)

        self.project_display_name_input = QLineEdit(
            self.project_settings_edit.get("project_display_name",
                                           DEFAULT_PROJECT_SETTINGS.get("project_display_name"))
        )
        layout.addRow("プロジェクト表示名:", self.project_display_name_input)

        self.project_model_combo = QComboBox()
        self.project_model_combo.addItems(self.available_models)
        current_project_model = self.project_settings_edit.get("model",
                                                               DEFAULT_PROJECT_SETTINGS.get("model"))
        if current_project_model in self.available_models:
            self.project_model_combo.setCurrentText(current_project_model)
        elif self.available_models: # リストにない場合は先頭を選択
            self.project_model_combo.setCurrentIndex(0)
        layout.addRow("プロジェクト使用モデル:", self.project_model_combo)

        self.project_system_prompt_input = QTextEdit(
            self.project_settings_edit.get("main_system_prompt",
                                           DEFAULT_PROJECT_SETTINGS.get("main_system_prompt"))
        )
        self.project_system_prompt_input.setMinimumHeight(100) # 少し小さく
        layout.addRow("メインシステムプロンプト:", self.project_system_prompt_input)

        # --- アプリケーション全体設定セクション ---
        layout.addRow(self._create_separator_line()) # 区切り線
        global_settings_label = QLabel("<b>アプリケーション全体設定</b>")
        layout.addRow(global_settings_label)

        self.global_default_model_combo = QComboBox()
        self.global_default_model_combo.addItems(self.available_models)
        current_global_default_model = self.global_config_edit.get("default_model",
                                                                    DEFAULT_GLOBAL_CONFIG.get("default_model"))
        if current_global_default_model in self.available_models:
            self.global_default_model_combo.setCurrentText(current_global_default_model)
        elif self.available_models:
            self.global_default_model_combo.setCurrentIndex(0)
        layout.addRow("新規プロジェクト用デフォルトモデル:", self.global_default_model_combo)

        # --- OK / Cancel ボタン ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setMinimumWidth(600) # ダイアログの最小幅

    def _create_separator_line(self) -> QFrame:
        """設定セクション間の区切り線を作成して返します。"""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def update_api_key_status_label(self):
        """APIキーがOSに保存されているか確認し、対応するラベルを更新します。"""
        if get_api_key(): # USERNAME_GEMINI がデフォルト
            self.api_key_status_label.setText("<font color='green'>OSの資格情報ストアに保存済み</font>")
        else:
            self.api_key_status_label.setText("<font color='red'>未保存 (または取得失敗)</font>")

    def _save_api_key_to_os(self):
        """入力フィールドのAPIキーをOSの資格情報ストアに保存します。"""
        key_to_save = self.api_key_input_for_save.text().strip()
        if not key_to_save:
            # 空の場合は、現在保存されているキーを削除するかどうかを尋ねる
            if get_api_key(): # 現在キーが保存されている場合のみ尋ねる
                reply = QMessageBox.question(self, "APIキー削除確認",
                                           "APIキーが入力されていません。現在OSに保存されているAPIキーを削除しますか？",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    success, msg = delete_api_key() # 削除実行
                    QMessageBox.information(self, "APIキー操作完了", msg)
                else:
                    return # 何もしない
            else: # キーが元々保存されていない場合は何もしない
                QMessageBox.information(self, "情報", "APIキーが入力されていません。保存するキーを入力してください。")
                return
        else: # キーが入力されている場合は保存
            success, msg = save_api_key(key_to_save)
            if success:
                self.api_key_input_for_save.clear() # 保存成功時は入力欄をクリア
                QMessageBox.information(self, "APIキー保存完了", msg)
            else:
                QMessageBox.warning(self, "APIキー保存エラー", msg)
        self.update_api_key_status_label() # 保存/削除後の状態を再表示

    def _delete_api_key_from_os(self):
        """OSの資格情報ストアに保存されているAPIキーを削除します。"""
        if not get_api_key(): # そもそもキーがなければ何もしない
            QMessageBox.information(self, "情報", "OSに保存されているAPIキーはありません。")
            return

        reply = QMessageBox.question(self, "APIキー削除確認",
                                   "OSに保存されているAPIキーを削除しますか？\nこの操作は元に戻せません。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, msg = delete_api_key()
            QMessageBox.information(self, "APIキー削除完了", msg)
            self.update_api_key_status_label() # 削除後の状態を再表示

    def accept(self):
        """OKボタンが押されたときの処理。編集された設定を内部変数に格納します。

        実際のファイルへの保存は、このダイアログの呼び出し元 (MainWindow) が
        `get_updated_configs()` を使って行います。
        """
        # グローバル設定の編集結果を格納
        self.global_config_edit["default_model"] = self.global_default_model_combo.currentText()
        # active_project はこのダイアログでは編集不可 (MainWindowが管理)

        # プロジェクト設定の編集結果を格納
        self.project_settings_edit["project_display_name"] = self.project_display_name_input.text().strip()
        self.project_settings_edit["model"] = self.project_model_combo.currentText()
        self.project_settings_edit["main_system_prompt"] = self.project_system_prompt_input.toPlainText().strip()

        super().accept() # QDialog.Accepted を発行

    def get_updated_configs(self) -> tuple[dict, dict]:
        """編集されたグローバル設定とプロジェクト設定をタプルで返します。

        このメソッドは、ダイアログが `Accepted` で閉じられた後に呼び出されることを想定しています。

        Returns:
            tuple[dict, dict]: (更新されたグローバル設定の辞書, 更新されたプロジェクト設定の辞書)
        """
        return self.global_config_edit, self.project_settings_edit

if __name__ == '__main__':
    """SettingsDialog の基本的な表示テスト。"""
    app = QApplication(sys.argv)

    # テスト用のダミー設定データ
    dummy_global_config = {
        "active_project": "test_project",
        "default_model": "gemini-1.5-flash-latest",
        "available_models": ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-pro", "test-model"]
    }
    dummy_project_settings = {
        "project_display_name": "私のテストプロジェクト",
        "main_system_prompt": "これはテストプロジェクトのシステムプロンプトです。\nよろしくお願いします。",
        "model": "gemini-1.5-pro-latest"
    }

    print("--- SettingsDialog テスト ---")
    dialog = SettingsDialog(dummy_global_config, dummy_project_settings)

    if dialog.exec_() == QDialog.Accepted:
        print("\n設定ダイアログ: OK")
        updated_g_conf, updated_p_conf = dialog.get_updated_configs()
        print(f"  更新されたグローバル設定: {updated_g_conf}")
        print(f"  更新されたプロジェクト設定: {updated_p_conf}")
    else:
        print("\n設定ダイアログ: Cancel")

    print("\n--- APIキーなし、プロジェクト設定なしの場合のテスト ---")
    # APIキーはOS依存なので、ここでは get_api_key() の結果に依存する
    dialog_no_proj = SettingsDialog(dummy_global_config, None) # プロジェクト設定なし
    # dialog_no_proj.exec_() # 表示だけならこれでもOK

    print("\n--- テスト完了 ---")
    # sys.exit(app.exec_()) # MainWindowなどから実行時は不要
