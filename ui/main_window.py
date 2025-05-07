# ui/main_window.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QTextBrowser, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView,
    QTabWidget, QApplication, QDialog, QSplitter, QFrame, QCheckBox,
    QSizePolicy, QStyle, qApp, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QDesktopServices # 使用しない可能性あり

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.config_manager import (
    load_global_config, save_global_config,
    load_project_settings, save_project_settings,
    list_project_dir_names # プロジェクト一覧取得用
)
from core.subprompt_manager import load_subprompts, save_subprompts
from core.data_manager import get_item # 他にも data_manager の関数を UI から直接呼ぶなら追加
from core.api_key_manager import get_api_key as get_os_api_key

# --- uiモジュールインポート ---
from ui.settings_dialog import SettingsDialog
from ui.subprompt_dialog import SubPromptEditDialog
from ui.data_widget import DataManagementWidget # DataManagementWidget をインポート

# --- Gemini API ハンドラー ---
from core.gemini_handler import configure_gemini_api, generate_response, is_configured


# ==============================================================================
# サブプロンプト項目用カスタムウィジェット
# ==============================================================================
class SubPromptItemWidget(QWidget):
    checkStateChanged = pyqtSignal(bool)
    editRequested = pyqtSignal()
    deleteRequested = pyqtSignal()

    def __init__(self, name, is_checked=False, parent=None):
        super().__init__(parent)
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        self.checkbox = QCheckBox(name)
        self.checkbox.setChecked(is_checked)
        self.checkbox.stateChanged.connect(lambda state: self.checkStateChanged.emit(state == Qt.Checked))
        layout.addWidget(self.checkbox, 1) # チェックボックスがスペースを優先的に使う
        edit_button = QPushButton()
        edit_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton)) # SP_LineEditClearButton SP_DialogSaveButton
        edit_button.setToolTip("編集")
        edit_button.setFixedSize(24, 24)
        edit_button.clicked.connect(self.editRequested.emit)
        layout.addWidget(edit_button)
        delete_button = QPushButton()
        delete_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delete_button.setToolTip("削除")
        delete_button.setFixedSize(24, 24)
        delete_button.clicked.connect(self.deleteRequested.emit)
        layout.addWidget(delete_button)
        self.setLayout(layout)

    def set_name(self, name):
        self.name = name
        self.checkbox.setText(name)

    def set_checked(self, checked):
        self.checkbox.setChecked(checked)

    def is_checked(self):
        return self.checkbox.isChecked()

# ==============================================================================
# メインウィンドウクラス
# ==============================================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        # --- ★★★ 1. アクティブプロジェクト名と関連設定の初期化 ★★★ ---
        self.global_config = load_global_config()
        self.current_project_dir_name = self.global_config.get("active_project", "default_project") # ディレクトリ名
        self.current_project_settings = {} # プロジェクト固有設定 (main_system_prompt, model など)
        self.subprompts = {} # プロジェクトごとのサブプロンプト
        self.checked_subprompts = {} # プロジェクトごとのチェック状態

        self._load_current_project_data() # ★ プロジェクトデータをロードするメソッド呼び出し
        # ----------------------------------------------------------

        self.gemini_configured = False # API設定フラグ
        self.init_ui()
        self.configure_gemini() # API設定を試みる

    def _load_current_project_data(self):
        """現在アクティブなプロジェクトのデータを読み込む"""
        print(f"--- Loading data for project: '{self.current_project_dir_name}' ---")
        # プロジェクト設定 (main_system_prompt, model, project_display_name) の読み込み
        project_settings = load_project_settings(self.current_project_dir_name)
        if project_settings is None: # 読み込み失敗またはプロジェクト存在せず
            print(f"警告: プロジェクト '{self.current_project_dir_name}' の設定を読み込めませんでした。デフォルトを使用します。")
            # 必要ならここで新しいプロジェクトを初期化するロジック
            if not os.path.exists(os.path.join("data", self.current_project_dir_name)):
                 print(f"  プロジェクトフォルダ {self.current_project_dir_name} が存在しません。作成を試みます。")
                 # プロジェクトフォルダとデフォルト設定ファイルを作成
                 from core.config_manager import DEFAULT_PROJECT_SETTINGS, save_project_settings
                 if save_project_settings(self.current_project_dir_name, DEFAULT_PROJECT_SETTINGS.copy()):
                      project_settings = DEFAULT_PROJECT_SETTINGS.copy()
                 else:
                      # それでもダメなら最低限のフォールバック
                      project_settings = {"main_system_prompt": "Error loading prompt.", "model": "gemini-1.5-pro-latest", "project_display_name": self.current_project_dir_name + " (Error)"}
            else: # フォルダはあるが設定ファイル読み込み失敗
                 project_settings = {"main_system_prompt": "Error loading prompt.", "model": "gemini-1.5-pro-latest", "project_display_name": self.current_project_dir_name + " (Error)"}
        self.current_project_settings = project_settings
        print(f"  Project settings loaded: {self.current_project_settings}")

        # サブプロンプトの読み込み
        self.subprompts = load_subprompts(self.current_project_dir_name)
        self.checked_subprompts = {
            cat: set() for cat in self.subprompts.keys()
        } # チェック状態を初期化
        print(f"  Subprompts loaded: {len(self.subprompts)} categories.")

        # メインシステムプロンプトをUIに反映 (init_ui 後に呼ばれるため、UI要素が存在する前提)
        if hasattr(self, 'system_prompt_input_main'): # UI要素があるか確認
            self.system_prompt_input_main.setPlainText(
                self.current_project_settings.get("main_system_prompt", "")
            )
        # ウィンドウタイトルにプロジェクト表示名を設定
        display_name = self.current_project_settings.get("project_display_name", self.current_project_dir_name)
        self.setWindowTitle(f"TRPG AI Tool - {display_name}")


    def init_ui(self):
        self.setWindowTitle(f"TRPG AI Tool - Loading...") # 初期タイトル
        self.setGeometry(300, 300, 1200, 800) # ウィンドウサイズ

        main_layout = QHBoxLayout(self) # 水平分割

        # --- 左側エリア (メインプロンプト、AI応答履歴、入力) ---
        left_layout = QVBoxLayout()
        # 左上: メインシステムプロンプト
        left_layout.addWidget(QLabel("メインシステムプロンプト:"))
        self.system_prompt_input_main = QTextEdit()
        self.system_prompt_input_main.setPlaceholderText("AIへの全体的な指示を入力...")
        self.system_prompt_input_main.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.system_prompt_input_main.setFixedHeight(100) # 高さを固定または最小/最大設定
        # ★★★ 初期値は _load_current_project_data で設定される ★★★
        # self.system_prompt_input_main.setPlainText(self.current_project_settings.get("main_system_prompt", ""))
        left_layout.addWidget(self.system_prompt_input_main)

        # 左中: AI応答履歴
        left_layout.addWidget(QLabel("AI応答履歴:"))
        self.response_display = QTextBrowser()
        self.response_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.response_display)

        # 左下: ユーザー入力と送信ボタン
        input_area_layout = QHBoxLayout()
        self.user_input = QTextEdit()
        self.user_input.setPlaceholderText("ここにメッセージを入力...")
        self.user_input.setFixedHeight(80) # 高さを固定
        input_area_layout.addWidget(self.user_input)
        send_button_layout = QVBoxLayout() # ボタンを縦に並べる
        self.send_button = QPushButton("送信")
        self.send_button.clicked.connect(self.on_send_button_clicked)
        self.send_button.setFixedHeight(80) # 高さを入力欄に合わせる
        send_button_layout.addWidget(self.send_button)
        input_area_layout.addLayout(send_button_layout)
        left_layout.addLayout(input_area_layout)

        # --- 右側エリア (設定ボタン、サブプロンプト、データ管理) ---
        right_layout = QVBoxLayout()
        # 右上: 設定ボタン
        settings_button_layout = QHBoxLayout()
        settings_button_layout.addStretch() # ボタンを右寄せ
        self.settings_button = QPushButton("設定")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        settings_button_layout.addWidget(self.settings_button)
        right_layout.addLayout(settings_button_layout)

        # 右側を上下に分割するスプリッター
        splitter = QSplitter(Qt.Vertical)

        # 上部: サブシステムプロンプトエリア
        subprompt_area = QWidget()
        subprompt_layout = QVBoxLayout(subprompt_area)
        subprompt_label_layout = QHBoxLayout()
        subprompt_label_layout.addWidget(QLabel("サブシステムプロンプト:"))
        subprompt_label_layout.addStretch()
        self.add_subprompt_category_button = QPushButton("カテゴリ追加")
        self.add_subprompt_category_button.clicked.connect(self.add_subprompt_category)
        self.add_subprompt_button = QPushButton("プロンプト追加")
        self.add_subprompt_button.clicked.connect(lambda: self.add_or_edit_subprompt())
        subprompt_label_layout.addWidget(self.add_subprompt_category_button)
        subprompt_label_layout.addWidget(self.add_subprompt_button)
        subprompt_layout.addLayout(subprompt_label_layout)
        self.subprompt_tab_widget = QTabWidget()
        self.subprompt_tab_widget.currentChanged.connect(self._on_subprompt_tab_changed)
        self.subprompt_lists = {} # カテゴリ名をキー、QListWidgetを値とする辞書
        subprompt_layout.addWidget(self.subprompt_tab_widget)
        splitter.addWidget(subprompt_area)

        # 下部: データ管理エリア
        # --- ★★★ DataManagementWidget に project_dir_name を渡す ★★★ ---
        self.data_management_widget = DataManagementWidget(project_dir_name=self.current_project_dir_name, parent=self)
        # self.data_management_widget.checkedItemsChanged.connect(self.handle_data_check_change) # 必要なら接続
        # ----------------------------------------------------------------
        splitter.addWidget(self.data_management_widget)
        self.data_management_widget.addCategoryRequested.connect(self._handle_add_category_request)
        self.data_management_widget.addItemRequested.connect(self._handle_add_item_request)
        splitter.setSizes([self.height() // 2, self.height() // 2]) # おおよその分割比率

        right_layout.addWidget(splitter)

        # メインレイアウトに左右エリアを追加
        main_layout.addLayout(left_layout, 7) # 左側を7割
        main_layout.addLayout(right_layout, 3) # 右側を3割

        # UI初期化後にプロジェクトデータを再度読み込み、UIに反映
        self._load_current_project_data()
        self.refresh_subprompt_tabs() # サブプロンプトタブも更新


    def configure_gemini(self):
        """Gemini APIクライアントを設定する"""
        api_key = get_os_api_key()
        if api_key:
            success, message = configure_gemini_api(api_key)
            if success:
                print(f"Gemini API設定完了 (OS資格情報からキー取得, Project Model: {self.current_project_settings.get('model')})")
                self.gemini_configured = True
            else:
                QMessageBox.warning(self, "API設定エラー", f"Gemini APIクライアントの設定に失敗しました:\n{message}")
                self.gemini_configured = False
        else:
            QMessageBox.information(self, "APIキー未設定", "Gemini APIキーがOSの資格情報に保存されていません。\n「設定」からAPIキーを保存してください。")
            self.gemini_configured = False

    def open_settings_dialog(self):
        """設定ダイアログを開く"""
        # --- ★★★ SettingsDialogにグローバル設定と現在のプロジェクト設定を別々に渡す ★★★ ---
        dialog = SettingsDialog(self.global_config, self.current_project_settings, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            # --- ★★★ 更新された設定をタプルで受け取る ★★★ ---
            updated_global_config, updated_project_settings = dialog.get_updated_configs()

            # グローバル設定の保存
            if self.global_config != updated_global_config: # 変更があった場合のみ保存
                self.global_config = updated_global_config
                save_global_config(self.global_config)
                print("グローバル設定が更新・保存されました。")

            # プロジェクト固有設定の保存
            if self.current_project_settings != updated_project_settings: # 変更があった場合のみ保存
                self.current_project_settings = updated_project_settings
                save_project_settings(self.current_project_dir_name, self.current_project_settings)
                print(f"プロジェクト '{self.current_project_dir_name}' の設定が更新・保存されました。")

            # 設定変更をUIに反映
            self.system_prompt_input_main.setPlainText(self.current_project_settings.get("main_system_prompt", ""))
            display_name = self.current_project_settings.get("project_display_name", self.current_project_dir_name)
            self.setWindowTitle(f"TRPG AI Tool - {display_name}")
            self.configure_gemini() # モデルが変更された可能性があるので再設定
            print("設定ダイアログの変更が適用されました。")


    def on_send_button_clicked(self):
        """送信ボタンが押されたときの処理"""
        if not self.gemini_configured:
            QMessageBox.warning(self, "API未設定", "Gemini APIが設定されていません。設定画面からAPIキーを入力してください。")
            return

        user_text = self.user_input.toPlainText().strip()
        if not user_text:
            return

        self.response_display.append(f"<font color='blue'><b>あなた:</b></font><br>{user_text}<br>")
        self.user_input.clear()
        QApplication.processEvents() # UIの応答性を保つ

        # --- プロンプト構築 ---
        final_prompt_parts = []
        # 1. メインシステムプロンプト
        main_system_prompt = self.current_project_settings.get("main_system_prompt", "").strip()
        if main_system_prompt:
            final_prompt_parts.append(main_system_prompt)

        # 2. 選択されたサブプロンプト
        active_subprompts_content = []
        subprompt_specific_models = []
        for category, names in self.checked_subprompts.items():
            if category in self.subprompts:
                for name in names:
                    if name in self.subprompts[category]:
                        sub_data = self.subprompts[category][name]
                        prompt_text = sub_data.get("prompt", "")
                        # --- ★★★ サブプロンプトのモデルを取得 ★★★ ---
                        sub_model = sub_data.get("model", "")
                        if sub_model: # サブプロンプトにモデル指定があればそれを記録
                            subprompt_specific_models.append(sub_model)
                        # ------------------------------------
                        if prompt_text:
                            active_subprompts_content.append(f"--- サブプロンプト: {category} - {name} ---\n{prompt_text}")
        if active_subprompts_content:
            final_prompt_parts.append("\n--- 選択されたサブプロンプト情報 ---\n" + "\n\n".join(active_subprompts_content))

        # 3. 選択されたデータアイテムの情報
        checked_data_for_prompt = []
        # --- ★★★ data_management_widget から project_dir_name を使って情報を取得 ★★★ ---
        checked_data_items = self.data_management_widget.get_checked_items() # {category: {item_id1, item_id2}}
        for category, item_ids in checked_data_items.items():
            for item_id in item_ids:
                # ★ get_item に project_dir_name を渡す
                item_detail = get_item(self.current_project_dir_name, category, item_id)
                if item_detail:
                    item_info_str = f"--- データ: {category} - {item_detail.get('name', 'N/A')} ---\n"
                    item_info_str += f"名前: {item_detail.get('name', 'N/A')}\n"
                    item_info_str += f"説明/メモ: {item_detail.get('description', '')}\n"
                    tags = item_detail.get('tags', [])
                    if tags: item_info_str += f"タグ: {', '.join(tags)}\n"
                    checked_data_for_prompt.append(item_info_str)
        if checked_data_for_prompt:
            final_prompt_parts.append("\n--- 選択されたデータアイテム情報 ---\n" + "\n".join(checked_data_for_prompt))
        # -----------------------------------------------------------------------------

        # 4. ユーザーの入力
        final_prompt_parts.append(f"\n--- ユーザーの入力 ---\n{user_text}")
        final_prompt = "\n\n".join(final_prompt_parts).strip()
        print("--- Final Prompt to AI ---")
        print(final_prompt)
        print("--------------------------")

        # AIに送信 (モデルはプロジェクト設定から取得)
        # --- ★★★ AIに送信するモデルの決定ロジック ★★★ ---
        target_model_for_ai = self.current_project_settings.get("model", self.global_config.get("default_model")) # まずプロジェクトモデル
        # サブプロンプトに固有のモデル指定があれば、それを優先する（複数あれば最初のものを採用するなどのルールが必要）
        # ここでは、チェックされたサブプロンプトの中に一つでもモデル指定があれば、その中で最初に見つかったものを使う、という単純なルールにする
        if subprompt_specific_models:
            target_model_for_ai = subprompt_specific_models[0]
            print(f"  Using model specified in subprompt: {target_model_for_ai}")
        else:
            print(f"  No specific model in subprompts, using project model: {target_model_for_ai}")
        # ------------------------------------------------

        ai_response, error_msg = generate_response(target_model_for_ai, final_prompt) # ★ 決定したモデルを使用

        if error_msg:
            self.response_display.append(f"<font color='red'><b>エラー:</b> {error_msg}</font><br>")
        elif ai_response:
            self.response_display.append(f"<font color='green'><b>Gemini ({target_model_for_ai}):</b></font><br>{ai_response}<br>")
        else:
            self.response_display.append("<font color='orange'><b>AIからの応答がありませんでした。</b></font><br>")

    # --- サブプロンプト管理メソッド (project_dir_name を使用するように修正) ---
    def refresh_subprompt_tabs(self):
        current_tab_text = None
        current_tab_index = self.subprompt_tab_widget.currentIndex()
        if current_tab_index != -1:
             current_tab_text = self.subprompt_tab_widget.tabText(current_tab_index)

        self.subprompt_tab_widget.clear()
        self.subprompt_lists.clear()

        # ★★★ self.subprompts は _load_current_project_data で既にロード済み ★★★
        categories = sorted(self.subprompts.keys())
        if not categories: # サブプロンプトデータが空の場合
             if "一般" not in self.subprompts:
                  self.subprompts["一般"] = {} # デフォルトカテゴリをメモリ上に作成
                  categories.append("一般")
                  # ★★★ save_subprompts に project_dir_name を渡す ★★★
                  if save_subprompts(self.current_project_dir_name, self.subprompts):
                       print(f"プロジェクト '{self.current_project_dir_name}' にデフォルトカテゴリ'一般'(サブプロンプト)を作成しました。")

        # チェック状態の整合性を取る
        self.checked_subprompts = {cat: self.checked_subprompts.get(cat, set()) for cat in categories}

        new_tab_index = -1
        for i, category in enumerate(categories):
            list_widget = QListWidget()
            self.subprompt_lists[category] = list_widget
            checked_names_in_cat = self.checked_subprompts.get(category, set())
            subprompt_names_in_cat = sorted(self.subprompts.get(category, {}).keys())

            for name in subprompt_names_in_cat:
                is_checked = name in checked_names_in_cat
                item = QListWidgetItem(list_widget)
                item_widget = SubPromptItemWidget(name, is_checked)
                item_widget.checkStateChanged.connect(
                    lambda checked_state, current_name=name, current_category=category: \
                        self._handle_subprompt_check_change(current_category, current_name, checked_state)
                )
                item_widget.editRequested.connect(
                    lambda current_name=name, current_category=category: self.add_or_edit_subprompt(current_category, current_name)
                )
                item_widget.deleteRequested.connect(
                    lambda current_name=name, current_category=category: self.delete_subprompt(current_category, [current_name])
                )
                item.setSizeHint(item_widget.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, item_widget)
            self.subprompt_tab_widget.addTab(list_widget, category)
            if category == current_tab_text:
                new_tab_index = i
        if new_tab_index != -1:
             self.subprompt_tab_widget.setCurrentIndex(new_tab_index)
        elif self.subprompt_tab_widget.count() > 0:
             self.subprompt_tab_widget.setCurrentIndex(0)

    def _on_subprompt_tab_changed(self, index):
        # print(f"Subprompt tab changed to: {index}")
        pass # 必要なら何か処理

    def _handle_subprompt_check_change(self, category, name, is_checked):
        if category not in self.checked_subprompts:
            self.checked_subprompts[category] = set()
        if is_checked:
            self.checked_subprompts[category].add(name)
        else:
            self.checked_subprompts[category].discard(name)
        print(f"Subprompt checked: {category} - {name} = {is_checked}")
        # ここでプロンプトプレビューを更新するなどの処理も可能

    def add_subprompt_category(self):
        category_name, ok = QInputDialog.getText(self, "サブプロンプト カテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name:
            if category_name not in self.subprompts:
                self.subprompts[category_name] = {}
                # ★★★ save_subprompts に project_dir_name ★★★
                if save_subprompts(self.current_project_dir_name, self.subprompts):
                    self.refresh_subprompt_tabs()
                    # 追加したタブを選択状態にする
                    for i in range(self.subprompt_tab_widget.count()):
                        if self.subprompt_tab_widget.tabText(i) == category_name:
                            self.subprompt_tab_widget.setCurrentIndex(i)
                            break
                else: QMessageBox.warning(self, "保存エラー", "カテゴリの保存に失敗しました。")
            else: QMessageBox.warning(self, "エラー", "既に存在するカテゴリ名です。")
        elif ok : QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")


    def add_or_edit_subprompt(self, category=None, name=None):
        current_category_name = category
        if not current_category_name:
            current_tab_index = self.subprompt_tab_widget.currentIndex()
            if current_tab_index == -1:
                QMessageBox.warning(self, "カテゴリ未選択", "サブプロンプトを追加/編集するカテゴリを選択してください。")
                return
            current_category_name = self.subprompt_tab_widget.tabText(current_tab_index)

        initial_data = {"name": "", "prompt": "", "model": self.current_project_settings.get("model", "")} # デフォルトモデルを初期値に
        is_editing = False
        if name and current_category_name in self.subprompts and name in self.subprompts[current_category_name]:
            initial_data = self.subprompts[current_category_name][name].copy()
            initial_data["name"] = name # 編集中は名前も渡す
            is_editing = True

        dialog = SubPromptEditDialog(initial_data, parent=self, is_editing=is_editing, current_category=current_category_name)
        if dialog.exec_() == QDialog.Accepted:
            new_data = dialog.get_data()
            new_name = new_data.pop("name") # 名前はキーとして使うのでデータからは除く

            if not current_category_name in self.subprompts: # 万が一カテゴリが消えていたら作成
                self.subprompts[current_category_name] = {}

            # 編集中で名前が変更された場合は、古い名前のデータを削除
            if is_editing and name != new_name and name in self.subprompts[current_category_name]:
                del self.subprompts[current_category_name][name]
                # チェック状態も更新
                if name in self.checked_subprompts.get(current_category_name, set()):
                    self.checked_subprompts[current_category_name].remove(name)
                    if new_name not in self.subprompts[current_category_name]: # 新しい名前がまだなければ
                         self.checked_subprompts[current_category_name].add(new_name)


            self.subprompts[current_category_name][new_name] = new_data
            # ★★★ save_subprompts に project_dir_name ★★★
            if save_subprompts(self.current_project_dir_name, self.subprompts):
                self.refresh_subprompt_tabs()
            else:
                QMessageBox.warning(self, "保存エラー", "サブプロンプトの保存に失敗しました。")

    def delete_subprompt(self, category, names_to_delete):
        if not category in self.subprompts: return
        deleted_count = 0
        for name in names_to_delete:
            if name in self.subprompts[category]:
                del self.subprompts[category][name]
                if category in self.checked_subprompts and name in self.checked_subprompts[category]:
                    self.checked_subprompts[category].remove(name)
                deleted_count += 1
        if deleted_count > 0:
            # ★★★ save_subprompts に project_dir_name ★★★
            if save_subprompts(self.current_project_dir_name, self.subprompts):
                self.refresh_subprompt_tabs()
            else:
                QMessageBox.warning(self, "保存エラー", "サブプロンプトの削除内容の保存に失敗しました。")

    # --- データ管理ウィジェット連携メソッド ---
    def _handle_add_category_request(self):
        """DataManagementWidgetからのカテゴリ追加要求を処理"""
        category_name, ok = QInputDialog.getText(self, "データカテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name:
            # ★★★ data_management_widget に直接指示を出すか、シグナル経由が良いか検討 ★★★
            # ここでは data_management_widget のメソッドを直接呼ぶ
            self.data_management_widget.add_new_category_result(category_name)
        elif ok:
            QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")

    def _handle_add_item_request(self, category_from_data_widget):
        """DataManagementWidgetからのアイテム追加要求を処理"""
        item_name, ok = QInputDialog.getText(self, "アイテム追加", f"カテゴリ '{category_from_data_widget}' に追加するアイテムの名前:")
        if ok and item_name:
            self.data_management_widget.add_new_item_result(category_from_data_widget, item_name)
        elif ok:
            QMessageBox.warning(self, "入力エラー", "アイテム名を入力してください。")

    # def handle_data_check_change(self, checked_items):
    # print(f"MainWindow: Checked data items changed: {checked_items}")
    # 必要に応じてここで何か処理

    def closeEvent(self, event):
        """ウィンドウが閉じられるときの処理"""
        # 現在のメインシステムプロンプトをプロジェクト設定に保存
        current_main_prompt = self.system_prompt_input_main.toPlainText()
        if self.current_project_settings.get("main_system_prompt") != current_main_prompt:
            self.current_project_settings["main_system_prompt"] = current_main_prompt
            save_project_settings(self.current_project_dir_name, self.current_project_settings)
            print("終了時にメインシステムプロンプトを保存しました。")
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # アプリケーションアイコンの設定 (任意)
    # app_icon = QIcon("path/to/your/icon.png")
    # app.setWindowIcon(app_icon)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())

