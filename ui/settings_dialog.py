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
    QPushButton, QLabel, QMessageBox, QHBoxLayout, QFrame, QWidget, QDoubleSpinBox, QSpinBox,
    QFontComboBox, QSpinBox, QPushButton, QColorDialog, QVBoxLayout, QTabWidget # ★ QTabWidget を追加
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont # ★ 追加: QFont

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

        # --- AI編集支援用モデル設定 ---
        self.project_ai_edit_model_combo = QComboBox()
        # 選択肢の先頭に「プロジェクト使用モデルに同じ」を追加
        self.ai_edit_model_placeholder = "（プロジェクト使用モデルに同じ）"
        ai_edit_models_for_combo = [self.ai_edit_model_placeholder] + self.available_models
        self.project_ai_edit_model_combo.addItems(ai_edit_models_for_combo)

        current_ai_edit_model = self.project_settings_edit.get("ai_edit_model_name", "")
        if current_ai_edit_model and current_ai_edit_model in self.available_models:
            self.project_ai_edit_model_combo.setCurrentText(current_ai_edit_model)
        else: # 空白時またはリストにない場合はプレースホルダーを選択
            self.project_ai_edit_model_combo.setCurrentText(self.ai_edit_model_placeholder)
        layout.addRow("AI編集支援用モデル:", self.project_ai_edit_model_combo)
        # --- -------------------- ---

        self.project_system_prompt_input = QTextEdit() # まずインスタンスを作成
        self.project_system_prompt_input.setPlainText(
            self.project_settings_edit.get("main_system_prompt",
                                           DEFAULT_PROJECT_SETTINGS.get("main_system_prompt"))
        ) # setPlainText で設定
        self.project_system_prompt_input.setMinimumHeight(100) # 少し小さく
        layout.addRow("メインシステムプロンプト:", self.project_system_prompt_input)

        # --- ★★★ AI編集支援プロンプトテンプレート設定 (プロジェクト固有) ★★★ ---
        layout.addRow(self._create_separator_line())
        ai_edit_prompts_label = QLabel("<b>AI編集支援プロンプトテンプレート (プロジェクト固有)</b>")
        layout.addRow(ai_edit_prompts_label)

        # プロンプトテンプレートのキーとUI表示名のマッピング
        self.prompt_template_keys = {
            "description_edit": "「説明/メモ」編集用",
            "description_new": "「説明/メモ」新規作成用",
            "history_entry_add": "履歴エントリ追加用",
            "empty_description_template": "「説明/メモ」新規作成時の雛形"
        }
        self.ai_edit_prompt_inputs: dict[str, QTextEdit] = {}

        # ★★★ タブウィジェットを作成 ★★★
        self.prompt_tab_widget = QTabWidget()

        current_ai_prompts = self.project_settings_edit.get("ai_edit_prompts", DEFAULT_PROJECT_SETTINGS.get("ai_edit_prompts", {}))
        current_empty_template = self.project_settings_edit.get("empty_description_template", DEFAULT_PROJECT_SETTINGS.get("empty_description_template", ""))

        for key, display_name in self.prompt_template_keys.items():
            # 各テンプレート用のタブページウィジェットとレイアウトを作成
            tab_page_widget = QWidget()
            tab_page_layout = QVBoxLayout(tab_page_widget)
            tab_page_layout.setContentsMargins(5, 5, 5, 5) # タブ内のマージン調整

            text_edit = QTextEdit()
            text_edit.setMinimumHeight(150) # 各プロンプト入力欄の高さ (タブ内なので少し大きめに)
            
            if key == "empty_description_template":
                text_edit.setPlainText(current_empty_template)
                default_text = DEFAULT_PROJECT_SETTINGS.get("empty_description_template", "")
                tooltip_text = "利用可能なプレースホルダーはありません。"
            else:
                text_edit.setPlainText(current_ai_prompts.get(key, DEFAULT_PROJECT_SETTINGS.get("ai_edit_prompts", {}).get(key, "")))
                default_text = DEFAULT_PROJECT_SETTINGS.get("ai_edit_prompts", {}).get(key, "")
                if key == "description_edit":
                    tooltip_text = "利用可能なプレースホルダー: {item_name}, {current_text}, {user_instruction}"
                elif key == "description_new":
                    tooltip_text = "利用可能なプレースホルダー: {item_name}, {user_instruction}, {empty_description_template}"
                elif key == "history_entry_add":
                    tooltip_text = "利用可能なプレースホルダー: {item_name}, {user_instruction}, {item_description}, {item_existing_history}, {max_item_history_entries}"
                else:
                    tooltip_text = ""
            text_edit.setToolTip(tooltip_text)
            self.ai_edit_prompt_inputs[key] = text_edit # 保存用に QTextEdit を保持
            tab_page_layout.addWidget(text_edit)

            default_button = QPushButton("デフォルトに戻す")
            default_button.clicked.connect(lambda checked=False, k=key, dt=default_text: self.ai_edit_prompt_inputs[k].setPlainText(dt))
            tab_page_layout.addWidget(default_button, 0, Qt.AlignRight)
            
            # タブウィジェットにページを追加
            self.prompt_tab_widget.addTab(tab_page_widget, display_name)

        # フォームレイアウトにタブウィジェットを追加 (ラベルは空でも良いし、簡潔なものでも)
        layout.addRow("各種テンプレート:", self.prompt_tab_widget) # QFormLayoutに追加
        # --- ★★★ --------------------------------------------------------- ★★★ ---

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

        # --- 生成制御パラメータ (グローバル) ---
        generation_settings_label = QLabel("<b>AI応答生成の制御 (全体設定)</b>")
        layout.addRow(generation_settings_label)

        gen_params_layout = QHBoxLayout()
        self.temperature_spinbox = QDoubleSpinBox()
        self.temperature_spinbox.setRange(0.0, 2.0)
        self.temperature_spinbox.setSingleStep(0.1)
        self.temperature_spinbox.setValue(self.global_config_edit.get("generation_temperature", DEFAULT_GLOBAL_CONFIG.get("generation_temperature")))
        gen_params_layout.addWidget(QLabel("Temperature:"))
        gen_params_layout.addWidget(self.temperature_spinbox)
        gen_params_layout.addSpacing(15)

        self.top_p_spinbox = QDoubleSpinBox()
        self.top_p_spinbox.setRange(0.0, 1.0)
        self.top_p_spinbox.setSingleStep(0.01)
        self.top_p_spinbox.setValue(self.global_config_edit.get("generation_top_p", DEFAULT_GLOBAL_CONFIG.get("generation_top_p")))
        gen_params_layout.addWidget(QLabel("Top-P:"))
        gen_params_layout.addWidget(self.top_p_spinbox)
        gen_params_layout.addSpacing(15)

        self.top_k_spinbox = QSpinBox()
        self.top_k_spinbox.setRange(1, 100)
        self.top_k_spinbox.setValue(self.global_config_edit.get("generation_top_k", DEFAULT_GLOBAL_CONFIG.get("generation_top_k")))
        gen_params_layout.addWidget(QLabel("Top-K:"))
        gen_params_layout.addWidget(self.top_k_spinbox)
        gen_params_layout.addSpacing(15)

        self.max_tokens_spinbox = QSpinBox()
        self.max_tokens_spinbox.setRange(1, 8192)
        self.max_tokens_spinbox.setSuffix(" トークン")
        self.max_tokens_spinbox.setValue(self.global_config_edit.get("generation_max_output_tokens", DEFAULT_GLOBAL_CONFIG.get("generation_max_output_tokens")))
        gen_params_layout.addWidget(QLabel("最大トークン:")) # ラベル短縮
        gen_params_layout.addWidget(self.max_tokens_spinbox)
        gen_params_layout.addStretch()
        layout.addRow(gen_params_layout) # 1行でまとめて追加

        # --- フォント設定 (グローバル) ---
        layout.addRow(self._create_separator_line())
        font_settings_label = QLabel("<b>AI応答履歴のフォント設定 (全体設定)</b>")
        layout.addRow(font_settings_label)

        font_type_size_layout = QHBoxLayout()
        self.font_family_combo = QFontComboBox()
        current_font_family = self.global_config_edit.get("font_family", DEFAULT_GLOBAL_CONFIG.get("font_family"))
        self.font_family_combo.setCurrentFont(QFont(current_font_family))
        font_type_size_layout.addWidget(QLabel("フォント種類:"))
        font_type_size_layout.addWidget(self.font_family_combo)
        font_type_size_layout.addSpacing(15)

        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(6, 72)
        self.font_size_spinbox.setValue(self.global_config_edit.get("font_size", DEFAULT_GLOBAL_CONFIG.get("font_size")))
        self.font_size_spinbox.setSuffix(" pt")
        font_type_size_layout.addWidget(QLabel("サイズ:"))
        font_type_size_layout.addWidget(self.font_size_spinbox)
        font_type_size_layout.addSpacing(15) # ★★★ サイズと行間の間にスペーシング ★★★

        # --- ★★★ 行間設定を追加 ★★★ ---
        self.font_line_height_spinbox = QDoubleSpinBox()
        self.font_line_height_spinbox.setRange(0.5, 3.0) # 適切な範囲に調整
        self.font_line_height_spinbox.setSingleStep(0.1)
        self.font_line_height_spinbox.setDecimals(1) # 小数点以下1桁
        self.font_line_height_spinbox.setValue(
            self.global_config_edit.get("font_line_height", DEFAULT_GLOBAL_CONFIG.get("font_line_height", 1.5))
        )
        font_type_size_layout.addWidget(QLabel("行間:"))
        font_type_size_layout.addWidget(self.font_line_height_spinbox)
        # --- ★★★ ------------------- ★★★ ---

        font_type_size_layout.addStretch()
        layout.addRow(font_type_size_layout) # 1行でまとめて追加
        
        font_colors_layout = QHBoxLayout()
        # ユーザー発言の文字色
        self.font_color_user_button = QPushButton("ユーザー色") # ラベル短縮
        self.font_color_user_button.setToolTip("ユーザー発言の文字色を選択")
        self.font_color_user_button.clicked.connect(lambda: self._pick_color("font_color_user", self.font_color_user_preview))
        self.font_color_user_preview = QLabel()
        self._update_color_preview(self.font_color_user_preview, self.global_config_edit.get("font_color_user", DEFAULT_GLOBAL_CONFIG.get("font_color_user")))
        font_colors_layout.addWidget(self.font_color_user_button)
        font_colors_layout.addWidget(self.font_color_user_preview)
        font_colors_layout.addSpacing(10)

        # AI応答の文字色
        self.font_color_model_button = QPushButton("AI応答色") # ラベル短縮
        self.font_color_model_button.setToolTip("AI応答の文字色を選択")
        self.font_color_model_button.clicked.connect(lambda: self._pick_color("font_color_model", self.font_color_model_preview))
        self.font_color_model_preview = QLabel()
        self._update_color_preview(self.font_color_model_preview, self.global_config_edit.get("font_color_model", DEFAULT_GLOBAL_CONFIG.get("font_color_model")))
        font_colors_layout.addWidget(self.font_color_model_button)
        font_colors_layout.addWidget(self.font_color_model_preview)
        font_colors_layout.addSpacing(10)

        # AI最新応答の文字色
        self.font_color_model_latest_button = QPushButton("AI最新応答色") # ラベル短縮
        self.font_color_model_latest_button.setToolTip("AIの最新の応答の文字色を選択")
        self.font_color_model_latest_button.clicked.connect(lambda: self._pick_color("font_color_model_latest", self.font_color_model_latest_preview))
        self.font_color_model_latest_preview = QLabel()
        self._update_color_preview(self.font_color_model_latest_preview, self.global_config_edit.get("font_color_model_latest", DEFAULT_GLOBAL_CONFIG.get("font_color_model_latest")))
        font_colors_layout.addWidget(self.font_color_model_latest_button)
        font_colors_layout.addWidget(self.font_color_model_latest_preview)
        font_colors_layout.addStretch()
        layout.addRow("文字色設定:", font_colors_layout) # ラベルをつけて1行で追加

        # --- OK / Cancel ボタン ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setMinimumWidth(800) # ダイアログの最小幅
        self.setMinimumHeight(700) # ★★★ 最小高さを設定 ★★★

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

    def _pick_color(self, config_key: str, preview_label: QLabel):
        """カラーピッカーダイアログを開き、選択された色を設定とプレビューに反映します。"""
        initial_color_hex = self.global_config_edit.get(config_key, DEFAULT_GLOBAL_CONFIG.get(config_key))
        initial_color = QColor(initial_color_hex)
        color = QColorDialog.getColor(initial_color, self, "色を選択")
        if color.isValid():
            color_hex = color.name()
            self.global_config_edit[config_key] = color_hex
            self._update_color_preview(preview_label, color_hex)

    def _update_color_preview(self, label: QLabel, color_hex: str):
        """指定されたラベルの背景色とテキストを更新して色のプレビューを表示します。"""
        label.setText(color_hex)
        label.setStyleSheet(f"background-color: {color_hex}; color: {self._get_contrasting_text_color(color_hex)}; padding: 2px;")
        label.setFixedWidth(100) # プレビューの幅を固定

    def _get_contrasting_text_color(self, bg_hex_color: str) -> str:
        """背景色に対して見やすい文字色 (黒または白) を返します。"""
        try:
            color = QColor(bg_hex_color)
            # 輝度を計算 (簡易的な方法)
            # Y = 0.299*R + 0.587*G + 0.114*B (ITU-R BT.601)
            # 0-255の範囲なので、128を閾値とする
            brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            return "#000000" if brightness > 128 else "#FFFFFF"
        except:
            return "#000000" # エラー時は黒

    def accept(self):
        """OKボタンが押されたときの処理。編集された設定を内部変数に格納します。

        実際のファイルへの保存は、このダイアログの呼び出し元 (MainWindow) が
        `get_updated_configs()` を使って行います。
        """
        # グローバル設定の編集結果を格納
        self.global_config_edit["default_model"] = self.global_default_model_combo.currentText()
        self.global_config_edit["generation_temperature"] = self.temperature_spinbox.value()
        self.global_config_edit["generation_top_p"] = self.top_p_spinbox.value()
        self.global_config_edit["generation_top_k"] = self.top_k_spinbox.value()
        self.global_config_edit["generation_max_output_tokens"] = self.max_tokens_spinbox.value()
        # フォント設定の保存
        self.global_config_edit["font_family"] = self.font_family_combo.currentFont().family()
        self.global_config_edit["font_size"] = self.font_size_spinbox.value()
        self.global_config_edit["font_line_height"] = self.font_line_height_spinbox.value() # ★★★ 行間を保存 ★★★
        # カラーは _pick_color で self.global_config_edit に直接保存済み
        # active_project はこのダイアログでは編集不可 (MainWindowが管理)

        # プロジェクト設定の編集結果を格納
        self.project_settings_edit["project_display_name"] = self.project_display_name_input.text().strip()
        self.project_settings_edit["model"] = self.project_model_combo.currentText()
        selected_ai_edit_model = self.project_ai_edit_model_combo.currentText()
        if selected_ai_edit_model == self.ai_edit_model_placeholder:
            self.project_settings_edit["ai_edit_model_name"] = "" # プレースホルダー選択時は空文字で保存
        else:
            self.project_settings_edit["ai_edit_model_name"] = selected_ai_edit_model
        self.project_settings_edit["main_system_prompt"] = self.project_system_prompt_input.toPlainText().strip()

        # ★★★ AI編集支援プロンプトテンプレートの保存 ★★★
        updated_ai_prompts = {}
        for key, text_edit_widget in self.ai_edit_prompt_inputs.items():
            if key == "empty_description_template":
                self.project_settings_edit["empty_description_template"] = text_edit_widget.toPlainText()
            else:
                updated_ai_prompts[key] = text_edit_widget.toPlainText()
        self.project_settings_edit["ai_edit_prompts"] = updated_ai_prompts
        # ★★★ ------------------------------------ ★★★

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
