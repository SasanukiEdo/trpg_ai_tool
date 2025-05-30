# ui/detail_window.py

"""選択されたデータアイテムの詳細情報を表示・編集するためのウィンドウを提供します。

このモジュールは `DetailWindow` クラスを定義しており、アイテムの名前、説明、
履歴、タグ、画像などの属性をユーザーが確認・変更できるようにします。
AIによる説明文の編集支援機能や、AI支援による履歴追記機能、履歴の削除機能も統合されています。
"""

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QScrollArea, QFrame, QFileDialog, QMessageBox, QDialog,
    QSizePolicy, QSpacerItem, QInputDialog, QApplication, qApp
)
from PyQt5.QtGui import QPixmap, QImageReader, QResizeEvent, QShowEvent
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QTimer
from typing import Optional



# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# --- coreモジュールインポート ---
from core.data_manager import get_item, update_item, add_history_entry
from core.gemini_handler import GeminiChatHandler, is_configured as gemini_is_configured 
from core.shared_instances import get_main_window_instance 
from core.config_manager import DEFAULT_PROJECT_SETTINGS, get_category_template

# --- uiモジュールインポート ---
from ui.ai_text_edit_dialog import AIAssistedEditDialog



class DetailWindow(QWidget):
    """データアイテムの詳細情報を表示し、編集機能を提供するウィンドウクラス。

    アイテムの属性（名前、説明、履歴、タグ、画像）を表示し、
    ユーザーによる編集と保存を可能にします。
    AIによる説明文の編集支援機能や、AI支援による履歴追記機能、履歴の削除機能も提供します。

    Attributes:
        dataSaved (pyqtSignal): アイテムデータが保存されたときに発行されるシグナル。
                                 引数としてカテゴリ名(str)とアイテムID(str)を渡します。
        windowClosed (pyqtSignal): この詳細ウィンドウが閉じられたときに発行されるシグナル。
        current_project_dir_name (str | None): 現在操作対象のプロジェクトディレクトリ名。
        current_category (str | None): 現在表示しているアイテムのカテゴリ名。
        current_item_id (str | None): 現在表示しているアイテムのID。
        item_data (dict | None): 現在表示・編集中アイテムの全データ。
        detail_widgets (dict): 各データフィールドに対応するUIウィジェットを格納する辞書。
                               キーはフィールド名 (例: 'name', 'description')。
        ai_edit_dialog (AIAssistedEditDialog | None): AI編集支援ダイアログのインスタンス。
        ai_edit_dialog_mode (str | None): AI編集支援ダイアログが現在どのモード('description' または 'history')で使用されているかを示す。
    """
    dataSaved = pyqtSignal(str, str)
    """pyqtSignal: データが正常に保存された後に発行されます。

    Args:
        category (str): 保存されたアイテムのカテゴリ名。
        item_id (str): 保存されたアイテムのID。
    """
    windowClosed = pyqtSignal()
    """pyqtSignal: ウィンドウが閉じられる際に発行されます。"""

    def __init__(self,
                 main_config: dict | None = None,
                 project_dir_name: str | None = None,
                 parent: QWidget | None = None):
        """DetailWindowのコンストラクタ。

        Args:
            main_config (dict | None, optional):
                メインウィンドウから渡される設定情報（主にAIモデル名など）。
                デフォルトは None。
            project_dir_name (str | None, optional):
                現在操作対象のプロジェクトのディレクトリ名。
                アイテムデータの読み書きに必要。デフォルトは None。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
        """
        super().__init__(parent)
        self.main_config = main_config if main_config is not None else {}
        """dict: メインウィンドウから渡される設定情報。"""
        self.current_project_dir_name = project_dir_name
        """str | None: 現在操作対象のプロジェクトディレクトリ名。"""
        self.current_category: str | None = None
        """str | None: 現在表示しているアイテムのカテゴリ名。load_data()で設定される。"""
        self.current_item_id: str | None = None
        """str | None: 現在表示しているアイテムのID。load_data()で設定される。"""
        self.item_data: dict | None = None
        """dict | None: 現在表示・編集中アイテムの全データ。load_data()で設定される。"""

        self.detail_widgets: dict[str, QWidget] = {} # UIウィジェットを保持
        """dict: 表示/編集フィールド名とそのUIウィジェットのマッピング。"""
        self.ai_edit_dialog: AIAssistedEditDialog | None = None
        self.ai_edit_dialog_mode: str | None = None # ★ AI編集ダイアログのモード
        """str | None: AI編集支援ダイアログが何の編集に使われているか ('description' or 'history')"""

        self._original_image_pixmap: QPixmap | None = None
        """QPixmap | None: 読み込んだ画像のスケーリングされていないオリジナルピクスマップ。"""

        self.setWindowFlags(Qt.Window) # 独立したウィンドウとして表示
        self.setWindowTitle("詳細情報 (アイテム未選択)")
        self.setMinimumWidth(450)
        self.setMinimumHeight(600) # 高さを確保

        self.init_ui()

    def init_ui(self):
        """UI要素を初期化し、レイアウトを設定します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize) # または QLayout.SetMinimumSize

        # スクロールエリアのセットアップ
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # 横スクロールバーは常にオフ
        main_layout.addWidget(scroll_area)

        self.scroll_content_widget = QWidget() # スクロールされる中身のウィジェット
        self.content_layout = QVBoxLayout(self.scroll_content_widget)
        self.content_layout.setAlignment(Qt.AlignTop) # ウィジェットを上寄せ
        self.content_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize) # または QLayout.SetMinimumSize
        scroll_area.setWidget(self.scroll_content_widget)

        # --- 各詳細フィールドのプレースホルダー ---
        # (load_dataが呼ばれるまで空か、ローディング表示)
        self.content_layout.addWidget(QLabel("アイテムを選択すると詳細が表示されます。"))

        # --- 保存ボタン ---
        self.save_button = QPushButton("変更を保存")
        self.save_button.clicked.connect(self.save_details)
        self.save_button.setEnabled(False) # 初期状態は無効 (データロード後に有効化)
        main_layout.addWidget(self.save_button)

    def load_data(self, category: str, item_id: str):
        """指定されたカテゴリとIDのアイテムデータを読み込み、UIに表示します。

        Args:
            category (str): 読み込むアイテムのカテゴリ名。
            item_id (str): 読み込むアイテムのID。
        """
        self.clear_view() # 表示をクリア

        if not self.current_project_dir_name:
            QMessageBox.critical(self, "プロジェクトエラー",
                                 "プロジェクトが指定されていません。アイテム詳細を読み込めません。")
            self.setWindowTitle("詳細情報 (プロジェクトエラー)")
            return

        print(f"DetailWindow: Loading data for Project='{self.current_project_dir_name}', Category='{category}', ID='{item_id}'")
        item_data_loaded = get_item(self.current_project_dir_name, category, item_id)

        if not item_data_loaded:
            QMessageBox.warning(self, "データ読み込みエラー",
                                f"アイテム (ID: {item_id}, カテゴリ: {category}) のデータの読み込みに失敗しました。")
            self.setWindowTitle(f"詳細情報 (読込エラー: {item_id})")
            return

        self.current_category = category
        self.current_item_id = item_id
        self.item_data = item_data_loaded.copy() # 変更を反映させるためにコピーを保持
        print(f"DEBUG: DetailWindow.load_data - Loaded item_data: name='{self.item_data.get('name')}', description='{self.item_data.get('description')}'") # DEBUG

        self.setWindowTitle(f"詳細: {self.item_data.get('name', 'N/A')} ({category})")
        self._build_detail_view() # データに基づいてUIを構築
        self.save_button.setEnabled(True) # データロード成功で保存ボタンを有効化


    def clear_view(self):
        """現在の詳細表示エリアの内容をクリアします。"""
        # self.content_layout の中のウィジェットを全て削除
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.detail_widgets.clear()
        self.item_data = None
        self.current_category = None
        self.current_item_id = None
        self.setWindowTitle("詳細情報 (アイテム未選択)")
        self.save_button.setEnabled(False)


    def _build_detail_view(self):
        """`self.item_data` に基づいて詳細表示UIを動的に構築します。
        履歴表示に通し番号と区切り線を追加し、タイムスタンプを非表示にします。
        履歴削除ボタン、履歴編集ボタンを追加します。
        参照先タグ入力フィールドも追加します。
        """
        if not self.item_data: return

        # 名前
        name_label = QLabel("<b>名前:</b>"); name_edit = QLineEdit(self.item_data.get("name", "")); self.detail_widgets['name'] = name_edit; self.content_layout.addWidget(name_label); self.content_layout.addWidget(name_edit)

        # 説明/メモ
        desc_label = QLabel("<b>説明/メモ:</b>")
        desc_edit = QTextEdit() # まずインスタンスを作成
        desc_edit.setPlainText(self.item_data.get("description", "")) # setPlainText で設定
        desc_edit.setMinimumHeight(150)
        desc_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.detail_widgets['description'] = desc_edit
        self.content_layout.addWidget(desc_label)
        self.content_layout.addWidget(desc_edit)

        ai_update_button = QPushButton("AIで「説明/メモ」を編集支援"); ai_update_button.clicked.connect(self._on_ai_update_description_clicked); self.content_layout.addWidget(ai_update_button)

        # 履歴
        history_label = QLabel("<b>履歴:</b>")
        self.content_layout.addWidget(history_label) # ラベルを先に追加

        history_view_container = QWidget() # 履歴表示とボタンをまとめるコンテナ
        history_view_layout = QVBoxLayout(history_view_container)
        history_view_layout.setContentsMargins(0,0,0,0)

        self.history_view_text_edit = QTextEdit() # QTextEditはメンバ変数に
        self.history_view_text_edit.setReadOnly(True)
        history_entries = self.item_data.get("history", [])
        history_display_html = ""
        if not history_entries:
            history_display_html = "履歴はありません。"
        else:
            for i, h_entry_dict in enumerate(history_entries):
                entry_text_for_display = h_entry_dict.get('entry', '(内容なし)')
                # タイムスタンプは表示しない、代わりに通し番号を表示
                # formatted_entry_text = entry_text_for_display.replace("\n", "<br>") # 修正前コメントアウト
                # 1. 半角スペースを &nbsp; に置換
                temp_text = entry_text_for_display.replace(" ", "&nbsp;")
                # 2. 改行を <br> に置換
                formatted_entry_text = temp_text.replace("\n", "<br>") # ★★★ 修正箇所 ★★★
                history_display_html += f"<b>({i + 1})</b> {formatted_entry_text}"
                if i < len(history_entries) - 1: # 最後の要素以外には区切り線
                    history_display_html += "<hr>" # 区切り線
        self.history_view_text_edit.setHtml(history_display_html) # HTMLとしてセット
        self.history_view_text_edit.setMinimumHeight(100) # 高さを調整
        self.detail_widgets['history_view'] = self.history_view_text_edit # 保存対象外
        history_view_layout.addWidget(self.history_view_text_edit)

        history_buttons_layout = QHBoxLayout()
        add_history_button = QPushButton("AIで履歴エントリを生成・追加")
        add_history_button.setToolTip("AIの支援を受けて新しい履歴エントリを作成し、追加します。")
        add_history_button.clicked.connect(self.add_history_entry_with_ai_ui)
        history_buttons_layout.addWidget(add_history_button)

        edit_history_button = QPushButton("履歴を編集")
        edit_history_button.setToolTip("指定した番号の履歴エントリを編集します。")
        edit_history_button.clicked.connect(self.edit_history_entry_ui) # 新しいメソッドに接続
        history_buttons_layout.addWidget(edit_history_button)

        delete_history_button = QPushButton("履歴を削除")
        delete_history_button.setToolTip("指定した番号の履歴エントリを削除します。")
        delete_history_button.clicked.connect(self.delete_history_entry_ui)
        history_buttons_layout.addWidget(delete_history_button)
        history_buttons_layout.addStretch()
        history_view_layout.addLayout(history_buttons_layout)
        self.content_layout.addWidget(history_view_container)

        # タグ (既存のアイテム自身のタグ)
        tags_label = QLabel("<b>タグ</b> (カンマ区切り):")
        tags_edit = QLineEdit(", ".join(self.item_data.get("tags", [])))
        self.detail_widgets['tags'] = tags_edit
        self.content_layout.addWidget(tags_label)
        self.content_layout.addWidget(tags_edit)

        # --- ★★★ 参照先タグ入力フィールドを追加 (アイテム用) ★★★ ---
        ref_tags_label = QLabel("<b>参照先タグ</b> (カンマ区切り、プロンプト連携用):")
        ref_tags_edit = QLineEdit(", ".join(self.item_data.get("reference_tags", []))) # 新しいキー
        ref_tags_edit.setPlaceholderText("例: ギルド職員, 魔法武器")
        self.detail_widgets['reference_tags'] = ref_tags_edit # detail_widgets に登録
        self.content_layout.addWidget(ref_tags_label)
        self.content_layout.addWidget(ref_tags_edit)
        # --- ★★★ ------------------------------------------ ★★★ ---

        # 画像
        self.img_path_label = QLabel("<b>画像:</b> (選択されていません)")
        self.img_path_label.setWordWrap(True)
        self.detail_widgets['image_path_display'] = self.img_path_label
        self.content_layout.addWidget(self.img_path_label)

        self.img_preview_label = QLabel()
        self.img_preview_label.setAlignment(Qt.AlignCenter)
        self.img_preview_label.setMinimumSize(200, 150)
        self.img_preview_label.setFrameShape(QFrame.StyledPanel)
        self.img_preview_label.setScaledContents(True)
        self.img_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.detail_widgets['image_preview'] = self.img_preview_label
        self._update_image_preview(self.item_data.get("image_path"))
        self.content_layout.addWidget(self.img_preview_label)

        img_buttons_layout = QHBoxLayout()
        select_img_button = QPushButton("画像を選択")
        select_img_button.clicked.connect(self.select_image_file)
        img_buttons_layout.addWidget(select_img_button)
        clear_img_button = QPushButton("画像をクリア")
        clear_img_button.clicked.connect(self.clear_image_file)
        img_buttons_layout.addWidget(clear_img_button)
        img_buttons_layout.addStretch()
        self.content_layout.addLayout(img_buttons_layout)
        

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding); self.content_layout.addSpacerItem(spacer)

    def _on_ai_update_description_clicked(self):
        """「AIで説明/メモを編集」ボタンがクリックされたときの処理。"""
        print(f"DEBUG: _on_ai_update_description_clicked - current_item_id: {self.current_item_id}") # DEBUG
        if self.item_data: # DEBUG
            print(f"DEBUG: _on_ai_update_description_clicked - item_data: name='{self.item_data.get('name')}', desc_len={len(self.item_data.get('description', ''))}") # DEBUG
        else: # DEBUG
            print("DEBUG: _on_ai_update_description_clicked - self.item_data is None") # DEBUG

        if not self.item_data or not self.current_project_dir_name or not self.current_category:
            QMessageBox.warning(self, "AI編集エラー", "アイテムデータがロードされていません。")
            return

        # current_text を self.item_data から直接取得するように変更
        current_text = self.item_data.get("description", "") 
        item_name = self.item_data.get("name", "不明なアイテム")
        # print(f"DEBUG: current_text for branching: '{current_text}'") # このデバッグは item_data ベースになる

        # プロジェクト設定からAI編集支援プロンプトを取得
        from core.config_manager import load_project_settings # 動的に読み込む
        project_settings = load_project_settings(self.current_project_dir_name)
        if not project_settings:
            QMessageBox.warning(self, "設定エラー", "プロジェクト設定を読み込めませんでした。")
            return

        ai_prompts = project_settings.get("ai_edit_prompts", DEFAULT_PROJECT_SETTINGS.get("ai_edit_prompts", {}))
        empty_template_full_text = project_settings.get("empty_description_template", DEFAULT_PROJECT_SETTINGS.get("empty_description_template", ""))

        if not current_text.strip(): # 説明が空の場合 (新規作成モード)
            prompt_template_str = ai_prompts.get("description_new", "")
            print(f"DEBUG: description_new template: {prompt_template_str}") # DEBUG
            # カテゴリに応じた雛形テンプレートを取得
            category_specific_empty_template = get_category_template(self.current_category, empty_template_full_text)
            print(f"DEBUG: category_specific_empty_template for '{self.current_category}': {category_specific_empty_template}") # DEBUG
            if not category_specific_empty_template:
                 # カテゴリ別テンプレートがない場合、デフォルトの全体を使用
                category_specific_empty_template = empty_template_full_text 
            
            # プレースホルダを実際の値で置換
            # description_new の {empty_description_template} を category_specific_empty_template で置換
            if "{empty_description_template}" in prompt_template_str:
                prompt_template_str = prompt_template_str.replace("{empty_description_template}", category_specific_empty_template)
            else: # description_new に雛形テンプレートのプレースホルダがない場合、直接雛形を使う (フォールバック)
                print("警告: description_new プロンプトに {empty_description_template} プレースホルダがありません。empty_description_template を直接使用します。")
                prompt_template_str = category_specific_empty_template # この場合、指示プロンプトなしで雛形のみになる
            print(f"DEBUG: prompt_template_str after empty_template replacement: {prompt_template_str}") # DEBUG
            
            final_prompt = prompt_template_str.replace("{item_name}", item_name) # item_name も置換
            instruction_text = f"「{item_name}」の「説明/メモ」を新規作成してください。" # ダイアログ用の指示
            print(f"DEBUG: final_prompt (new): {final_prompt}") # DEBUG
        else: # 既存の説明がある場合 (編集モード)
            prompt_template_str = ai_prompts.get("description_edit", "")
            print(f"DEBUG: description_edit template: {prompt_template_str}") # DEBUG
            final_prompt = prompt_template_str.replace("{item_name}", item_name).replace("{current_text}", current_text)
            # instruction_text は編集モードの場合も final_prompt を使うべきか、あるいは現在のままでも良いか検討。
            # 現状はダイアログの instruction_edit に final_prompt が表示されるべきなので、instruction_text は final_prompt と同じにする。
            instruction_text = f"「{item_name}」の「説明/メモ」を編集してください。" # これはダイアログのタイトル等に使われる想定だったかもしれないが、初期テキストとしては final_prompt を使う。
            print(f"DEBUG: final_prompt (edit): {final_prompt}") # DEBUG

        if not final_prompt.strip():
            QMessageBox.warning(self, "プロンプトエラー", "AI編集用のプロンプトテンプレートが空です。設定を確認してください。")
            return

        # AI編集ダイアログを表示
        # instruction_text には実際にダイアログの編集エリアに表示させたいプロンプト(final_prompt)を渡す
        self._show_ai_edit_dialog(
            instruction_text=final_prompt, # ★★★ ここを final_prompt に変更 ★★★
            system_prompt=project_settings.get("main_system_prompt", ""),
            user_prompt_template=final_prompt, # この引数は _show_ai_edit_dialog 内では未使用だが、一旦そのまま
            target_widget=self.detail_widgets.get('description'),
            mode='description' # モードを設定
        )
        print(f"DEBUG: _on_ai_update_description_clicked - Just before calling _show_ai_edit_dialog, final_prompt length: {len(final_prompt)}") # DEBUG

    def _show_ai_edit_dialog(self, instruction_text: str, system_prompt: str, user_prompt_template: str, target_widget: QTextEdit, mode: str):
        """AI編集支援ダイアログを表示します。

        Args:
            instruction_text (str): AIに提示する指示プロンプト。
            system_prompt (str): AIに提示するシステムプロンプト。
            user_prompt_template (str): ユーザーが入力するテンプレート。
            target_widget (QTextEdit): 編集対象のテキストウィジェット。
            mode (str): AI編集ダイアログのモード ('description' または 'history')。
        """
        print(f"DEBUG: _show_ai_edit_dialog - Received instruction_text length: {len(instruction_text)}") # DEBUG

        # 既存のダイアログインスタンスがあれば、安全に破棄する
        if self.ai_edit_dialog:
            try:
                # シグナル接続が残っている可能性があるので、先に切断を試みる (必須ではないが多くの場合安全)
                self.ai_edit_dialog.request_ai_button.clicked.disconnect()
            except TypeError: # 未接続の場合 TypeError が発生する
                pass
            self.ai_edit_dialog.deleteLater() # deleteLater() で安全に破棄
            self.ai_edit_dialog = None

        # 毎回新しいダイアログインスタンスを作成する
        current_description_for_dialog = self.item_data.get("description", "") if self.item_data else ""
        self.ai_edit_dialog = AIAssistedEditDialog(
            initial_instruction_text=instruction_text,
            current_item_description=current_description_for_dialog,
            parent=self,
            window_title=f"AIで「{self.item_data.get('name', '不明なアイテム')}」を編集 ({mode})"
        )
        self.ai_edit_dialog_mode = mode # モードを設定
        
        # AI提案リクエストボタンのシグナルを接続
        # (インスタンスが毎回新しいので、毎回接続が必要)
        self.ai_edit_dialog.request_ai_button.clicked.connect(
            lambda: self._handle_ai_suggestion_request(
                self.ai_edit_dialog.get_instruction_text()
            )
        )

        # ダイアログを表示し、結果を処理
        if self.ai_edit_dialog.exec_() == QDialog.Accepted:
            final_text = self.ai_edit_dialog.get_final_text()
            if target_widget: # target_widget が None でないことを確認
                target_widget.setPlainText(final_text)
            print("AIによる説明編集が適用されました。(保存は別途必要)")
        
        # exec_() が終了したら、ダイアログインスタンスを確実に破棄する
        if self.ai_edit_dialog: # まだインスタンスへの参照が残っていれば
            self.ai_edit_dialog.deleteLater()
        self.ai_edit_dialog = None

    def _handle_ai_suggestion_request(self, instruction_text: str):
        """AIAssistedEditDialog からのAI提案リクエストを処理します。

        Args:
            instruction_text (str): AIAssistedEditDialog でユーザーが編集した指示プロンプト。
        """
        if not self.ai_edit_dialog: return
        if not gemini_is_configured():
            QMessageBox.warning(self.ai_edit_dialog, "APIキーエラー", "APIキーが未設定です。")
            return
        if not self.item_data: # アイテムデータがないとコンテキスト作れない
            QMessageBox.warning(self.ai_edit_dialog, "情報不足", "編集対象のアイテムデータが読み込まれていません。")
            return

        main_window = get_main_window_instance()
        if not main_window:
            QMessageBox.critical(self.ai_edit_dialog, "内部エラー", "メインウィンドウのインスタンスを取得できませんでした。")
            return
        
        chat_handler = main_window.get_gemini_chat_handler() # MainWindow にこのメソッドがあると仮定
        if not chat_handler:
            QMessageBox.critical(self.ai_edit_dialog, "内部エラー", "チャットハンドラを取得できませんでした。")
            return

        # --- AI編集支援用モデル名の決定 ---
        target_model_name = None
        project_settings = getattr(main_window, 'current_project_settings', None)
        if project_settings:
            ai_edit_model = project_settings.get("ai_edit_model_name", "")
            if ai_edit_model and ai_edit_model.strip():
                target_model_name = ai_edit_model.strip()
            else:
                target_model_name = project_settings.get("model") # プロジェクトデフォルトモデル
        
        if not target_model_name: # それでも決まらない場合 (通常ありえないが念のため)
            target_model_name = chat_handler.model_name # ハンドラの現在のモデル
            QMessageBox.warning(self.ai_edit_dialog, "モデル未特定", "AI編集支援用モデルが特定できませんでした。チャット用のモデルを使用します。")
        # --- ---------------------- ---

        # --- アイテムコンテキストの準備 ---
        item_context_for_ai: Optional[str] = None
        item_name_for_context = self.item_data.get("name", "このアイテム")
        item_desc_for_context = self.item_data.get("description", "(説明なし)")

        if self.ai_edit_dialog_mode == "description":
            # 説明編集時は、プロンプトテンプレートに現在の説明が含まれるため、
            # ここでの item_context は、アイテム名など補足情報に留めるか、空でも良い。
            item_context_for_ai = f"編集対象アイテム名: {item_name_for_context}"
        elif self.ai_edit_dialog_mode == "history":
            # 履歴生成時は、現在のアイテム名と説明をコンテキストとして渡すのが有効。
            item_context_for_ai = (
                f"現在のアイテム名: {item_name_for_context}\n"
                f"現在のアイテム説明: {item_desc_for_context}"
            )
        # --- -------------------- ---

        # --- 会話履歴の準備 ---
        # MainWindow に get_current_chat_history() のようなメソッドがあると仮定
        current_chat_history = main_window.get_current_chat_history()
        # MainWindow に current_history_range_for_prompt (スライダーの値) があると仮定
        max_history_pairs = getattr(main_window, 'current_history_range_for_prompt', None)
        # --- -------------- ---

        self.ai_edit_dialog.show_processing_message(True)
        QApplication.processEvents()

        response_text, error_message, usage_data = chat_handler.generate_response_with_history_and_context(
            user_instruction=instruction_text,
            item_context=item_context_for_ai,
            chat_history_to_include=current_chat_history,
            max_history_pairs=max_history_pairs,
            override_model_name=target_model_name # ★ 決定したモデル名を渡す
        )

        self.ai_edit_dialog.show_processing_message(False)

        if error_message:
            QMessageBox.critical(self.ai_edit_dialog, "AI応答エラー", f"AIからの応答取得に失敗しました。\nエラー: {error_message}")
            self.ai_edit_dialog.set_suggestion_text("")
        elif response_text is not None:
            self.ai_edit_dialog.set_suggestion_text(response_text)
        else:
            QMessageBox.warning(self.ai_edit_dialog, "AI応答なし", "AIから有効な応答が得られませんでした。(詳細不明)")
            self.ai_edit_dialog.set_suggestion_text("")

    def select_image_file(self):
        """「画像を選択」ボタンがクリックされたときの処理。
        ファイルダイアログを開き、選択された画像をプロジェクトのimagesフォルダにコピーし、
        アイテムデータには相対パスを保存します。
        """
        if not self.item_data or not self.current_project_dir_name:
            QMessageBox.warning(self, "エラー", "画像を設定するアイテムまたはプロジェクトが選択されていません。")
            return

        source_file_path, _ = QFileDialog.getOpenFileName(
            self, "画像ファイルを選択", "",
            "画像ファイル (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if source_file_path:
            # 1. プロジェクトの画像用ディレクトリパスを取得し、なければ作成
            #    core.data_manager から ensure_project_images_dir_exists をインポートしておくこと
            from core.data_manager import ensure_project_images_dir_exists, IMAGES_SUBDIR_NAME
            
            project_images_dir_abs_path = ensure_project_images_dir_exists(self.current_project_dir_name)
            if not project_images_dir_abs_path:
                QMessageBox.critical(self, "エラー", "プロジェクトの画像保存用ディレクトリの作成に失敗しました。")
                return

            # 2. コピー先のファイルパスを決定 (ファイル名はそのまま)
            file_name_only = os.path.basename(source_file_path)
            destination_file_abs_path = os.path.join(project_images_dir_abs_path, file_name_only)

            # 3. ファイルをコピー (shutil をインポートしておくこと)
            #    既に同名ファイルが存在する場合の処理も考慮 (上書き確認など)
            #    今回はシンプルに上書きする
            import shutil
            try:
                # 同じファイルならコピーしない (移動やリネームの場合を考慮)
                if not os.path.exists(destination_file_abs_path) or not os.path.samefile(source_file_path, destination_file_abs_path):
                    shutil.copy2(source_file_path, destination_file_abs_path) # copy2はメタデータもコピー
                    print(f"Image copied from '{source_file_path}' to '{destination_file_abs_path}'")
                else:
                    print(f"Image '{file_name_only}' already exists in project and is the same file. No copy needed.")
            except Exception as e:
                QMessageBox.critical(self, "コピーエラー", f"画像のプロジェクトフォルダへのコピーに失敗しました:\n{e}")
                return

            # 4. アイテムデータに相対パスを保存
            #    相対パスは images/ファイル名 の形式
            relative_image_path = os.path.join(IMAGES_SUBDIR_NAME, file_name_only).replace("\\", "/") # OSパス区切りをスラッシュに統一
            self.item_data['image_path'] = relative_image_path
            print(f"  Saved relative image path: {relative_image_path}")

            # 5. プレビューを更新
            from PyQt5.QtCore import QTimer # QTimer をインポート
            # self._update_image_preview(relative_image_path) # 直接呼び出すのをやめる
            QTimer.singleShot(0, lambda path=relative_image_path: self._update_image_preview(path))
            print(f"  Scheduled delayed image preview update for: {relative_image_path}")

    def clear_image_file(self):
        """「画像をクリア」ボタンがクリックされたときの処理。画像パスをクリアします。"""
        if not self.item_data: return
        self.item_data['image_path'] = None
        self._update_image_preview(None)

    def _update_image_preview(self, relative_image_path: str | None):
        """指定された相対画像パスから画像をロードし、アスペクト比を維持してプレビュー表示します。
        画像がない場合はプレビューをクリアします。

        Args:
            relative_image_path (str | None): プロジェクトルートからの相対画像パス。
        """
        if not hasattr(self, 'img_preview_label') or not self.img_preview_label: # UI未初期化の場合
            return

        if relative_image_path and self.current_project_dir_name:
            # PROJECTS_BASE_DIR は config_manager から取得するか、DetailWindow が知る必要がある
            # ここでは仮に core.data_manager にそのような定数があるとする
            from core.data_manager import PROJECTS_BASE_DIR # 仮のインポート
            absolute_image_path = os.path.join(PROJECTS_BASE_DIR, self.current_project_dir_name, relative_image_path)
            
            if os.path.exists(absolute_image_path):
                pixmap = QPixmap(absolute_image_path)
                if not pixmap.isNull():
                    # --- ★★★ アスペクト比を維持してスケーリング ★★★ ---
                    # QLabel の現在のサイズに合わせてスケーリング
                    # setScaledContents(True) は使わないか、False にする
                    self.img_preview_label.setScaledContents(False) # QLabelによる自動スケーリングを無効化 [22]
                    
                    # アスペクト比を計算
                    aspect_ratio = pixmap.height() / pixmap.width() if pixmap.width() != 0 else 1 # ゼロ除算を避ける
                    
                    # ラベルのサイズを取得
                    # label_width = self.img_preview_label.width()
                    label_width = 450
                    label_height = int(label_width * aspect_ratio)

                    if label_width > 0 and label_height > 0: # ラベルサイズが有効な場合のみ
                        # アスペクト比を保ちつつ、ラベルのサイズに収まるようにスケーリング
                        # Qt.KeepAspectRatio: 指定された矩形に収まるようにアスペクト比を維持 [5][10][12][22]
                        # Qt.SmoothTransformation: スムーズな（高品質な）スケーリング
                        scaled_pixmap = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.img_preview_label.setPixmap(scaled_pixmap)
                    else:
                        # ラベルサイズがまだ確定していない場合（初回表示時など）は、
                        # 元のpixmapをそのままセットするか、デフォルトサイズでスケーリング
                        # ここでは、一度そのままセットしておき、resizeEventで調整されることを期待する
                        # あるいは、ウィンドウの初期サイズからプレビューラベルの期待サイズを計算する
                        # self.img_preview_label.setPixmap(pixmap) # これだと大きすぎる可能性
                        # 例: とりあえず幅を合わせる (高さは自動)
                        temp_scaled_pixmap = pixmap.scaledToWidth(max(400, self.img_preview_label.minimumWidth()), Qt.SmoothTransformation)
                        self.img_preview_label.setPixmap(temp_scaled_pixmap)

                    self.img_path_label.setText(f"<b>画像:</b> {relative_image_path}")
                    return # 正常に表示
                else:
                    self.img_path_label.setText("<b>画像:</b> (読み込みエラー)")
            else:
                self.img_path_label.setText("<b>画像:</b> (ファイルが見つかりません)")
        else:
            self.img_path_label.setText("<b>画像:</b> (選択されていません)")
        
        self.img_preview_label.clear() # 画像がない場合やエラー時はクリア

    
    def resizeEvent(self, event: 'QResizeEvent'):
        """ウィンドウのリサイズイベント。
        画像プレビューのアスペクト比を維持して再描画します。
        """
        super().resizeEvent(event) # 親クラスのイベント処理を呼び出す
        if hasattr(self, 'item_data') and self.item_data and hasattr(self, 'img_preview_label') and self.img_preview_label.isVisible():
            # item_data がロードされていて、プレビューラベルが表示されている場合のみ更新
            # _update_image_preview は内部でラベルサイズを取得してスケーリングするので、
            # ここで再度呼び出せば、新しいラベルサイズに合わせてアスペクト比を維持した画像が表示される。
            current_image_path = self.item_data.get("image_path")
            if current_image_path: # 画像パスがあれば再描画
                 print(f"DetailWindow.resizeEvent: Updating image preview for {current_image_path}")
                 self._update_image_preview(current_image_path)
            # else: 画像パスがなければ _update_image_preview(None) が呼ばれるか、何もしない
            #       (clear_image_file などで既にクリアされているはず)


    def add_history_entry_with_ai_ui(self):
        """AIの支援を受けて新しい履歴エントリを作成し、UI経由で追加します。"""
        if not gemini_is_configured():
            QMessageBox.warning(self, "APIキー未設定", "Gemini APIキーが設定されていません。設定画面でキーを登録してください。")
            return
        if not self.item_data or not self.current_project_dir_name or not self.current_category:
            QMessageBox.warning(self, "情報不足", "アイテムデータ、プロジェクト、またはカテゴリが正しく読み込まれていません。")
            return

        item_name = self.item_data.get("name", "このアイテム")
        item_desc = self.item_data.get("description", "(説明なし)")
        existing_history_entries = self.item_data.get("history", [])
        
        # --- 履歴コンテキストの整形 (最大件数はメインウィンドウから取得できるようにしたい) ---
        main_window_for_hist = get_main_window_instance()
        max_history_for_context_ui = 5 # デフォルト値
        if main_window_for_hist:
            # MainWindowに `get_item_history_range_for_prompt()` のようなメソッドがあるか、
            # あるいは設定値に直接アクセスできると良い。
            # ここでは仮に固定値を使うが、将来的には MainWindow 経由で取得を検討。
            # (例: self.main_window.settings_dialog.item_history_range_spinbox.value() など、ただし循環参照に注意)
            # 今回はプロジェクト設定の `ai_edit_prompts` のプレースホルダーに合わせる
            # {max_item_history_entries} が使えるようにする
            pass # 後で MainWindow 側に getter を作るか、設定値を直接参照

        history_context_str = "既存の履歴はありません。"
        if existing_history_entries:
            # 履歴表示は最新のものが下（リストの末尾）なので、最後からN件を取得
            # テンプレートで {max_item_history_entries} を使う前提なので、ここでは全件渡しても良いし、
            # プロンプトが長くなりすぎるのを防ぐために、ここで絞っても良い。
            # 今回は、テンプレート側で絞ることを期待し、ある程度の件数を渡す。
            # (ただし、あまりにも長大な履歴は問題になる可能性があるので、適度に制限するのが望ましい)
            # ここでは最大10件に制限してみる。
            num_to_show = 10 
            shown_entries = []
            for entry_dict in reversed(existing_history_entries[-num_to_show:]):
                shown_entries.append(f"- {entry_dict.get('entry', '(内容なし)')}")
            history_context_str = "\n".join(shown_entries)
            if len(existing_history_entries) > num_to_show:
                history_context_str += f"\n... (他{len(existing_history_entries) - num_to_show}件)"
        
        # --- プロンプトテンプレートの取得とフォーマット ---
        initial_instruction = "AIへの指示をここに記述してください。"
        if main_window_for_hist and main_window_for_hist.current_project_settings:
            project_settings = main_window_for_hist.current_project_settings
            ai_prompts = project_settings.get("ai_edit_prompts", DEFAULT_PROJECT_SETTINGS.get("ai_edit_prompts", {}))
            raw_template = ai_prompts.get("history_entry_add", "")
            
            # {max_item_history_entries} の値を決定 (設定画面にUIがないので仮の値)
            # 本来は設定から取得するべきだが、今回は固定値で。5件くらいが妥当か。
            max_entries_for_template_placeholder = 5 

            placeholders = {
                "item_name": item_name,
                "user_instruction": "", # ダイアログでユーザーが入力
                "item_description": item_desc,
                "item_existing_history": history_context_str, # 整形済み履歴
                "max_item_history_entries": max_entries_for_template_placeholder
            }
            try:
                initial_instruction = raw_template.format(**placeholders)
            except KeyError as e:
                QMessageBox.warning(self, "テンプレートエラー", f"履歴追加プロンプトのフォーマットに失敗: {e}")
            except Exception as e:
                 QMessageBox.critical(self, "致命的なテンプレートエラー", f"履歴プロンプト生成中に予期せぬエラー: {e}")
                 return
        else:
            QMessageBox.warning(self, "設定エラー", "プロジェクト設定を読み込めず、デフォルトの指示を使用します。")
            # フォールバック (プロジェクト設定がない場合)
            # (この部分は、仕様に応じてより詳細なエラー処理やデフォルトテンプレートの提供を検討)
            initial_instruction = f"アイテム「{item_name}」の新しい履歴エントリを作成してください。ユーザーの指示を考慮してください。"

        self.ai_edit_dialog_mode = "history" # モード設定
        self.ai_edit_dialog = AIAssistedEditDialog(
            initial_instruction_text=initial_instruction,
            current_item_description=item_desc, # 履歴モードではコンテキストとして利用
            parent=self,
            window_title=f"AIで「{item_name}」の履歴エントリを生成"
        )
        # 接続は変わらず
        self.ai_edit_dialog.request_ai_button.clicked.connect(
            lambda: self._handle_ai_suggestion_request( # ラムダでラップ
                self.ai_edit_dialog.get_instruction_text()
            )
        )

        if self.ai_edit_dialog.exec_() == QDialog.Accepted:
            new_history_entry_text = self.ai_edit_dialog.get_final_text().strip()
            if new_history_entry_text:
                success, message = add_history_entry(self.current_project_dir_name,
                                                   self.current_category,
                                                   self.current_item_id,
                                                   new_history_entry_text)
                if success:
                    QMessageBox.information(self, "履歴追加成功", "新しい履歴エントリが追加されました。")
                    self.load_data(self.current_category, self.current_item_id) # 再読み込みして表示更新
                else:
                    QMessageBox.critical(self, "履歴追加失敗", f"履歴エントリの追加に失敗しました。\n{message}")
            else:
                QMessageBox.information(self, "履歴未追加", "履歴エントリのテキストが空だったため、追加されませんでした。")
        self.ai_edit_dialog = None # インスタンスをクリア

    # 履歴編集UIメソッド
    def edit_history_entry_ui(self):
        """「履歴を編集」ボタンがクリックされたときの処理。
        ユーザーに番号で編集対象の履歴を指定させ、複数行入力ダイアログで編集させ、変更を保存します。
        """
        if not self.item_data or not self.current_category or not self.current_item_id or not self.current_project_dir_name:
            QMessageBox.warning(self, "エラー", "履歴を編集するアイテムが選択されていません。")
            return

        history_list = self.item_data.get("history", [])
        if not history_list:
            QMessageBox.information(self, "履歴なし", "編集できる履歴がありません。")
            return

        num_entries = len(history_list)
        entry_number, ok = QInputDialog.getInt(
            self, "履歴編集",
            f"編集する履歴の番号を入力してください (1～{num_entries}):",
            min=1, max=num_entries, value=1
        )

        if ok:
            index_to_edit = entry_number - 1 # 0ベースのインデックス
            if 0 <= index_to_edit < num_entries:
                current_entry_dict = history_list[index_to_edit]
                current_entry_text = current_entry_dict.get('entry', '')

                new_entry_text, ok_multiline = QInputDialog.getMultiLineText(
                    self, "履歴編集",
                    f"履歴 ({entry_number}) の内容を編集してください:",
                    current_entry_text
                )

                if ok_multiline and new_entry_text.strip() != current_entry_text.strip(): # 内容が変更された場合のみ
                    # 履歴エントリの 'entry' を更新
                    # (id や timestamp は変更しない)
                    self.item_data['history'][index_to_edit]['entry'] = new_entry_text.strip()

                    if update_item(self.current_project_dir_name, self.current_category, self.current_item_id, {"history": self.item_data['history']}):
                        QMessageBox.information(self, "履歴編集完了", f"履歴エントリ ({entry_number}) を更新しました。")
                        self.load_data(self.current_category, self.current_item_id) # UIを再読み込み
                    else:
                        QMessageBox.warning(self, "履歴編集エラー", "履歴の編集内容の保存に失敗しました。")
                        # 保存失敗時はメモリ上の item_data['history'] を元に戻す方が安全
                        self.item_data['history'][index_to_edit]['entry'] = current_entry_text # 元に戻す
                elif ok_multiline: # OK押したが変更なし
                    QMessageBox.information(self, "変更なし", "履歴内容は変更されませんでした。")
            else:
                QMessageBox.warning(self, "入力エラー", f"無効な番号です。1から{num_entries}の間で指定してください。")

    # 履歴削除UIメソッド
    def delete_history_entry_ui(self):
        """「履歴を削除」ボタンがクリックされたときの処理。
        ユーザーに番号で削除対象の履歴を指定させ、削除を実行します。
        """
        if not self.item_data or not self.current_category or not self.current_item_id or not self.current_project_dir_name:
            QMessageBox.warning(self, "エラー", "履歴を追加するアイテムが選択されていません。")
            return

        history_list = self.item_data.get("history", [])
        if not history_list:
            QMessageBox.information(self, "履歴なし", "削除できる履歴がありません。")
            return

        # ユーザーに削除する履歴の番号を入力させる
        # 履歴は1から始まる番号で表示されている想定
        num_entries = len(history_list)
        entry_number, ok = QInputDialog.getInt(
            self, "履歴削除",
            f"削除する履歴の番号を入力してください (1～{num_entries}):",
            min=1, max=num_entries, value=1
        )

        if ok:
            index_to_delete = entry_number - 1 # 0ベースのインデックスに変換
            if 0 <= index_to_delete < num_entries:
                entry_to_delete = history_list[index_to_delete]
                entry_text_preview = entry_to_delete.get('entry', '(内容不明)')[:30] + "..." \
                                     if len(entry_to_delete.get('entry', '')) > 30 \
                                     else entry_to_delete.get('entry', '(内容不明)')

                reply = QMessageBox.question(self, "履歴削除確認",
                                           f"以下の履歴エントリ ({entry_number}) を本当に削除しますか？\n\n「{entry_text_preview}」\n\nこの操作は元に戻せません。",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    # 履歴リストから該当エントリを削除 (IDで照合がより確実だが、今回はインデックスで)
                    # もし add_history_entry で履歴にIDを振っていれば、そのIDで削除する方が良い
                    # ここでは、リストから直接削除する
                    del self.item_data['history'][index_to_delete]

                    if update_item(self.current_project_dir_name, self.current_category, self.current_item_id, {"history": self.item_data['history']}):
                        QMessageBox.information(self, "履歴削除完了", f"履歴エントリ ({entry_number}) を削除しました。")
                        self.load_data(self.current_category, self.current_item_id) # UIを再読み込み
                    else:
                        QMessageBox.warning(self, "履歴削除エラー", "履歴の削除内容の保存に失敗しました。")
                        # 失敗した場合、メモリ上の item_data['history'] を元に戻す方が安全
                        # (今回は簡略化のため、再ロードに任せる)
            else:
                QMessageBox.warning(self, "入力エラー", f"無効な番号です。1から{num_entries}の間で指定してください。")

    def save_details(self):
        """「変更を保存」ボタンがクリックされたときの処理。編集内容をファイルに保存します。"""
        if not self.item_data or not self.current_category or not self.current_item_id or not self.current_project_dir_name:
            QMessageBox.warning(self, "保存エラー", "保存するデータがロードされていません。")
            return

        # --- UIから更新されたデータを収集 ---
        updated_data_payload = {} # 保存する変更差分
        changed_fields_count = 0

        # 名前
        if 'name' in self.detail_widgets:
            new_name = self.detail_widgets['name'].text().strip()
            if new_name != self.item_data.get('name'):
                updated_data_payload['name'] = new_name
                changed_fields_count += 1

        # 説明/メモ
        if 'description' in self.detail_widgets:
            new_desc = self.detail_widgets['description'].toPlainText().strip()
            if new_desc != self.item_data.get('description'):
                updated_data_payload['description'] = new_desc
                changed_fields_count += 1
                
        # タグ (アイテム自身のタグ)
        if 'tags' in self.detail_widgets:
            tags_str = self.detail_widgets['tags'].text()
            new_tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            # 保存されているリストと比較 (順序無視)
            # self.item_data.get('tags', []) がNoneの場合も考慮
            current_tags = self.item_data.get('tags', [])
            if current_tags is None: current_tags = [] # Noneなら空リストとして扱う
            if set(new_tags_list) != set(current_tags):
                updated_data_payload['tags'] = new_tags_list
                changed_fields_count += 1

        # --- ★★★ 参照先タグの変更を収集 ★★★ ---
        if 'reference_tags' in self.detail_widgets:
            ref_tags_str = self.detail_widgets['reference_tags'].text()
            new_ref_tags_list = [tag.strip() for tag in ref_tags_str.split(',') if tag.strip()]
            current_ref_tags = self.item_data.get('reference_tags', [])
            if current_ref_tags is None: current_ref_tags = []
            if set(new_ref_tags_list) != set(current_ref_tags):
                updated_data_payload['reference_tags'] = new_ref_tags_list
                changed_fields_count += 1
        # --- ★★★ ------------------------- ★★★ ---

        # 画像パス
        original_item_for_image_check = get_item(self.current_project_dir_name, self.current_category, self.current_item_id)
        if original_item_for_image_check and self.item_data.get('image_path') != original_item_for_image_check.get('image_path'):
             updated_data_payload['image_path'] = self.item_data.get('image_path')
             changed_fields_count += 1

        if changed_fields_count == 0:
            QMessageBox.information(self, "変更なし", "保存する変更点がありません。")
            return

        if update_item(self.current_project_dir_name, self.current_category, self.current_item_id, updated_data_payload):
            QMessageBox.information(self, "保存完了", "変更を保存しました。")
            # ローカルの item_data も更新
            for key, value in updated_data_payload.items():
                self.item_data[key] = value
            # ウィンドウタイトル更新 (名前変更時)
            if 'name' in updated_data_payload:
                self.setWindowTitle(f"詳細: {updated_data_payload['name']} ({self.current_category})")
            self.dataSaved.emit(self.current_category, self.current_item_id)
        else:
            QMessageBox.warning(self, "保存エラー", "変更の保存に失敗しました。")


    def closeEvent(self, event):
        """ウィンドウが閉じられるときに呼び出されるイベントハンドラ。"""
        print("DetailWindow is closing.")
        self.windowClosed.emit()
        # 必要なら未保存の変更があるか確認して警告を出す処理を追加
        super().closeEvent(event)


if __name__ == '__main__':
    """DetailWindow の基本的な表示・インタラクションテスト。"""
    app = QApplication(sys.argv)
    test_project_name_detail = "detail_window_test_hist_del"; test_category_name_detail = "テストキャラ履歴削除"; test_item_id_detail = "char-test-hist-del-001"
    from core.config_manager import save_project_settings as sps, DEFAULT_PROJECT_SETTINGS as DPS
    sps(test_project_name_detail, DPS.copy())
    from core.data_manager import create_category as dmcc, add_item as dmai
    dmcc(test_project_name_detail, test_category_name_detail)
    dmai(test_project_name_detail, test_category_name_detail, {"id": test_item_id_detail, "name": "履歴削除テスト勇者", "description": "初期説明。", "history": [{"id":"dummy-uuid-1", "timestamp":"2024-01-01", "entry":"冒険開始"}, {"id":"dummy-uuid-2", "timestamp":"2024-01-02", "entry":"ドラゴン遭遇"}], "tags": ["テスト"], "image_path": None})
    main_test_config = {"model": "gemini-1.5-flash-latest"}
    detail_win = DetailWindow(main_config=main_test_config, project_dir_name=test_project_name_detail)
    detail_win.load_data(test_category_name_detail, test_item_id_detail)
    detail_win.dataSaved.connect( lambda cat, iid: print(f"\n--- Signal: dataSaved received for Category='{cat}', ItemID='{iid}' ---"))
    detail_win.windowClosed.connect( lambda: print("\n--- Signal: windowClosed received ---"))
    detail_win.show(); app_exit_code = app.exec_()
    import shutil; test_project_dir_to_remove = os.path.join("data", test_project_name_detail)
    if os.path.exists(test_project_dir_to_remove): shutil.rmtree(test_project_dir_to_remove)
    sys.exit(app_exit_code)

