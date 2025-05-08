# ui/detail_window.py

"""選択されたデータアイテムの詳細情報を表示・編集するためのウィンドウを提供します。

このモジュールは `DetailWindow` クラスを定義しており、アイテムの名前、説明、
履歴、タグ、画像などの属性をユーザーが確認・変更できるようにします。
また、AIによる説明文の編集支援機能も統合されています。
"""

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QScrollArea, QFrame, QFileDialog, QMessageBox, QDialog,
    QSizePolicy, QSpacerItem # QSpacerItem を追加
)
from PyQt5.QtGui import QPixmap, QImageReader # QImageReader を追加
from PyQt5.QtCore import Qt, pyqtSignal

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
    AIによる説明文の編集支援機能も呼び出せます。

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
        """AIAssistedEditDialog | None: AI編集支援ダイアログのインスタンス。"""

        self.setWindowFlags(Qt.Window) # 独立したウィンドウとして表示
        self.setWindowTitle("詳細情報 (アイテム未選択)")
        self.setMinimumWidth(450)
        self.setMinimumHeight(600) # 高さを確保

        self.init_ui()

    def init_ui(self):
        """UI要素を初期化し、レイアウトを設定します。"""
        main_layout = QVBoxLayout(self)

        # スクロールエリアのセットアップ
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # 横スクロールバーは常にオフ
        main_layout.addWidget(scroll_area)

        self.scroll_content_widget = QWidget() # スクロールされる中身のウィジェット
        self.content_layout = QVBoxLayout(self.scroll_content_widget)
        self.content_layout.setAlignment(Qt.AlignTop) # ウィジェットを上寄せ
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
        """`self.item_data` に基づいて詳細表示UIを動的に構築します。"""
        if not self.item_data:
            return

        # 名前 (QLineEdit)
        name_label = QLabel("名前:")
        name_edit = QLineEdit(self.item_data.get("name", ""))
        self.detail_widgets['name'] = name_edit
        self.content_layout.addWidget(name_label)
        self.content_layout.addWidget(name_edit)

        # 説明/メモ (QTextEdit と AI支援ボタン)
        desc_label = QLabel("説明/メモ:")
        desc_edit = QTextEdit(self.item_data.get("description", ""))
        desc_edit.setMinimumHeight(150) # ある程度の高さを確保
        desc_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.detail_widgets['description'] = desc_edit
        self.content_layout.addWidget(desc_label)
        self.content_layout.addWidget(desc_edit)

        ai_update_button = QPushButton("AIで「説明/メモ」を編集支援")
        ai_update_button.clicked.connect(self._on_ai_update_description_clicked)
        self.content_layout.addWidget(ai_update_button)


        # 履歴 (QTextEdit - 表示専用, 追加ボタン)
        history_label = QLabel("履歴:")
        history_view = QTextEdit()
        history_view.setReadOnly(True)
        history_text = "\n".join([f"[{h.get('timestamp', '日時不明')}] {h.get('entry', '')}"
                                  for h in self.item_data.get("history", [])])
        history_view.setPlainText(history_text if history_text else "履歴はありません。")
        history_view.setMinimumHeight(80)
        self.detail_widgets['history_view'] = history_view # 表示用なので保存対象外
        self.content_layout.addWidget(history_label)
        self.content_layout.addWidget(history_view)
        add_history_button = QPushButton("履歴を追加")
        add_history_button.clicked.connect(self.add_history_entry_ui)
        self.content_layout.addWidget(add_history_button)


        # タグ (QLineEdit - カンマ区切り)
        tags_label = QLabel("タグ (カンマ区切り):")
        tags_edit = QLineEdit(", ".join(self.item_data.get("tags", [])))
        self.detail_widgets['tags'] = tags_edit
        self.content_layout.addWidget(tags_label)
        self.content_layout.addWidget(tags_edit)


        # 画像 (QLabelでプレビュー, 選択/クリアボタン)
        img_section_layout = QHBoxLayout() # 画像関連を横に並べる
        img_label = QLabel("画像:")
        img_section_layout.addWidget(img_label)
        img_section_layout.addStretch()
        select_img_button = QPushButton("画像を選択")
        select_img_button.clicked.connect(self.select_image_file)
        clear_img_button = QPushButton("画像をクリア")
        clear_img_button.clicked.connect(self.clear_image_file)
        img_section_layout.addWidget(select_img_button)
        img_section_layout.addWidget(clear_img_button)
        self.content_layout.addLayout(img_section_layout)

        self.img_path_label = QLabel("画像パス: (選択されていません)") # 画像パス表示用
        self.img_path_label.setWordWrap(True)
        self.detail_widgets['image_path_display'] = self.img_path_label # 表示用
        self.content_layout.addWidget(self.img_path_label)

        self.img_preview_label = QLabel() # 画像プレビュー用
        self.img_preview_label.setAlignment(Qt.AlignCenter)
        self.img_preview_label.setMinimumSize(200, 150) # プレビューの最小サイズ
        self.img_preview_label.setFrameShape(QFrame.StyledPanel)
        self.detail_widgets['image_preview'] = self.img_preview_label # 表示用
        self._update_image_preview(self.item_data.get("image_path")) # 初期プレビュー更新
        self.content_layout.addWidget(self.img_preview_label)

        # 最後にスペーサーを追加して、コンテンツが上に詰まるようにする
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.content_layout.addSpacerItem(spacer)


    def _on_ai_update_description_clicked(self):
        """「AIで「説明/メモ」を編集支援」ボタンがクリックされたときの処理。"""
        if not self.item_data:
            QMessageBox.warning(self, "エラー", "編集対象のアイテムがロードされていません。")
            return
        if self.ai_edit_dialog is not None and self.ai_edit_dialog.isVisible():
            self.ai_edit_dialog.activateWindow() # 既に開いていればアクティブ化
            return

        current_description = self.detail_widgets.get('description').toPlainText()
        # AIへの指示テンプレート (より高度なものは設定ファイルなどからロードする)
        instruction_template = (
            f"以下の「現在の説明」を参考にしつつ、ユーザーの具体的な指示に従って、"
            f"「説明/メモ」欄の内容を更新または新規作成してください。\n\n"
            f"## 現在の説明:\n{current_description}\n\n"
            f"## ユーザーの指示:\n[ここに具体的な指示を記述してください。例えば、「より詳細な設定を追加して」「戦闘シーンを描写して」など]\n\n"
            f"## 更新後の「説明/メモ」の提案:\n"
        )

        self.ai_edit_dialog = AIAssistedEditDialog(
            initial_instruction_text=instruction_template,
            current_item_description=current_description, # 将来のAIコンテキスト用
            parent=self
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
            else:
                QMessageBox.warning(self, "保存エラー", "「説明/メモ」の更新内容の保存に失敗しました。")
        else: # キャンセルされた
            print("AIによる説明編集はキャンセルされました。")
        self.ai_edit_dialog = None # ダイアログインスタンスをクリア


    def _handle_ai_suggestion_request(self):
        """`AIAssistedEditDialog` からAI提案依頼があった場合の処理。"""
        if not self.ai_edit_dialog: return

        instruction_text = self.ai_edit_dialog.get_instruction_text()
        if not instruction_text.strip():
            QMessageBox.warning(self.ai_edit_dialog, "入力エラー", "AIへの指示を入力してください。")
            return

        ai_model_to_use = self.main_config.get("model", "gemini-1.5-pro-latest") # 設定からモデル取得
        print(f"DetailWindow: Requesting AI suggestion with model '{ai_model_to_use}'. Instruction length: {len(instruction_text)}")
        self.ai_edit_dialog.show_processing_message(True) # 処理中表示開始

        # --- ここで実際にAIにリクエストを送信する ---
        # (gemini_handler.py をインポートして使用)
        from core.gemini_handler import generate_response as call_gemini, is_configured as gemini_is_configured
        if not gemini_is_configured():
            QMessageBox.critical(self.ai_edit_dialog, "APIエラー", "Gemini APIが設定されていません。")
            self.ai_edit_dialog.show_processing_message(False)
            return

        ai_suggestion, error_msg = call_gemini(ai_model_to_use, instruction_text)
        self.ai_edit_dialog.show_processing_message(False) # 処理中表示終了

        if error_msg:
            QMessageBox.warning(self.ai_edit_dialog, "AI提案エラー", f"AIからの提案取得に失敗しました:\n{error_msg}")
        elif ai_suggestion:
            self.ai_edit_dialog.set_suggestion_text(ai_suggestion)
            QMessageBox.information(self.ai_edit_dialog, "提案取得完了", "AIからの提案を取得しました。必要に応じて編集してください。")
        else:
            QMessageBox.information(self.ai_edit_dialog, "提案なし", "AIから有効な提案がありませんでした。")


    def select_image_file(self):
        """「画像を選択」ボタンがクリックされたときの処理。ファイルダイアログを開きます。"""
        if not self.item_data: return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "画像ファイルを選択", "",
            "画像ファイル (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.item_data['image_path'] = file_path # ローカルデータにパスを保存
            self._update_image_preview(file_path)

    def clear_image_file(self):
        """「画像をクリア」ボタンがクリックされたときの処理。画像パスをクリアします。"""
        if not self.item_data: return
        self.item_data['image_path'] = None
        self._update_image_preview(None)

    def _update_image_preview(self, image_path: str | None):
        """指定された画像パスに基づいて画像プレビューを更新します。

        Args:
            image_path (str | None): 表示する画像のパス。Noneの場合はプレビューをクリア。
        """
        if 'image_preview' not in self.detail_widgets or 'image_path_display' not in self.detail_widgets:
            return

        if image_path and os.path.exists(image_path):
            try:
                # 画像サイズを制限して読み込む (QImageReader を使用)
                reader = QImageReader(image_path)
                if reader.canRead():
                    # プレビューラベルのサイズに合わせてリサイズ
                    preview_width = self.img_preview_label.width() - 10 # 少しマージン
                    preview_height = self.img_preview_label.height() - 10
                    if preview_width < 50: preview_width = 150 # 最小幅
                    if preview_height < 50: preview_height = 100 # 最小高さ

                    reader.setScaledSize(reader.size().scaled(preview_width, preview_height, Qt.KeepAspectRatio))
                    pixmap = QPixmap.fromImageReader(reader)

                    if not pixmap.isNull():
                        self.img_preview_label.setPixmap(pixmap)
                        self.img_path_label.setText(f"画像パス: {image_path}")
                    else:
                        self.img_preview_label.setText(f"画像プレビュー失敗:\n{reader.errorString()}")
                        self.img_path_label.setText(f"画像パス(読込エラー): {image_path}")
                else: # canRead() が False
                    self.img_preview_label.setText(f"画像形式非対応:\n{os.path.basename(image_path)}")
                    self.img_path_label.setText(f"画像パス(形式非対応): {image_path}")
            except Exception as e:
                print(f"Error updating image preview for {image_path}: {e}")
                self.img_preview_label.setText(f"画像表示エラー:\n{os.path.basename(image_path)}")
                self.img_path_label.setText(f"画像パス(表示エラー): {image_path}")
        else:
            self.img_preview_label.setText("画像プレビューなし")
            self.img_path_label.setText("画像パス: (選択されていません)")


    def add_history_entry_ui(self):
        """「履歴を追加」ボタンがクリックされたときの処理。入力ダイアログを表示します。"""
        if not self.current_item_id or not self.current_category or not self.current_project_dir_name:
            QMessageBox.warning(self, "エラー", "履歴を追加するアイテムが選択されていません。")
            return

        text, ok = QInputDialog.getText(self, "履歴追加", "新しい履歴エントリ:")
        if ok and text:
            if add_history_entry(self.current_project_dir_name, self.current_category, self.current_item_id, text):
                QMessageBox.information(self, "成功", "履歴エントリを追加しました。")
                # 表示を更新するために再度データを読み込むか、履歴部分だけを更新
                self.load_data(self.current_category, self.current_item_id) # 再読み込みが簡単
            else:
                QMessageBox.warning(self, "エラー", "履歴エントリの追加に失敗しました。")
        elif ok: # OK押したがテキストが空
            QMessageBox.warning(self, "入力エラー", "履歴内容を入力してください。")


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
        if self.item_data.get('image_path') != get_item(self.current_project_dir_name, self.current_category, self.current_item_id).get('image_path'):
             updated_data_payload['image_path'] = self.item_data.get('image_path') # self.item_dataは既に更新済み
             changed_fields_count += 1


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

    # --- テスト用のダミーデータと環境準備 ---
    test_project_name_detail = "detail_window_test_project"
    test_category_name_detail = "テストキャラ"
    test_item_id_detail = "char-test-001"

    # data_manager の関数を直接使うために、一時的にプロジェクトディレクトリとファイルを作成
    from core.config_manager import save_project_settings, DEFAULT_PROJECT_SETTINGS
    save_project_settings(test_project_name_detail, DEFAULT_PROJECT_SETTINGS.copy()) # プロジェクト設定も念のため

    from core.data_manager import create_category as dm_create_cat, add_item as dm_add_item
    dm_create_cat(test_project_name_detail, test_category_name_detail)
    dm_add_item(test_project_name_detail, test_category_name_detail, {
        "id": test_item_id_detail,
        "name": "テスト勇者",
        "description": "これはテスト用の勇者の説明です。\n複数行もOK。\n初期状態。",
        "history": [{"timestamp": "2024-01-01 10:00:00", "entry": "冒険を開始した"}],
        "tags": ["勇者", "テスト"],
        "image_path": None # テスト用に画像パスは最初はNone
    })
    # ------------------------------------

    # DetailWindow の作成と表示
    main_test_config = {"model": "gemini-1.5-flash-latest"} # AI提案機能用
    detail_win = DetailWindow(main_config=main_test_config, project_dir_name=test_project_name_detail)
    detail_win.load_data(test_category_name_detail, test_item_id_detail) # データをロード

    # シグナル接続テスト (コンソールに出力)
    detail_win.dataSaved.connect(
        lambda cat, iid: print(f"\n--- Signal: dataSaved received for Category='{cat}', ItemID='{iid}' ---")
    )
    detail_win.windowClosed.connect(
        lambda: print("\n--- Signal: windowClosed received ---")
    )

    detail_win.show()
    app_exit_code = app.exec_()

    # --- テスト後のクリーンアップ ---
    import shutil
    test_project_dir_to_remove = os.path.join("data", test_project_name_detail)
    if os.path.exists(test_project_dir_to_remove):
        print(f"\nCleaning up test project directory: {test_project_dir_to_remove}")
        shutil.rmtree(test_project_dir_to_remove)
    # -----------------------------

    sys.exit(app_exit_code)

