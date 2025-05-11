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
    QSizePolicy, QSpacerItem, QInputDialog, QApplication
)
from PyQt5.QtGui import QPixmap, QImageReader
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtGui import QBrush, QPalette

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.data_manager import get_item, update_item, add_history_entry
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
    
        self._image_display_mode: str = "normal" # "normal" または "background"
        """str: 現在の画像表示モード ("normal" または "background")。"""

        self.setObjectName("DetailWindow") # スタイルシートで特定できるように

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
        """
        if not self.item_data: return

        # 名前
        name_label = QLabel("名前:"); name_edit = QLineEdit(self.item_data.get("name", "")); self.detail_widgets['name'] = name_edit; self.content_layout.addWidget(name_label); self.content_layout.addWidget(name_edit)

        # 説明/メモ
        desc_label = QLabel("説明/メモ:"); desc_edit = QTextEdit(self.item_data.get("description", "")); desc_edit.setMinimumHeight(150); desc_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); self.detail_widgets['description'] = desc_edit; self.content_layout.addWidget(desc_label); self.content_layout.addWidget(desc_edit)
        ai_update_button = QPushButton("AIで「説明/メモ」を編集支援"); ai_update_button.clicked.connect(self._on_ai_update_description_clicked); self.content_layout.addWidget(ai_update_button)

        # 履歴
        history_label = QLabel("履歴:")
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
                formatted_entry_text = entry_text_for_display.replace("\n", "<br>")
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

        # タグ
        tags_label = QLabel("タグ (カンマ区切り):"); tags_edit = QLineEdit(", ".join(self.item_data.get("tags", []))); self.detail_widgets['tags'] = tags_edit; self.content_layout.addWidget(tags_label); self.content_layout.addWidget(tags_edit)

        # 画像
        img_section_layout = QHBoxLayout()
        img_label = QLabel("画像:")
        img_section_layout.addWidget(img_label)
        img_section_layout.addStretch()
        
        self.toggle_image_mode_button = QPushButton("背景表示に切替") # ボタンテキストはモードによって変更
        self.toggle_image_mode_button.setToolTip("画像表示を通常モードと背景モードで切り替えます。")
        self.toggle_image_mode_button.setCheckable(True) # チェック状態を持つボタンに
        self.toggle_image_mode_button.toggled.connect(self._on_toggle_image_mode)
        img_section_layout.addWidget(self.toggle_image_mode_button)
        
        select_img_button = QPushButton("画像を選択")
        select_img_button.clicked.connect(self.select_image_file)
        img_section_layout.addWidget(select_img_button)
        clear_img_button = QPushButton("画像をクリア")
        clear_img_button.clicked.connect(self.clear_image_file)
        img_section_layout.addWidget(clear_img_button)
        self.content_layout.addLayout(img_section_layout)

        self.img_path_label = QLabel("画像パス: (選択されていません)")
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
        self.content_layout.addWidget(self.img_preview_label)

        # --- ★★★ スクロールコンテンツウィジェットにオブジェクト名を設定 ★★★ ---
        if self.scroll_content_widget:
            self.scroll_content_widget.setObjectName("ScrollContentWidget")
            # スクロールコンテンツの背景を初期状態で透明にする（スタイルシートで上書き可能）
            self.scroll_content_widget.setStyleSheet("QWidget#ScrollContentWidget { background-color: transparent; }")
        # --- ★★★ ---------------------------------------------------- ★★★ ---
        
        # --- ★★★ 各編集ウィジェットにもスタイル設定用の名前を付ける（任意） ★★★ ---
        name_edit.setObjectName("DetailNameEdit")
        desc_edit.setObjectName("DetailDescriptionEdit")
        self.history_view_text_edit.setObjectName("DetailHistoryView") # self.history_view_text_edit に変更
        tags_edit.setObjectName("DetailTagsEdit")
        # これにより、背景画像モード時にこれらのウィジェットの背景を不透明にするスタイルを適用しやすくなる
        # 例: self.setStyleSheet("QWidget#DetailWindow { ... } QLineEdit#DetailNameEdit { background-color: white; } ");
        # -----------------------------------------------------------------

        self._update_image_display_mode() # 初期表示モードを適用
        self._update_image_preview(self.item_data.get("image_path")) # 最後にプレビュー更新

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.content_layout.addSpacerItem(spacer)


    def _on_ai_update_description_clicked(self):
        """「AIで「説明/メモ」を編集支援」ボタンがクリックされたときの処理。
        `AIAssistedEditDialog` を説明編集モードで開きます。
        """
        if not self.item_data: QMessageBox.warning(self, "エラー", "編集対象のアイテムがロードされていません。"); return
        if self.ai_edit_dialog is not None and self.ai_edit_dialog.isVisible(): self.ai_edit_dialog.activateWindow(); return

        current_description = self.detail_widgets.get('description').toPlainText()
        # AIへの指示テンプレート (より高度なものは設定ファイルなどからロードする)
        instruction_template = (
            f"あなたはTRPGのデータ管理を行うアシスタントです。\n"
            f"以下の「現在の説明/メモ」に基づいて、現在の状況を考慮して新しい「説明/メモ」を作成してください。\n"
            f"元の情報で重要なものが失われないようにし、説明/メモ以外の余計な情報は出力しないようにしてください。\n\n"
            f"現在の説明/メモ:\n"
            f"--------------------\n"
            f"{current_description}\n"
            f"--------------------\n\n"
        )
        self.ai_edit_dialog_mode = "description" # モード設定

        self.ai_edit_dialog = AIAssistedEditDialog(
            initial_instruction_text=instruction_template,
            current_item_description=current_description,
            parent=self,
            window_title="AIによる「説明/メモ」編集支援"
        )
        # AI提案依頼ボタンのクリックシグナルを接続
        self.ai_edit_dialog.request_ai_button.clicked.connect(self._handle_ai_suggestion_request)

        if self.ai_edit_dialog.exec_() == QDialog.Accepted: # ダイアログでOKが押された
            final_edited_text = self.ai_edit_dialog.get_final_text()
            update_payload = {'description': final_edited_text}

            if not self.current_project_dir_name or not self.current_category or not self.current_item_id:
                QMessageBox.warning(self, "エラー", "アイテムの更新に必要な情報が不足しています。")
                self.ai_edit_dialog = None # ダイアログインスタンスをクリア
                return

            if update_item(self.current_project_dir_name, self.current_category, self.current_item_id, update_payload):
                QMessageBox.information(self, "更新完了", "「説明/メモ」をAIの提案に基づいて更新しました。")
                self.item_data['description'] = final_edited_text # ローカルデータも更新
                if 'description' in self.detail_widgets:
                    self.detail_widgets['description'].setPlainText(final_edited_text) # UIも更新
                self.dataSaved.emit(self.current_category, self.current_item_id)
            else: QMessageBox.warning(self, "保存エラー", "「説明/メモ」の更新内容の保存に失敗しました。")
        else: print("AIによる説明編集はキャンセルされました。")
        self.ai_edit_dialog = None; self.ai_edit_dialog_mode = None # クリア


    def _handle_ai_suggestion_request(self):
        """`AIAssistedEditDialog` からAI提案依頼があった場合の処理。
        現在の `self.ai_edit_dialog_mode` に応じてAIへの処理を行います。
        """
        if not self.ai_edit_dialog: return

        instruction_text = self.ai_edit_dialog.get_instruction_text()
        if not instruction_text.strip(): QMessageBox.warning(self.ai_edit_dialog, "入力エラー", "AIへの指示を入力してください。"); return
        ai_model_to_use = self.main_config.get("model", "gemini-1.5-pro-latest"); self.ai_edit_dialog.show_processing_message(True)
        from core.gemini_handler import generate_response as call_gemini, is_configured as gemini_is_configured
        if not gemini_is_configured():
            QMessageBox.critical(self.ai_edit_dialog, "APIエラー", "Gemini APIが設定されていません。"); self.ai_edit_dialog.show_processing_message(False); return

        # --- ★★★ モードに応じてプロンプトの前処理や後処理を変えることも可能 ★★★ ---
        # 例えば、履歴モードの場合は、AIからの応答を1行に整形するような後処理を加えるなど。
        # 現状は instruction_text をそのまま渡す。
        final_prompt_for_ai = instruction_text
        # if self.ai_edit_dialog_mode == "history":
        #     final_prompt_for_ai += "\n上記の情報を基に、タイムスタンプを除いた1行の履歴エントリを生成してください。" # 例

        ai_suggestion, error_msg = call_gemini(ai_model_to_use, final_prompt_for_ai)
        self.ai_edit_dialog.show_processing_message(False)

        if error_msg:
            QMessageBox.warning(self.ai_edit_dialog, "AI提案エラー", f"AIからの提案取得に失敗しました:\n{error_msg}")
        elif ai_suggestion:
            # --- ★★★ 履歴モードの場合、生成されたテキストを1行に丸める（任意） ★★★ ---
            processed_suggestion = ai_suggestion
            if self.ai_edit_dialog_mode == "history":
                # 複数行の提案が来た場合、最初の行だけ採用するか、改行をスペースに置換するなど
                processed_suggestion = ai_suggestion.splitlines()[0] if ai_suggestion.strip() else "AIからの提案なし"
            # -------------------------------------------------------------------
            self.ai_edit_dialog.set_suggestion_text(processed_suggestion)
            QMessageBox.information(self.ai_edit_dialog, "提案取得完了", "AIからの提案を取得しました。必要に応じて編集してください。")
        else:
            QMessageBox.information(self.ai_edit_dialog, "提案なし", "AIから有効な提案がありませんでした。")


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

    def _on_toggle_image_mode(self, checked: bool):
        """「背景表示切替」ボタンの状態が変更されたときに呼び出されるスロット。
        画像表示モードを切り替えます。

        Args:
            checked (bool): ボタンがチェックされた状態なら True。
        """
        if checked:
            self._image_display_mode = "background"
            self.toggle_image_mode_button.setText("通常表示に切替")
            self.toggle_image_mode_button.setToolTip("画像表示を通常プレビューモードに戻します。")
        else:
            self._image_display_mode = "normal"
            self.toggle_image_mode_button.setText("背景表示に切替")
            self.toggle_image_mode_button.setToolTip("画像をウィンドウの背景として表示します。")
        
        self._update_image_display_mode()

    def _update_image_display_mode(self):
        """現在の `_image_display_mode` に基づいて、画像表示関連のUIを更新します。
        """
        print(f"Updating image display mode to: {self._image_display_mode}")
        
        # DetailWindow自体はQPaletteで背景画像を設定
        # ScrollContentWidgetと、その中の主要な入力ウィジェットはスタイルシートで背景を制御

        if self._image_display_mode == "background":
            # 背景表示モード
            self.img_path_label.setVisible(False)
            self.img_preview_label.setVisible(False)
            
            current_stylesheet_parts = []

            if self._original_image_pixmap and not self._original_image_pixmap.isNull():
                # QPaletteでDetailWindowの背景画像を設定 (前回と同様)
                self.setAutoFillBackground(True)
                palette = self.palette()
                bg_pixmap_scaled = self._original_image_pixmap.scaled(
                    self.size(), # DetailWindowの現在のサイズ
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                palette.setBrush(QPalette.Window, QBrush(bg_pixmap_scaled))
                self.setPalette(palette)
                
                # ScrollContentWidget の背景を透明に (スタイルシート)
                current_stylesheet_parts.append(
                    "QWidget#ScrollContentWidget {"
                    "  background-color: transparent;"
                    "}"
                )
                
                # 各編集ウィジェットの背景を半透明の白に (スタイルシートでIDセレクタ使用)
                # _build_detail_viewでsetObjectNameしている前提
                input_widget_bg = "background-color: rgba(255, 255, 255, 0.85); border: 1px solid lightgray;"
                current_stylesheet_parts.append(f"QLineEdit#DetailNameEdit {{ {input_widget_bg} }}")
                current_stylesheet_parts.append(f"QTextEdit#DetailDescriptionEdit {{ {input_widget_bg} }}")
                # QTextEdit の viewport も透明にする (より確実に背景画像を見せるため)
                current_stylesheet_parts.append(
                    "QTextEdit#DetailDescriptionEdit QAbstractScrollArea,"
                    "QTextEdit#DetailDescriptionEdit QWidget {" # viewportとその中のウィジェット
                    "  background-color: transparent;"
                    "}"
                )
                current_stylesheet_parts.append(f"QTextEdit#DetailHistoryView {{ {input_widget_bg} }}")
                current_stylesheet_parts.append(
                    "QTextEdit#DetailHistoryView QAbstractScrollArea,"
                    "QTextEdit#DetailHistoryView QWidget {"
                    "  background-color: transparent;"
                    "}"
                )
                current_stylesheet_parts.append(f"QLineEdit#DetailTagsEdit {{ {input_widget_bg} }}")

                # QLabelはデフォルトで背景が親に追従するので、通常は明示的な透明化は不要
                # もしQLabelの背景が不透明に見える場合は追加
                # current_stylesheet_parts.append("QLabel { background-color: transparent; }")

                print(f"  Set background image using QPalette for DetailWindow.")
            else: # 画像データがない
                self.setAutoFillBackground(False)
                self.setPalette(QPalette()) # デフォルトパレットに戻す
                print("  No original image pixmap for background mode (QPalette). Cleared DetailWindow background.")

            # スタイルシートを適用 (ScrollContentWidget と編集ウィジェット用)
            final_stylesheet = "\n".join(current_stylesheet_parts)
            # DetailWindow 自体のスタイルシートはQPaletteで管理しているので、
            # ここで self.setStyleSheet を呼ぶとQPaletteが上書きされる可能性がある。
            # scroll_content_widget にスタイルを適用するか、
            # あるいは各ウィジェットに個別に setStyleSheet する。
            # ここでは、DetailWindowにまとめて設定し、QPaletteが影響を受けないように
            # DetailWindow#QWidget の背景指定は含めない。
            if self.scroll_content_widget: # scroll_content_widget は常に存在するはずだが念のため
                 # scroll_content_widget は透明にし、その子ウィジェットにスタイルを適用
                 # scroll_content_widget に objectName が設定されている前提
                 scroll_content_widget_style = "QWidget#ScrollContentWidget { background-color: transparent; }"
                 
                 # 個々の入力ウィジェットのスタイル
                 name_edit_style = f"QLineEdit#DetailNameEdit {{ {input_widget_bg} }}"
                 desc_edit_style = (
                     f"QTextEdit#DetailDescriptionEdit {{ {input_widget_bg} }}"
                     # QTextEditのviewportの背景も透過させることで、下の背景画像が見えるようにする
                     # ただし、入力エリアの背景はinput_widget_bgで半透明白にしているので、
                     # viewport自体は完全に透明で良い。
                     f"QTextEdit#DetailDescriptionEdit > QAbstractScrollArea > QWidget {{ background-color: transparent; }}"
                 )
                 hist_view_style = (
                     f"QTextEdit#DetailHistoryView {{ {input_widget_bg} }}"
                     f"QTextEdit#DetailHistoryView > QAbstractScrollArea > QWidget {{ background-color: transparent; }}"
                 )
                 tags_edit_style = f"QLineEdit#DetailTagsEdit {{ {input_widget_bg} }}"

                 # DetailWindowに適用するスタイルシートは、これらの子ウィジェットのスタイルのみ
                 combined_stylesheet = "\n".join([
                     scroll_content_widget_style,
                     name_edit_style,
                     desc_edit_style,
                     hist_view_style,
                     tags_edit_style
                 ])
                 self.setStyleSheet(combined_stylesheet)
                 print(f"  Applied stylesheet for child widgets:\n{combined_stylesheet}")

        else: # "normal" モード
            # 背景をデフォルトに戻す
            self.setAutoFillBackground(False)
            self.setPalette(QPalette()) # デフォルトパレットに戻す
            self.setStyleSheet("") # 全てのスタイルシートをクリア

            self.img_path_label.setVisible(True)
            self.img_preview_label.setVisible(True)
            self._update_image_preview(self.item_data.get('image_path') if self.item_data else None)
        
        # ボタンの有効/無効状態 (変更なし)
        can_show_background = bool(self._original_image_pixmap and not self._original_image_pixmap.isNull())
        self.toggle_image_mode_button.setEnabled(can_show_background)
        if not can_show_background and self._image_display_mode == "background":
            self.toggle_image_mode_button.setChecked(False)

        self.update() # 念のため再描画

    def _update_image_preview(self, relative_image_path: str | None):
        """指定された相対画像パスに基づいて画像プレビューを更新します。
        オリジナルのピクスマップを保持し、表示時にラベルサイズに合わせてスケーリングします。
        相対パスはプロジェクトルートからのパス (例: 'images/キャラ絵.png') とします。

        Args:
            relative_image_path (str | None): 表示する画像のプロジェクト相対パス。Noneの場合はプレビューをクリア。
        """
        if 'image_preview' not in self.detail_widgets or 'image_path_display' not in self.detail_widgets:
            return

        preview_label = self.detail_widgets.get('image_preview')
        if not isinstance(preview_label, QLabel): # 念のため型チェック
            return

        # --- ★★★ ラベルの setScaledContents は True のままにしておく ★★★ ---
        # preview_label.setScaledContents(True) # _build_detail_view で設定済みのはず

        if not self.current_project_dir_name and relative_image_path:
            # ... (変更なし)
            preview_label.clear(); preview_label.setText("画像プレビュー (プロジェクト未指定)"); self.img_path_label.setText(f"画像パス: {relative_image_path} (プロジェクト未指定)"); self._original_image_pixmap = None; preview_label.setMinimumHeight(150); preview_label.setMaximumHeight(16777215)
            if hasattr(self, 'toggle_image_mode_button'): self.toggle_image_mode_button.setEnabled(False) # ★ ボタン無効化
            return

        absolute_image_path = None
        if relative_image_path:
            # プロジェクトルートからの相対パスなので、プロジェクトベースディレクトリと結合
            # core.data_manager から PROJECTS_BASE_DIR をインポートするか、
            # または MainWindow 経由でプロジェクトの絶対パスを取得する。
            # ここでは get_project_images_path のように組み立てる。
            from core.data_manager import PROJECTS_BASE_DIR # data_managerからインポート
            project_root_abs_path = os.path.join(PROJECTS_BASE_DIR, self.current_project_dir_name)
            absolute_image_path = os.path.join(project_root_abs_path, relative_image_path)
            print(f"  Attempting to load image from absolute path: {absolute_image_path} (relative: {relative_image_path})")

        self._original_image_pixmap = None # まずクリア
        image_loaded_successfully = False # ★ 画像ロード成功フラグ

        if absolute_image_path and os.path.exists(absolute_image_path):
            try:
                # オリジナルのピクスマップを読み込んで保持
                original_pixmap = QPixmap(absolute_image_path)
                if not original_pixmap.isNull():
                    self._original_image_pixmap = original_pixmap
                    
                    # --- ★★★ 画像のアスペクト比に基づいてラベルの高さを設定 ★★★ ---
                    img_width = original_pixmap.width()
                    img_height = original_pixmap.height()

                    if img_width > 0 and img_height > 0:
                        # ラベルの現在の幅を取得（これが基準になる）
                        # 初回表示時はまだ幅が小さい可能性があるので、親ウィジェットの幅も考慮
                        available_width = preview_label.width()
                        if available_width <= preview_label.minimumWidth(): # 初期値や最小サイズより小さい場合
                            if self.scroll_content_widget and self.scroll_content_widget.width() > 20 :
                                available_width = self.scroll_content_widget.width() - 20 # スクロールエリアの幅から
                            elif self.width() > 40:
                                available_width = self.width() - 40 # DetailWindowの幅から
                            else:
                                available_width = preview_label.minimumWidth() # 最低でもラベルの最小幅

                        # アスペクト比を維持した高さを計算
                        expected_height = int((img_height / img_width) * available_width)
                        
                        # 上限は設けないか、非常に大きな値にする
                        # max_preview_height = 16777215 # Qtの最大ウィジェット高さ
                        # expected_height = min(expected_height, max_preview_height)
                        
                        min_height_for_label = 100 # どんな画像でも最低これくらいは確保 (任意)
                        expected_height = max(expected_height, min_height_for_label)

                        print(f"  _update_image_preview: Image original: {img_width}x{img_height}, Label available_width: {available_width}, Calculated expected_height for minimum: {expected_height}")
                        
                        # ラベルの高さを明示的に設定
                        # setFixedHeight を使うとリサイズ時に追従しなくなるので setMinimumHeight と setMaximumHeight を使う
                        preview_label.setMinimumHeight(expected_height)
                        preview_label.setMaximumHeight(16777215) # 最大高さ制限を解除！

                        # ピクスマップをラベルにセット (resizeEvent で適切なスケーリングが行われる)
                        # ここでは、一度アスペクト比を保ってスケーリングしたものをセットしておく
                        scaled_pixmap = self._original_image_pixmap.scaled(
                            available_width, expected_height, # 計算した幅と高さ
                            Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        preview_label.setPixmap(scaled_pixmap); image_loaded_successfully = True # ★ ロード成功
                        # --------------------------------------------------------------
                    else:
                        preview_label.clear(); preview_label.setText("画像サイズ不正")
                    # --------------------------------------------------------
                    self.img_path_label.setText(f"画像パス: {relative_image_path}")
                else:
                    preview_label.clear(); preview_label.setText(f"画像読込失敗:\n{os.path.basename(absolute_image_path)}"); self.img_path_label.setText(f"画像パス(読込エラー): {relative_image_path}")
            except Exception as e:
                self._original_image_pixmap = None; preview_label.clear(); preview_label.setText(f"画像表示エラー:\n{os.path.basename(absolute_image_path)}"); self.img_path_label.setText(f"画像パス(表示エラー): {relative_image_path}")
        elif relative_image_path:
            self._original_image_pixmap = None; preview_label.clear(); preview_label.setText(f"画像ファイル未発見:\n{relative_image_path}"); self.img_path_label.setText(f"画像パス(未発見): {relative_image_path}")
        else:
            self._original_image_pixmap = None; preview_label.clear(); preview_label.setText("画像プレビューなし"); self.img_path_label.setText("画像パス: (選択されていません)")
            preview_label.setMinimumHeight(150) # デフォルトの最小高さ
            preview_label.setMaximumHeight(16777215) # 最大高さ制限を解除
        
        # --- ★★★ 表示モード切替ボタンの有効/無効を設定 ★★★ ---
        if hasattr(self, 'toggle_image_mode_button'):
            self.toggle_image_mode_button.setEnabled(image_loaded_successfully)
            # もし画像がないのに背景モードだったら通常モードに戻す
            if not image_loaded_successfully and self._image_display_mode == "background":
                self.toggle_image_mode_button.setChecked(False) # これで _on_toggle_image_mode が呼ばれる

    def resizeEvent(self, event: 'QResizeEvent'):
        """ウィンドウがリサイズされたときに呼び出されるイベントハンドラ。
        画像プレビューを新しいウィンドウサイズに合わせて再スケーリングします。
        ラベルの高さもアスペクト比に合わせて調整します。
        """
        super().resizeEvent(event)
        
        if self._original_image_pixmap and 'image_preview' in self.detail_widgets:
            preview_label = self.detail_widgets['image_preview']
            if isinstance(preview_label, QLabel) and not self._original_image_pixmap.isNull():
                
                # --- ★★★ ラベルの現在のサイズに合わせてオリジナルをスケーリング ★★★ ---
                # setScaledContents(True) と組み合わせることで、ラベルのサイズ変更に追従する
                # ここでラベルの minimumHeight や maximumHeight を変更する必要はない
                # （_update_image_previewで設定したminimumHeightが効いているはず）
                
                # 非常に小さいサイズへのスケーリングを防ぐ（任意）
                if preview_label.width() <= 10 or preview_label.height() <= 10:
                    # print("Resize skipped due to too small label size.")
                    return

                scaled_pixmap = self._original_image_pixmap.scaled(
                    preview_label.size(), # QLabelの現在の描画領域サイズ
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                preview_label.setPixmap(scaled_pixmap)
                # print(f"Resized: Label size: {preview_label.size()}, Pixmap set.")

        # --- ★★★ 背景表示モードの場合、背景画像を再スケーリング ★★★ ---
        elif self._image_display_mode == "background" and \
             self._original_image_pixmap and \
             not self._original_image_pixmap.isNull():
            
            palette = self.palette()
            scaled_pixmap = self._original_image_pixmap.scaled(
                self.size(), # DetailWindowの新しいサイズ
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
            self.setPalette(palette)
            # self.update() # setPalette後、必要なら


    def add_history_entry_with_ai_ui(self):
        """「AIで履歴エントリを生成・追加」ボタンがクリックされたときの処理。
        `AIAssistedEditDialog` を履歴追記モードで開きます。
        """
        if not self.item_data or not self.current_category or not self.current_item_id or not self.current_project_dir_name:
            QMessageBox.warning(self, "エラー", "履歴を追加するアイテムが選択されていません。")
            return
        if self.ai_edit_dialog is not None and self.ai_edit_dialog.isVisible():
            self.ai_edit_dialog.activateWindow(); return

        # 履歴追記用のプロンプトテンプレートを生成
        item_name = self.item_data.get("name", "このアイテム")
        item_desc = self.item_data.get("description", "(説明なし)")
        recent_history = self.item_data.get("history", [])
        recent_history_str = "\n".join([f"- {h.get('entry', '')}" for h in recent_history[-3:]]) # 直近3件
        if not recent_history_str: recent_history_str = "(まだ履歴はありません)"

        instruction_template_history = (
            f"## 履歴自動追記支援\n\n"
            f"以下の情報とユーザーの具体的な出来事の説明に基づいて、キャラクター「{item_name}」の履歴に1行で追記する簡潔なエントリーを作成してください。"
            f"タイムスタンプは自動で付与されるため、エントリー内容のみを生成してください。\n\n"
            f"### 現在のキャラクター「{item_name}」の情報:\n"
            f"- 説明/メモ:\n{item_desc}\n"
            f"- 直近の履歴:\n{recent_history_str}\n\n"
            f"### ユーザーによる出来事の説明やAIへの指示:\n"
            f"[ここに具体的な出来事や、どのような視点で記録してほしいかなどを記述します。例:「NPCエルダとの会話で、古代遺跡の場所を聞き出した」「ゴブリンとの戦闘に辛くも勝利し、左腕を負傷した」など]\n\n"
            f"### 生成する履歴エントリーの提案 (1行):\n"
        )
        self.ai_edit_dialog_mode = "history" # モード設定
        self.ai_edit_dialog = AIAssistedEditDialog(
            initial_instruction_text=instruction_template_history,
            current_item_description="", # 履歴モードでは直接使わないが、引数は合わせる
            parent=self,
            window_title=f"AIによる「{item_name}」の履歴追記支援"
        )
        self.ai_edit_dialog.request_ai_button.clicked.connect(self._handle_ai_suggestion_request)

        if self.ai_edit_dialog.exec_() == QDialog.Accepted:
            final_history_entry_text = self.ai_edit_dialog.get_final_text().strip() # 前後の空白除去
            if final_history_entry_text: # 空でなければ追加
                if add_history_entry(self.current_project_dir_name, self.current_category, self.current_item_id, final_history_entry_text):
                    QMessageBox.information(self, "履歴追加完了", "新しい履歴エントリを追加しました。")
                    self.load_data(self.current_category, self.current_item_id) # UIを再読み込みして履歴を更新
                else:
                    QMessageBox.warning(self, "履歴追加エラー", "履歴エントリの追加に失敗しました。")
            else: # AIの提案が空か、ユーザーがクリアした場合
                QMessageBox.information(self, "履歴追加なし", "履歴エントリが空のため、追加されませんでした。")
        else:
            print("AIによる履歴追記はキャンセルされました。")
        self.ai_edit_dialog = None; self.ai_edit_dialog_mode = None # クリア

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

        # タグ
        if 'tags' in self.detail_widgets:
            tags_str = self.detail_widgets['tags'].text()
            new_tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            if set(new_tags_list) != set(self.item_data.get('tags', [])): # 順序無視で比較
                updated_data_payload['tags'] = new_tags_list
                changed_fields_count += 1

        # 画像パス (self.item_data['image_path'] は select_image_file/clear_image_file で直接更新済みのはず)
        # なので、ここでは保存前のローカルデータとの比較で変更を検知
        original_item_for_image_check = get_item(self.current_project_dir_name, self.current_category, self.current_item_id)
        if original_item_for_image_check and self.item_data.get('image_path') != original_item_for_image_check.get('image_path'): updated_data_payload['image_path'] = self.item_data.get('image_path'); changed_fields_count += 1



        # 履歴は add_history_entry_ui で個別に保存されるため、ここでは対象外

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

