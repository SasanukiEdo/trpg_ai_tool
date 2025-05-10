# ui/main_window.py

"""TRPG AI Toolのメインウィンドウとアプリケーション全体の制御を提供します。

このモジュールは `MainWindow` クラスを定義しており、ユーザーインターフェースの
主要な部分（メインプロンプト入力、AI応答表示、サブプロンプト管理、
データ管理など）を統合し、ユーザー操作に応じて各機能モジュールと連携します。

プロジェクト単位でのデータ管理の基盤となり、アクティブなプロジェクトの
設定やデータを読み込み、UIに反映する役割も担います。
プロジェクトの選択機能も提供します。
"""

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QTextBrowser, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView,
    QTabWidget, QApplication, QDialog, QSplitter, QFrame, QCheckBox,
    QSizePolicy, QStyle, qApp, QInputDialog, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.config_manager import (
    load_global_config, save_global_config,
    load_project_settings, save_project_settings,
    list_project_dir_names, # プロジェクト一覧取得用 (将来的に使用)
    DEFAULT_PROJECT_SETTINGS # プロジェクト初期化用
)
from core.subprompt_manager import load_subprompts, save_subprompts
from core.data_manager import get_item # AIプロンプト構築時に使用
from core.api_key_manager import get_api_key as get_os_api_key # OS資格情報からAPIキー取得

# --- uiモジュールインポート ---
from ui.settings_dialog import SettingsDialog
from ui.subprompt_dialog import SubPromptEditDialog
from ui.data_widget import DataManagementWidget

# --- Gemini API ハンドラー ---
from core.gemini_handler import configure_gemini_api, generate_response, is_configured


# ==============================================================================
# サブプロンプト項目用カスタムウィジェット (MainWindow内で定義)
# ==============================================================================
class SubPromptItemWidget(QWidget):
    """サブプロンプトリストの各項目を表示・操作するためのカスタムウィジェット。

    サブプロンプト名を表示するチェックボックス、編集ボタン、削除ボタンを提供します。
    これらの操作はシグナルを通じて親ウィジェット（MainWindow）に通知されます。

    Attributes:
        checkStateChanged (pyqtSignal): チェックボックスの状態変更時に発行。bool値を渡す。
        editRequested (pyqtSignal): 編集ボタンクリック時に発行。
        deleteRequested (pyqtSignal): 削除ボタンクリック時に発行。
        name (str): このウィジェットが表すサブプロンプトの名前。
    """
    checkStateChanged = pyqtSignal(bool)
    editRequested = pyqtSignal()
    deleteRequested = pyqtSignal()

    def __init__(self, name: str, is_checked: bool = False, parent: QWidget | None = None):
        """SubPromptItemWidgetのコンストラクタ。

        Args:
            name (str): 表示するサブプロンプトの名前。
            is_checked (bool, optional): チェックボックスの初期状態。デフォルトは False。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
        """
        super().__init__(parent)
        self.name: str = name
        """str: このウィジェットが表すサブプロンプトの名前。"""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        self.checkbox = QCheckBox(name)
        self.checkbox.setChecked(is_checked)
        self.checkbox.stateChanged.connect(lambda state: self.checkStateChanged.emit(state == Qt.Checked))
        layout.addWidget(self.checkbox, 1) # チェックボックスがスペースを優先的に使用

        edit_button = QPushButton()
        edit_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton)) # 編集アイコン
        edit_button.setToolTip(f"サブプロンプト「{name}」を編集")
        edit_button.setFixedSize(24, 24)
        edit_button.clicked.connect(self.editRequested.emit)
        layout.addWidget(edit_button)

        delete_button = QPushButton()
        delete_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon)) # 削除アイコン
        delete_button.setToolTip(f"サブプロンプト「{name}」を削除")
        delete_button.setFixedSize(24, 24)
        delete_button.clicked.connect(self.deleteRequested.emit)
        layout.addWidget(delete_button)

        self.setLayout(layout)

    def set_name(self, name: str):
        """ウィジェットに表示されるサブプロンプト名を更新します。

        Args:
            name (str): 新しいサブプロンプト名。
        """
        self.name = name
        self.checkbox.setText(name)

    def set_checked(self, checked: bool):
        """チェックボックスの状態をプログラムから設定します。シグナルは発行しません。

        Args:
            checked (bool): 新しいチェック状態。
        """
        self.checkbox.blockSignals(True) # シグナル発行を一時的に抑制
        self.checkbox.setChecked(checked)
        self.checkbox.blockSignals(False)

    def is_checked(self) -> bool:
        """現在のチェックボックスの状態を返します。

        Returns:
            bool: チェックされていれば True、そうでなければ False。
        """
        return self.checkbox.isChecked()

# ==============================================================================
# メインウィンドウクラス
# ==============================================================================
class MainWindow(QWidget):
    """TRPG AI Tool のメインウィンドウクラス。

    アプリケーションのUI全体の構築、ユーザーインタラクションの処理、
    コア機能モジュールとの連携、プロジェクトデータの管理など、
    アプリケーションの中心的な役割を担います。
    プロジェクト選択機能も提供します。

    Attributes:
        global_config (dict): アプリケーション全体のグローバル設定。
        current_project_dir_name (str): 現在アクティブなプロジェクトのディレクトリ名。
        current_project_settings (dict): 現在アクティブなプロジェクトの固有設定。
        subprompts (dict): 現在アクティブなプロジェクトのサブプロンプトデータ。
        checked_subprompts (dict): {カテゴリ名: {サブプロンプト名のセット}} でチェック状態を保持。
        gemini_configured (bool): Gemini APIが設定済みかを示すフラグ。
        project_selector_combo (QComboBox): プロジェクト選択用コンボボックス。
        system_prompt_input_main (QTextEdit): メインシステムプロンプト入力エリア。
        response_display (QTextBrowser): AI応答履歴表示エリア。
        user_input (QTextEdit): ユーザーメッセージ入力エリア。
        send_button (QPushButton): メッセージ送信ボタン。
        settings_button (QPushButton): 設定ダイアログを開くボタン。
        subprompt_tab_widget (QTabWidget): サブプロンプトカテゴリ表示用タブ。
        data_management_widget (DataManagementWidget): データ管理エリア用ウィジェット。
    """

    def __init__(self):
        """MainWindowのコンストラクタ。UIの初期化とプロジェクトデータの読み込みを行います。"""
        super().__init__()
        self.global_config: dict = {}
        """dict: `data/config.json` から読み込まれたグローバル設定。"""
        self.current_project_dir_name: str = "default_project" # フォールバック値
        """str: 現在アクティブなプロジェクトのディレクトリ名。"""
        self.current_project_settings: dict = {}
        """dict: 現在アクティブなプロジェクトの `project_settings.json` の内容。"""
        self.subprompts: dict = {}
        """dict: 現在アクティブなプロジェクトの `subprompts.json` の内容。
        {カテゴリ名: {サブプロンプト名: {"prompt": ..., "model": ...}}} の形式。
        """
        self.checked_subprompts: dict[str, set[str]] = {}
        """dict[str, set[str]]: {カテゴリ名: {チェックされたサブプロンプト名のセット}}。"""
        self.gemini_configured: bool = False
        """bool: Gemini APIが正しく設定されていれば True。"""
        # --- ★★★ プロジェクト選択コンボボックス用のプロジェクト情報リスト ★★★ ---
        self._projects_list_for_combo: list[tuple[str, str]] = [] # (表示名, ディレクトリ名) のタプルのリスト
        # -------------------------------------------------------------------

        self._initialize_configs_and_project() # 設定とプロジェクトデータを初期化
        self.init_ui()                        # UIを構築
        self.configure_gemini()               # Gemini APIクライアントを設定

    def _initialize_configs_and_project(self):
        """グローバル設定を読み込み、アクティブなプロジェクトのデータをロードします。"""
        print("--- MainWindow: Initializing configurations and project data ---")
        self.global_config = load_global_config()
        self.current_project_dir_name = self.global_config.get("active_project", "default_project")
        print(f"  Active project directory name from global config: '{self.current_project_dir_name}'")
        self._load_current_project_data() # 実際のデータ読み込み

    def _load_current_project_data(self):
        """現在アクティブなプロジェクトの各種設定・データを読み込み、UI要素も更新します。

        `self.current_project_settings`, `self.subprompts` を更新し、
        ウィンドウタイトル、メインシステムプロンプト表示などを更新します。
        `DataManagementWidget` のプロジェクトも設定します（UI初期化後）。
        """
        print(f"--- MainWindow: Loading data for project: '{self.current_project_dir_name}' ---")
        project_settings_loaded = load_project_settings(self.current_project_dir_name)
        if project_settings_loaded is None: # 読み込み/作成失敗
            print(f"  FATAL: Failed to load or initialize project settings for '{self.current_project_dir_name}'. Using fallback.")
            self.current_project_settings = DEFAULT_PROJECT_SETTINGS.copy()
            self.current_project_settings["project_display_name"] = f"{self.current_project_dir_name} (読込エラー)"
        else:
            self.current_project_settings = project_settings_loaded
        
        project_display_name_for_title = self.current_project_settings.get("project_display_name", self.current_project_dir_name)
        self.setWindowTitle(f"TRPG AI Tool - {project_display_name_for_title}")
        print(f"  Project settings loaded: Name='{project_display_name_for_title}', Model='{self.current_project_settings.get('model')}'")

        self.subprompts = load_subprompts(self.current_project_dir_name)
        # チェック状態はプロジェクトごとに初期化 (カテゴリが存在すれば空セット、なければキー自体なし)
        self.checked_subprompts = {
            cat: self.checked_subprompts.get(cat, set()) for cat in self.subprompts.keys()
        }
        print(f"  Subprompts loaded: {len(self.subprompts)} categories.")

        # UI要素が既に初期化されていれば、内容を反映
        if hasattr(self, 'system_prompt_input_main'):
            self.system_prompt_input_main.setPlainText(
                self.current_project_settings.get("main_system_prompt", "")
            )
        
        # --- ★★★ DataManagementWidget のプロジェクトも設定（UI初期化後） ★★★ ---
        if hasattr(self, 'data_management_widget') and self.data_management_widget:
            self.data_management_widget.set_project(self.current_project_dir_name)
        # --------------------------------------------------------------------

        # --- ★★★ サブプロンプトタブもUIがあれば更新 ★★★ ---
        if hasattr(self, 'subprompt_tab_widget'):
            self.refresh_subprompt_tabs()
        # -------------------------------------------------

    def init_ui(self):
        """メインウィンドウのユーザーインターフェースを構築します。"""
        self.setWindowTitle(f"TRPG AI Tool - 初期化中...") # _load_current_project_dataで更新される
        self.setGeometry(200, 200, 1300, 850) # ウィンドウサイズを少し調整

        main_layout = QHBoxLayout(self)

        # --- 左側エリア (メインプロンプト、AI応答履歴、ユーザー入力) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_layout.addWidget(QLabel("メインシステムプロンプト:"))
        self.system_prompt_input_main = QTextEdit()
        self.system_prompt_input_main.setPlaceholderText("AIへの全体的な指示を入力...")
        self.system_prompt_input_main.setMinimumHeight(100) # 最小高さを設定
        self.system_prompt_input_main.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # 高さは固定
        left_layout.addWidget(self.system_prompt_input_main)

        left_layout.addWidget(QLabel("AI応答履歴:"))
        self.response_display = QTextBrowser()
        self.response_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.response_display)

        input_area_layout = QHBoxLayout()
        self.user_input = QTextEdit()
        self.user_input.setPlaceholderText("ここにメッセージを入力...")
        self.user_input.setFixedHeight(100)
        input_area_layout.addWidget(self.user_input)
        send_button_layout = QVBoxLayout()
        self.send_button = QPushButton("送信")
        self.send_button.clicked.connect(self.on_send_button_clicked)
        self.send_button.setFixedHeight(self.user_input.height()) # 入力欄の高さに合わせる
        send_button_layout.addWidget(self.send_button)
        input_area_layout.addLayout(send_button_layout)
        left_layout.addLayout(input_area_layout)


        # --- 右側エリア (設定ボタン、サブプロンプト、データ管理) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # --- ★★★ 右上: プロジェクト選択と設定ボタンのレイアウト ★★★ ---
        top_controls_layout = QHBoxLayout()
        top_controls_layout.addWidget(QLabel("プロジェクト:"))
        self.project_selector_combo = QComboBox()
        self.project_selector_combo.setToolTip("アクティブなプロジェクトを切り替えます。")
        self.project_selector_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.project_selector_combo.activated[str].connect(self._on_project_selected_by_display_name) # 表示名で選択されたとき
        top_controls_layout.addWidget(self.project_selector_combo, 1) # 伸縮比率1

        self.settings_button = QPushButton("設定")
        self.settings_button.setToolTip("アプリケーション全体と現在のプロジェクトの設定を行います。")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        top_controls_layout.addWidget(self.settings_button)
        right_layout.addLayout(top_controls_layout)
        # -------------------------------------------------------------

        # 右側を上下に分割するスプリッター
        right_splitter = QSplitter(Qt.Vertical)

        # 上部: サブシステムプロンプトエリア
        subprompt_area_widget = QWidget()
        subprompt_area_layout = QVBoxLayout(subprompt_area_widget)
        subprompt_controls_layout = QHBoxLayout()
        subprompt_controls_layout.addWidget(QLabel("サブシステムプロンプト:"))
        subprompt_controls_layout.addStretch()
        self.add_subprompt_category_button = QPushButton("カテゴリ追加")
        self.add_subprompt_category_button.setToolTip("サブプロンプトの新しいカテゴリを作成します。")
        self.add_subprompt_category_button.clicked.connect(self.add_subprompt_category)
        subprompt_controls_layout.addWidget(self.add_subprompt_category_button)
        self.add_subprompt_button = QPushButton("プロンプト追加")
        self.add_subprompt_button.setToolTip("現在のカテゴリに新しいサブプロンプトを追加します。")
        self.add_subprompt_button.clicked.connect(lambda: self.add_or_edit_subprompt()) # 引数なしで呼び出し
        subprompt_controls_layout.addWidget(self.add_subprompt_button)
        subprompt_area_layout.addLayout(subprompt_controls_layout)

        self.subprompt_tab_widget = QTabWidget()
        self.subprompt_tab_widget.currentChanged.connect(self._on_subprompt_tab_changed)
        # self.subprompt_lists は refresh_subprompt_tabs で管理される
        subprompt_area_layout.addWidget(self.subprompt_tab_widget)
        right_splitter.addWidget(subprompt_area_widget)

        # 下部: データ管理エリア
        self.data_management_widget = DataManagementWidget(
            project_dir_name=self.current_project_dir_name,
            parent=self # DataManagementWidgetがMainWindowを参照できるように
        )
        # DataManagementWidgetからのシグナルを接続
        self.data_management_widget.addCategoryRequested.connect(self._handle_add_data_category_request)
        self.data_management_widget.addItemRequested.connect(self._handle_add_data_item_request)
        right_splitter.addWidget(self.data_management_widget)
        right_splitter.setSizes([int(self.height() * 0.4), int(self.height() * 0.6)]) # 分割比率を調整

        right_layout.addWidget(right_splitter)


        main_layout.addWidget(left_widget, 7)
        main_layout.addWidget(right_widget, 3)

        # --- ★★★ UI初期化後にプロジェクトコンボボックスを初期化・設定 ★★★ ---
        self._populate_project_selector()
        # -----------------------------------------------------------------

        self._load_current_project_data() # UI部品構築後に再度呼び出し、データ連携
        # refresh_subprompt_tabs は _load_current_project_data 内で呼ばれるように変更

    # --- ★★★ プロジェクト選択関連メソッド ★★★ ---
    def _populate_project_selector(self):
        """プロジェクト選択用コンボボックスに、利用可能なプロジェクトの一覧を設定します。

        `data/` ディレクトリをスキャンし、各プロジェクトの表示名とディレクトリ名を
        コンボボックスに登録します。現在アクティブなプロジェクトが選択された状態にします。
        """
        self.project_selector_combo.blockSignals(True) # 更新中のシグナル発行を抑制
        self.project_selector_combo.clear()
        self._projects_list_for_combo.clear()

        project_dir_names = list_project_dir_names()
        print(f"  Populating project selector. Found project dirs: {project_dir_names}")

        current_project_found_in_list = False
        for dir_name in project_dir_names:
            settings = load_project_settings(dir_name) # 表示名を取得するため設定をロード
            display_name = dir_name # フォールバック
            if settings and settings.get("project_display_name"):
                display_name = settings.get("project_display_name")
            
            self._projects_list_for_combo.append((display_name, dir_name))
            self.project_selector_combo.addItem(display_name) # コンボボックスには表示名を追加
            if dir_name == self.current_project_dir_name:
                self.project_selector_combo.setCurrentText(display_name)
                current_project_found_in_list = True
                print(f"    Set current project in combo: '{display_name}' (dir: '{dir_name}')")

        if not current_project_found_in_list and project_dir_names:
            # 現在のプロジェクトがリストにないが、他のプロジェクトはある場合
            # (例: config.jsonのactive_projectが不正だった場合など)
            # リストの最初のプロジェクトをアクティブにする
            print(f"  Warning: Current project '{self.current_project_dir_name}' not in valid list. Selecting first available.")
            if self._projects_list_for_combo:
                first_proj_display_name, first_proj_dir_name = self._projects_list_for_combo[0]
                self.project_selector_combo.setCurrentText(first_proj_display_name)
                # ここで実際にプロジェクトを切り替える処理を呼ぶ（_on_project_selected_by_display_name を直接呼ぶか、共通処理を切り出す）
                self._switch_project(first_proj_dir_name) # プロジェクト切り替え実行

        elif not project_dir_names: # プロジェクトが一つもない場合
             print("  No projects found to populate selector.")
             # ここで「プロジェクトなし」のような項目を追加したり、新規作成を促すUIを出すことも可能
             self.project_selector_combo.addItem("(プロジェクトがありません)")
             self.project_selector_combo.setEnabled(False) # 選択不可に

        self.project_selector_combo.blockSignals(False) # シグナル発行を再開

    def _on_project_selected_by_display_name(self, selected_display_name: str):
        """プロジェクト選択コンボボックスで表示名によってプロジェクトが選択された際のスロット。

        選択された表示名に対応するディレクトリ名を見つけ、プロジェクトを切り替えます。

        Args:
            selected_display_name (str): コンボボックスで選択されたプロジェクトの表示名。
        """
        print(f"--- MainWindow: Project selected by display name: '{selected_display_name}' ---")
        selected_dir_name = None
        for display_name, dir_name in self._projects_list_for_combo:
            if display_name == selected_display_name:
                selected_dir_name = dir_name
                break
        
        if selected_dir_name and selected_dir_name != self.current_project_dir_name:
            self._switch_project(selected_dir_name)
        elif not selected_dir_name:
            print(f"  Error: Could not find directory name for display name '{selected_display_name}'.")
            # 念のためコンボボックスを再描画
            self._populate_project_selector()


    def _switch_project(self, new_project_dir_name: str):
        """指定されたディレクトリ名のプロジェクトに実際に切り替える内部メソッド。

        関連する設定の更新、データの再読み込み、UIの更新を行います。

        Args:
            new_project_dir_name (str): 切り替え先のプロジェクトのディレクトリ名。
        """
        print(f"--- MainWindow: Switching project to '{new_project_dir_name}' ---")
        self.current_project_dir_name = new_project_dir_name
        
        # グローバル設定のアクティブプロジェクトを更新・保存
        self.global_config["active_project"] = self.current_project_dir_name
        if not save_global_config(self.global_config):
            QMessageBox.warning(self, "保存エラー", "アクティブプロジェクトの変更の保存に失敗しました。")
            # ここで元のプロジェクトに戻すなどの処理も検討できる
            return

        self._load_current_project_data() # 新しいプロジェクトのデータをロードし、UI部品も更新
        # _load_current_project_data内でDataManagementWidgetのset_projectとrefresh_subprompt_tabsが呼ばれる

        # コンボボックスの選択状態も（もし必要なら）再確認・設定
        # 通常は_on_project_selected_by_display_nameから呼ばれるので不要だが、直接呼ばれた場合のため
        current_display_name_in_combo = ""
        for disp_name, dir_name_map in self._projects_list_for_combo:
            if dir_name_map == self.current_project_dir_name:
                current_display_name_in_combo = disp_name
                break
        if self.project_selector_combo.currentText() != current_display_name_in_combo and current_display_name_in_combo:
            self.project_selector_combo.blockSignals(True)
            self.project_selector_combo.setCurrentText(current_display_name_in_combo)
            self.project_selector_combo.blockSignals(False)

        print(f"--- MainWindow: Project switched successfully to '{new_project_dir_name}' ---")
    # ---------------------------------------------

    # (configure_gemini, open_settings_dialog, on_send_button_clicked,
    #  サブプロンプト関連メソッド, データ管理ウィジェット連携メソッド, closeEvent
    #  のDocstringsとコードは前回のままで変更なしのため、ここでは省略します)
    # ... configure_gemini ...
    # ... open_settings_dialog ...
    # ... on_send_button_clicked ...
    # ... refresh_subprompt_tabs ...
    # ... _on_subprompt_tab_changed ...
    # ... _handle_subprompt_check_change ...
    # ... add_subprompt_category ...
    # ... add_or_edit_subprompt ...
    # ... delete_subprompt ...
    # ... _handle_add_data_category_request ...
    # ... _handle_add_data_item_request ...
    # ... closeEvent ...

    # --- 省略したメソッドのDocstringsとシグネチャのみ再掲（内容は前回と同じ） ---
    def configure_gemini(self):
        """Gemini APIクライアントを設定します。OS資格情報からAPIキーを取得します。"""
        api_key_from_os = get_os_api_key()
        if api_key_from_os:
            success, message = configure_gemini_api(api_key_from_os)
            if success:
                print(f"Gemini API設定完了 (Project Model: {self.current_project_settings.get('model')})")
                self.gemini_configured = True
            else:
                QMessageBox.warning(self, "API設定エラー", f"Gemini APIクライアントの設定に失敗しました:\n{message}")
                self.gemini_configured = False
        else:
            # 初回起動時などに表示されるメッセージ
            QMessageBox.information(self, "APIキー未設定",
                                    "Gemini APIキーがOSの資格情報に保存されていません。\n"
                                    "「設定」メニューからAPIキーを保存してください。")
            self.gemini_configured = False

    def open_settings_dialog(self):
        """設定ダイアログを開き、結果を適用します。"""
        dialog = SettingsDialog(self.global_config, self.current_project_settings, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            updated_g_conf, updated_p_conf = dialog.get_updated_configs()

            if self.global_config != updated_g_conf:
                self.global_config = updated_g_conf
                save_global_config(self.global_config)
                print("グローバル設定が更新・保存されました。")

            if self.current_project_settings != updated_p_conf:
                self.current_project_settings = updated_p_conf
                save_project_settings(self.current_project_dir_name, self.current_project_settings)
                print(f"プロジェクト '{self.current_project_dir_name}' の設定が更新・保存されました。")
            self.system_prompt_input_main.setPlainText(self.current_project_settings.get("main_system_prompt", ""))
            display_name = self.current_project_settings.get("project_display_name", self.current_project_dir_name)
            self.setWindowTitle(f"TRPG AI Tool - {display_name}")
            self.configure_gemini()
            print("設定ダイアログの変更が適用されました。")

    def on_send_button_clicked(self):
        """「送信」ボタンがクリックされたときの処理。AIに応答を要求します。"""
        if not self.gemini_configured:
            QMessageBox.warning(self, "API未設定", "Gemini APIが設定されていません。「設定」からAPIキーを入力してください。")
            return

        user_text = self.user_input.toPlainText().strip()
        if not user_text:
            QMessageBox.information(self, "入力なし", "送信するメッセージを入力してください。")
            return
        # ユーザーの入力もHTML形式で改行を<br>に置換して表示
        formatted_user_text = user_text.replace("\n", "<br>")
        self.response_display.append(f"<div style='color: blue;'><b>あなた:</b><br>{formatted_user_text}</div><br>")

        self.user_input.clear()
        QApplication.processEvents() # UIの応答性を維持

        # --- プロンプト構築 ---
        final_prompt_parts = []
        # 1. メインシステムプロンプト
        main_system_prompt_text = self.current_project_settings.get("main_system_prompt", "").strip()
        if main_system_prompt_text:
            final_prompt_parts.append(f"## システム指示\n{main_system_prompt_text}")

        # 2. 選択されたサブプロンプト
        active_subprompts_for_prompt = []
        subprompt_models_used = [] # 使用されたサブプロンプトのモデル名を収集
        for category, checked_names in self.checked_subprompts.items():
            if category in self.subprompts:
                for name in checked_names:
                    if name in self.subprompts[category]:
                        sub_data = self.subprompts[category][name]
                        prompt_content = sub_data.get("prompt", "")
                        sub_model = sub_data.get("model", "")
                        if sub_model: subprompt_models_used.append(sub_model)
                        if prompt_content:
                            active_subprompts_for_prompt.append(
                                f"### サブプロンプト: {category} - {name}\n{prompt_content}"
                            )
        if active_subprompts_for_prompt:
            final_prompt_parts.append("\n## 選択された補助指示\n" + "\n\n".join(active_subprompts_for_prompt))

        # 3. 選択されたデータアイテムの情報
        checked_data_for_prompt = []
        checked_data_from_widget = self.data_management_widget.get_checked_items()
        for category, item_ids in checked_data_from_widget.items():
            for item_id in item_ids:
                item_detail = get_item(self.current_project_dir_name, category, item_id)
                if item_detail:
                    info_str = f"### データ参照: {category} - {item_detail.get('name', 'N/A')}\n"
                    info_str += f"  - 名前: {item_detail.get('name', 'N/A')}\n"
                    info_str += f"  - 説明/メモ: {item_detail.get('description', '')}\n"
                    tags = item_detail.get('tags', [])
                    if tags: info_str += f"  - タグ: {', '.join(tags)}\n"
                    # 履歴も追加するかは検討 (長くなる可能性)
                    # history = item_detail.get('history', [])
                    # if history: info_str += f"  - 履歴 (抜粋): {history[-1]['entry'] if history else ''}\n" # 最新の履歴など
                    checked_data_for_prompt.append(info_str)
        if checked_data_for_prompt:
            final_prompt_parts.append("\n## 参照データ\n" + "\n".join(checked_data_for_prompt))

        # 4. ユーザーの入力
        final_prompt_parts.append(f"\n## ユーザーの現在の入力\n{user_text}")
        final_prompt_to_ai = "\n\n".join(final_prompt_parts).strip()

        print("--- Final Prompt to AI ---")
        print(final_prompt_to_ai) # デバッグ用にコンソールへ出力
        print("--------------------------")

        # AIに送信するモデルの決定
        target_model = self.current_project_settings.get("model", self.global_config.get("default_model"))
        if subprompt_models_used: # サブプロンプトにモデル指定があれば、最初のものを優先
            target_model = subprompt_models_used[0]
            print(f"  (Using model from subprompt: {target_model})")
        else:
            print(f"  (Using project/global model: {target_model})")

        ai_response_text, error_message = generate_response(target_model, final_prompt_to_ai)

        if error_message:
            self.response_display.append(f"<div style='color: red;'><b>エラー:</b> {error_message}</div><br>")
        elif ai_response_text:
            # AIの応答もHTML形式で改行を<br>に置換
            formatted_ai_response = ai_response_text.replace("\n", "<br>")
            self.response_display.append(f"<div style='color: green;'><b>Gemini ({target_model}):</b><br>{formatted_ai_response}</div><br>")
        else:
            self.response_display.append("<div style='color: orange;'><b>AIからの応答がありませんでした。</b></div><br>")

    # --- サブプロンプト管理メソッド ---
    def refresh_subprompt_tabs(self):
        """サブプロンプトタブウィジェットの内容を現在のプロジェクトデータに基づいて再構築します。"""
        current_tab_text_before_refresh = None
        current_tab_idx = self.subprompt_tab_widget.currentIndex()
        if current_tab_idx != -1:
             current_tab_text_before_refresh = self.subprompt_tab_widget.tabText(current_tab_idx)

        self.subprompt_tab_widget.clear() # 既存のタブを全て削除
        # self.subprompt_lists は廃止 (SubPromptItemWidget が直接リストに追加される)

        categories_in_subprompts = sorted(self.subprompts.keys())
        if not categories_in_subprompts: # サブプロンプトデータが空またはカテゴリがない場合
             if "一般" not in self.subprompts: # デフォルトカテゴリ "一般" がメモリ上にもなければ作成
                  self.subprompts["一般"] = {}
                  categories_in_subprompts.append("一般")
                  if save_subprompts(self.current_project_dir_name, self.subprompts): # ファイルにも保存
                       print(f"プロジェクト '{self.current_project_dir_name}' にデフォルトカテゴリ'一般'(サブプロンプト)を作成・保存しました。")

        # チェック状態辞書の整合性を取る (存在しないカテゴリのエントリを削除)
        self.checked_subprompts = {
            cat: checked_names for cat, checked_names in self.checked_subprompts.items()
            if cat in categories_in_subprompts
        }

        new_selected_tab_index = -1
        for i, category_name in enumerate(categories_in_subprompts):
            list_widget_for_category = QListWidget()
            list_widget_for_category.setObjectName(f"subpromptList_{category_name}") # デバッグ用
            
            checked_names_in_this_category = self.checked_subprompts.get(category_name, set())
            subprompt_names_in_this_category = sorted(self.subprompts.get(category_name, {}).keys())

            for sub_name in subprompt_names_in_this_category:
                is_item_checked = sub_name in checked_names_in_this_category
                item_container = QListWidgetItem(list_widget_for_category)
                widget_for_item = SubPromptItemWidget(sub_name, is_item_checked)
                # シグナル接続
                widget_for_item.checkStateChanged.connect(
                    lambda checked_state, current_cat=category_name, current_s_name=sub_name:
                        self._handle_subprompt_check_change(current_cat, current_s_name, checked_state)
                )
                widget_for_item.editRequested.connect(
                    lambda current_cat=category_name, current_s_name=sub_name:
                        self.add_or_edit_subprompt(current_cat, current_s_name)
                )
                widget_for_item.deleteRequested.connect(
                    lambda current_cat=category_name, current_s_name=sub_name:
                        self.delete_subprompt(current_cat, [current_s_name]) # 単一削除
                )
                item_container.setSizeHint(widget_for_item.sizeHint())
                list_widget_for_category.setItemWidget(item_container, widget_for_item)
            
            self.subprompt_tab_widget.addTab(list_widget_for_category, category_name)
            if category_name == current_tab_text_before_refresh:
                new_selected_tab_index = i
        
        if new_selected_tab_index != -1:
             self.subprompt_tab_widget.setCurrentIndex(new_selected_tab_index)
        elif self.subprompt_tab_widget.count() > 0: # 何も一致しなかったがタブはある場合
             self.subprompt_tab_widget.setCurrentIndex(0) # 最初のタブを選択

    def _on_subprompt_tab_changed(self, index: int):
        """サブプロンプトのカテゴリタブが変更されたときに呼び出されるスロット。(現在は未使用)

        Args:
            index (int): 新しく選択されたタブのインデックス。
        """
        # print(f"Subprompt tab changed to index: {index}")
        pass # 必要に応じて、タブ変更時の追加処理をここに記述

    def _handle_subprompt_check_change(self, category: str, name: str, is_checked: bool):
        """サブプロンプトアイテムのチェック状態が変更されたときの内部処理。

        `self.checked_subprompts` を更新します。

        Args:
            category (str): チェック状態が変更されたサブプロンプトのカテゴリ名。
            name (str): チェック状態が変更されたサブプロンプトの名前。
            is_checked (bool): 新しいチェック状態。
        """
        if category not in self.checked_subprompts:
            self.checked_subprompts[category] = set()
        if is_checked:
            self.checked_subprompts[category].add(name)
        else:
            self.checked_subprompts[category].discard(name)
        print(f"Subprompt check state: Category='{category}', Name='{name}', Checked={is_checked}")

    def add_subprompt_category(self):
        """「サブプロンプトカテゴリ追加」ボタンがクリックされたときの処理。"""
        category_name, ok = QInputDialog.getText(self, "サブプロンプト カテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name.strip():
            category_name = category_name.strip() # 前後の空白を除去
            if category_name not in self.subprompts:
                self.subprompts[category_name] = {} # メモリ上に新しいカテゴリ作成
                if save_subprompts(self.current_project_dir_name, self.subprompts):
                    self.refresh_subprompt_tabs() # UI更新
                    # 追加したタブを選択状態にする
                    for i in range(self.subprompt_tab_widget.count()):
                        if self.subprompt_tab_widget.tabText(i) == category_name:
                            self.subprompt_tab_widget.setCurrentIndex(i)
                            break
                else:
                    QMessageBox.warning(self, "保存エラー", f"カテゴリ '{category_name}' の保存に失敗しました。")
                    del self.subprompts[category_name] # 保存失敗時はメモリからも削除
            else:
                QMessageBox.warning(self, "エラー", f"カテゴリ名 '{category_name}' は既に存在します。")
        elif ok : # OK押したが名前が空
            QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")

    def add_or_edit_subprompt(self, category_to_edit: str | None = None, name_to_edit: str | None = None):
        """サブプロンプトの追加または編集ダイアログを開きます。

        引数なしで呼び出された場合は「追加」モード（現在のタブカテゴリ対象）。
        引数ありの場合は「編集」モード。

        Args:
            category_to_edit (str | None, optional): 編集対象のカテゴリ名。
                                                     Noneの場合は現在のタブのカテゴリ。
            name_to_edit (str | None, optional): 編集対象のサブプロンプト名。
                                                 Noneの場合は新規追加。
        """
        target_category = category_to_edit
        is_editing_mode = bool(name_to_edit) # name_to_edit があれば編集モード

        if not target_category: # カテゴリ指定がない場合は現在のタブから取得
            current_tab_index = self.subprompt_tab_widget.currentIndex()
            if current_tab_index == -1: # タブが選択されていない（またはタブがない）
                # デフォルトカテゴリ「一般」がなければ作成を試みる
                if "一般" not in self.subprompts: self.add_subprompt_category() # これが成功すればタブができるはず
                # 再度タブを確認
                current_tab_index = self.subprompt_tab_widget.currentIndex()
                if current_tab_index == -1: # それでもダメならエラー
                     QMessageBox.warning(self, "カテゴリ未選択", "サブプロンプトを追加/編集するカテゴリがありません。\nまず「カテゴリ追加」でカテゴリを作成してください。")
                     return
            target_category = self.subprompt_tab_widget.tabText(current_tab_index)

        initial_prompt_data = {"name": "", "prompt": "", "model": ""} # 新規作成時のデフォルト
        if is_editing_mode and target_category in self.subprompts and name_to_edit in self.subprompts[target_category]:
            initial_prompt_data = self.subprompts[target_category][name_to_edit].copy()
            initial_prompt_data["name"] = name_to_edit
        dialog = SubPromptEditDialog(initial_data=initial_prompt_data, parent=self, is_editing=is_editing_mode, current_category=target_category)
        if dialog.exec_() == QDialog.Accepted:
            new_sub_data = dialog.get_data()
            new_sub_name = new_sub_data.pop("name") # 名前はキーとして使用

            if not target_category in self.subprompts: # 万が一カテゴリが消えていたら(通常ありえない)
                self.subprompts[target_category] = {}

            # 編集時で名前が変更された場合、古い名前のデータを削除
            if is_editing_mode and name_to_edit != new_sub_name and name_to_edit in self.subprompts[target_category]:
                del self.subprompts[target_category][name_to_edit]
                # チェック状態も移行
                if target_category in self.checked_subprompts and name_to_edit in self.checked_subprompts[target_category]:
                    self.checked_subprompts[target_category].remove(name_to_edit)
                    self.checked_subprompts[target_category].add(new_sub_name) # 新しい名前でチェック

            self.subprompts[target_category][new_sub_name] = new_sub_data # 新しいデータで登録/上書き
            if save_subprompts(self.current_project_dir_name, self.subprompts):
                self.refresh_subprompt_tabs() # UI更新
            else:
                QMessageBox.warning(self, "保存エラー", "サブプロンプトの保存に失敗しました。")
                # TODO: 保存失敗時のロールバック処理 (メモリ上の変更を元に戻すなど)

    def delete_subprompt(self, category_name: str, names_to_delete: list[str]):
        """指定されたカテゴリから、指定された名前のサブプロンプトを削除します。

        Args:
            category_name (str): 削除対象サブプロンプトが含まれるカテゴリ名。
            names_to_delete (list[str]): 削除するサブプロンプトの名前のリスト。
        """
        if not category_name in self.subprompts: return # カテゴリ存在チェック

        deleted_something = False
        for name in names_to_delete:
            if name in self.subprompts[category_name]:
                del self.subprompts[category_name][name]
                # チェック状態からも削除
                if category_name in self.checked_subprompts and name in self.checked_subprompts[category_name]:
                    self.checked_subprompts[category_name].remove(name)
                deleted_something = True
        
        if deleted_something:
            if save_subprompts(self.current_project_dir_name, self.subprompts):
                self.refresh_subprompt_tabs() # UI更新
            else:
                QMessageBox.warning(self, "保存エラー", "サブプロンプトの削除内容の保存に失敗しました。")
                # TODO: 保存失敗時のロールバック処理

    # --- データ管理ウィジェット連携メソッド ---
    def _handle_add_data_category_request(self):
        """`DataManagementWidget`からのカテゴリ追加要求を処理します。"""
        category_name, ok = QInputDialog.getText(self, "データカテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name.strip():
            self.data_management_widget.add_new_category_result(category_name.strip())
        elif ok :
            QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")

    def _handle_add_data_item_request(self, category_from_data_widget: str):
        """`DataManagementWidget`からのアイテム追加要求を処理します。

        Args:
            category_from_data_widget (str): アイテムを追加する対象のカテゴリ名。
        """
        item_name, ok = QInputDialog.getText(self, "アイテム追加",
                                             f"カテゴリ '{category_from_data_widget}' に追加するアイテムの名前:")
        if ok and item_name.strip():
            self.data_management_widget.add_new_item_result(category_from_data_widget, item_name.strip())
        elif ok:
            QMessageBox.warning(self, "入力エラー", "アイテム名を入力してください。")

    def closeEvent(self, event):
        """ウィンドウが閉じられるときに呼び出されるイベントハンドラ。

        現在のメインシステムプロンプトをプロジェクト設定に保存します。
        """
        print("MainWindow is closing. Saving current main system prompt...")
        current_main_prompt_text = self.system_prompt_input_main.toPlainText()
        if self.current_project_settings.get("main_system_prompt") != current_main_prompt_text:
            self.current_project_settings["main_system_prompt"] = current_main_prompt_text
            if save_project_settings(self.current_project_dir_name, self.current_project_settings):
                print("  Main system prompt saved successfully on close.")
            else:
                print("  ERROR: Failed to save main system prompt on close.")
        # 詳細ウィンドウも明示的に閉じる (もし開いていれば)
        if hasattr(self, 'data_management_widget') and self.data_management_widget._detail_window:
            if self.data_management_widget._detail_window.isVisible():
                self.data_management_widget._detail_window.close()
        super().closeEvent(event)

if __name__ == '__main__':
    """MainWindowの基本的な表示・インタラクションテスト。"""
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())

