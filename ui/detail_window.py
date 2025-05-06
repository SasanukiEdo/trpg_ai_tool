# ui/detail_window.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QScrollArea, QFormLayout, QFileDialog, QMessageBox, QApplication,
    QInputDialog, QDialog # <<< QDialog をインポートリストに追加
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- core モジュールインポート ---
from core.data_manager import update_item, get_item, add_history_entry
from core.gemini_handler import generate_response, is_configured

# --- ui モジュールインポート ---
from ui.ai_text_edit_dialog import AIAssistedEditDialog

# ==============================================================================
# データ詳細ウィンドウ
# ==============================================================================
class DetailWindow(QWidget):
    # シグナル定義
    dataSaved = pyqtSignal(str, str) # category, item_id (保存が完了したことを通知)
    windowClosed = pyqtSignal()      # ウィンドウが閉じられたことを通知

    def __init__(self, main_config=None, parent=None):
        super().__init__(parent)
        self.main_config = main_config if main_config is not None else {} # メイン設定を保持
        
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("詳細情報")
        self.setMinimumWidth(400)

        self.current_category = None
        self.current_item_id = None
        self.item_data = None

        # --- メインレイアウト ---
        main_layout = QVBoxLayout(self)

        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        self.detail_widget = QWidget()
        scroll_area.setWidget(self.detail_widget)

        self.detail_layout = QFormLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(10, 10, 10, 10)

        self.detail_widgets = {} # ウィジェット参照

        # --- AI編集ボタン用のレイアウト ---
        self.ai_edit_button_layout = QHBoxLayout() # 後でウィジェットを追加

        # 初期状態のメッセージ
        self.detail_layout.addRow(QLabel("データ管理タブでアイテムを選択してください"))

        # 保存ボタンをウィンドウ下部に配置
        self.save_button = QPushButton("変更を保存")
        self.save_button.clicked.connect(self.save_details)
        self.save_button.setEnabled(False) # 初期状態は無効
        main_layout.addWidget(self.save_button)


    def load_data(self, category, item_id):
        """指定されたアイテムのデータを読み込んで表示"""
        self.clear_view()
        print(f"DetailWindow: Loading data for Category='{category}', ID='{item_id}'")
        item_data_loaded = get_item(category, item_id) # 変数名変更
        if not item_data_loaded:
            QMessageBox.warning(self, "エラー", f"アイテム (ID: {item_id}) のデータの読み込みに失敗しました。")
            return
        self.current_category = category
        self.current_item_id = item_id
        self.item_data = item_data_loaded.copy()
        self.setWindowTitle(f"詳細: {self.item_data.get('name', 'N/A')} ({category})")
        self.update_view()
        self.save_button.setEnabled(True)

    def clear_view(self):
        """表示内容をクリア (レイアウトからウィジェットを削除するだけ)"""
        while self.detail_layout.count():
            self.detail_layout.removeRow(0)
        self.detail_widgets = {}
        self.setWindowTitle("詳細情報")
        self.current_category = None
        self.current_item_id = None
        self.item_data = None
        self.save_button.setEnabled(False)

    def update_view(self):
        """現在の item_data に基づいてUIを更新"""
        print("DetailWindow: Updating view...")
        while self.detail_layout.rowCount() > 0:
            self.detail_layout.removeRow(0)
        self.detail_widgets = {}

        if not self.item_data:
             print("  No item data to display. Adding placeholder.")
             self.detail_layout.addRow(QLabel("データ管理タブでアイテムを選択してください"))
             return

        print(f"  Displaying data for ID: {self.item_data.get('id')}")
        # ID
        id_label = QLineEdit(self.item_data.get('id', 'N/A'))
        id_label.setReadOnly(True)
        self.detail_layout.addRow("ID:", id_label)
        self.detail_widgets['id'] = id_label
        # 名前
        name_edit = QLineEdit(self.item_data.get('name', ''))
        self.detail_layout.addRow("名前:", name_edit)
        self.detail_widgets['name'] = name_edit

        # 説明/メモ
        desc_edit = QTextEdit(self.item_data.get('description', ''))
        desc_edit.setMinimumHeight(150)
        self.detail_layout.addRow("説明/メモ:", desc_edit)
        self.detail_widgets['description'] = desc_edit

        # --- ★★★ 「AIで編集」ボタンを説明/メモの下に追加 ★★★ ---
        ai_button_layout = QHBoxLayout()
        self.ai_update_desc_button = QPushButton("AIで説明/メモを編集...")
        self.ai_update_desc_button.clicked.connect(self._on_ai_update_description_clicked)
        ai_button_layout.addStretch() # ボタンを右寄せ（または中央寄せなど）
        ai_button_layout.addWidget(self.ai_update_desc_button)
        self.detail_layout.addRow("", ai_button_layout) # ラベルなしで行追加
        # ----------------------------------------------------

        # タグ
        tags_str = ", ".join(self.item_data.get('tags', []))
        tags_edit = QLineEdit(tags_str)
        self.detail_layout.addRow("タグ (カンマ区切り):", tags_edit)
        self.detail_widgets['tags'] = tags_edit

        # 画像
        img_layout = QHBoxLayout()
        self.img_path_label = QLabel(self.item_data.get('image_path') or "未設定")
        self.img_path_label.setWordWrap(True)
        select_img_button = QPushButton("画像選択...")
        select_img_button.clicked.connect(self.select_image_file)
        clear_img_button = QPushButton("クリア")
        clear_img_button.clicked.connect(self.clear_image_file)
        img_layout.addWidget(self.img_path_label, 1)
        img_layout.addWidget(select_img_button)
        img_layout.addWidget(clear_img_button)
        self.detail_layout.addRow("画像ファイル:", img_layout)
        self.detail_widgets['image_path'] = self.img_path_label

        # 履歴
        history_text = ""
        history_list = self.item_data.get('history', [])
        for entry in reversed(history_list):
             ts = entry.get('timestamp', '')
             txt = entry.get('entry', '')
             history_text += f"[{ts}] {txt}\n"
        history_display = QTextEdit(history_text)
        history_display.setReadOnly(True)
        history_display.setMinimumHeight(100)
        add_history_button = QPushButton("履歴を追加...")
        add_history_button.clicked.connect(self.add_history_entry_ui)
        history_layout = QVBoxLayout()
        history_layout.addWidget(history_display)
        history_layout.addWidget(add_history_button)
        self.detail_layout.addRow("履歴:", history_layout)

        print("DetailWindow: View updated.")


    # --- ★★★ AIによる説明/メモ編集処理 ★★★ ---
    def _on_ai_update_description_clicked(self):
        if not self.item_data:
            QMessageBox.warning(self, "エラー", "編集対象のデータがありません。")
            return
        if not is_configured():
             QMessageBox.warning(self, "API未設定", "Gemini APIが設定されていません。メイン画面の「設定」からAPIキーを入力してください。")
             return

        current_description = self.item_data.get('description', '')
        user_instruction_placeholder = "[ここに具体的な指示を記述してください (例: レベルアップして新しいスキルを覚えたことを追記)]"

        # 初期指示テキストの準備 (プロンプトテンプレート)
        initial_instruction_template = (
            "あなたはTRPGのデータ管理を行うアシスタントです。\n"
            "以下の「現在の説明/メモ」に基づいて、現在の状況を考慮して新しい「説明/メモ」を作成してください。\n"
            "元の情報で重要なものが失われないようにし、説明/メモ以外の余計な情報は出力しないようにしてください。\n\n"
            "現在の説明/メモ:\n"
            "--------------------\n"
            "{current_desc}\n"
            "--------------------\n\n"
        )
        initial_instruction_text_for_dialog = initial_instruction_template.format(
            current_desc=current_description,
            instruction_placeholder=user_instruction_placeholder
        )

        # --- ★★★ 新しいAI支援編集ダイアログを使用 ★★★ ---
        self.ai_edit_dialog = AIAssistedEditDialog( # インスタンスを保持
            initial_instruction_text_for_dialog,
            current_description, # 現在のアイテム説明も渡す
            self, # 親ウィジェット
            window_title="AIによる「説明/メモ」編集支援"
        )
        # 「AIに提案を依頼」ボタンが押されたときの処理を接続
        self.ai_edit_dialog.request_ai_button.clicked.connect(self._handle_ai_suggestion_request)

        if self.ai_edit_dialog.exec_() == QDialog.Accepted: # ダイアログでOKが押された
            final_edited_text = self.ai_edit_dialog.get_final_text()
            # データを更新して保存
            update_payload = {'description': final_edited_text}
            if update_item(self.current_category, self.current_item_id, update_payload):
                QMessageBox.information(self, "更新完了", "「説明/メモ」を更新しました。")
                self.item_data['description'] = final_edited_text
                if 'description' in self.detail_widgets:
                    self.detail_widgets['description'].setPlainText(final_edited_text)
                self.dataSaved.emit(self.current_category, self.current_item_id)
            else:
                QMessageBox.warning(self, "保存エラー", "「説明/メモ」の更新内容の保存に失敗しました。")
        else: # キャンセルされた
            main_window = self.parent()
            if main_window and hasattr(main_window, 'response_display'):
                main_window.response_display.append("<i>AIによる説明/メモ編集はキャンセルされました。</i>")
        self.ai_edit_dialog = None # 参照をクリア
        # ----------------------------------------------------------


    def _handle_ai_suggestion_request(self):
        """AIAssistedEditDialog内の「AIに提案を依頼」ボタンが押されたときの処理"""
        if not self.ai_edit_dialog: return # ダイアログが存在しない場合は何もしない

        user_instruction_text = self.ai_edit_dialog.get_instruction_text()
        if not user_instruction_text.strip():
            QMessageBox.warning(self.ai_edit_dialog, "指示なし", "AIへの指示を入力してください。")
            return

        self.ai_edit_dialog.show_processing_message(True) # 処理中表示ON

        target_model_name = self.main_config.get("model", "gemini-1.5-pro-latest")
        # final_prompt はユーザーが編集した指示テキストそのものを使う
        # (末尾に "新しい説明/メモ:\n" を付けるのは generate_response 側で考慮するか、ここで付加)
        final_prompt_for_ai = user_instruction_text + "\n\n新しい説明/メモ:\n"

        print(f"--- Sending to AI for description update (Model: {target_model_name}) ---")
        # print(final_prompt_for_ai)
        ai_response_text, error_message = generate_response(target_model_name, final_prompt_for_ai)
        self.ai_edit_dialog.show_processing_message(False) # 処理中表示OFF

        if error_message:
            QMessageBox.critical(self.ai_edit_dialog, "AIエラー", f"AIからの応答取得中にエラーが発生しました:\n{error_message}")
            self.ai_edit_dialog.set_suggestion_text(f"エラー: {error_message}") # エラーも表示
            return
        if ai_response_text is None:
            QMessageBox.warning(self.ai_edit_dialog, "AI応答なし", "AIから有効な応答が得られませんでした。")
            self.ai_edit_dialog.set_suggestion_text("AIから有効な応答が得られませんでした。")
            return

        # AIの提案をダイアログの下部テキストエリアに表示
        self.ai_edit_dialog.set_suggestion_text(ai_response_text)


    def select_image_file(self):
        """画像ファイル選択"""
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        fileName, _ = QFileDialog.getOpenFileName(self, "画像ファイルを選択", "",
                                                  "画像ファイル (*.png *.jpg *.jpeg *.bmp *.gif);;すべてのファイル (*)", options=options)
        if fileName:
            try:
                 project_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                 relative_path = os.path.relpath(fileName, project_root_dir)
                 if ".." in relative_path and os.path.isabs(fileName):
                     self.img_path_label.setText(fileName)
                 else:
                     self.img_path_label.setText(relative_path.replace("\\", "/"))
            except ValueError:
                 self.img_path_label.setText(fileName)

    def clear_image_file(self):
        """画像パスをクリア"""
        self.img_path_label.setText("未設定")

    def add_history_entry_ui(self):
         """履歴追加"""
         if not self.current_category or not self.current_item_id: return
         entry_text, ok = QMessageBox.getText(self, "履歴追加", "追加する履歴を入力:")
         if ok and entry_text:
              if add_history_entry(self.current_category, self.current_item_id, entry_text):
                   # 成功したらデータを再読み込みして表示更新
                   self.load_data(self.current_category, self.current_item_id)
              else:
                   QMessageBox.warning(self, "エラー", "履歴の追加に失敗しました。")
         elif ok:
              QMessageBox.warning(self, "入力エラー", "履歴を入力してください。")

    def save_details(self):
        """変更を保存する"""
        if not self.current_category or not self.current_item_id:
            QMessageBox.warning(self, "保存エラー", "保存対象のアイテムが選択されていません。")
            return

        updated_data = {}
        try:
            # ウィジェットから値を取得 (DataManagementWidget.save_item_details と同様)
            updated_data['name'] = self.detail_widgets['name'].text()
            updated_data['description'] = self.detail_widgets['description'].toPlainText()
            tags_str = self.detail_widgets['tags'].text()
            updated_data['tags'] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            img_path_text = self.detail_widgets['image_path'].text()
            updated_data['image_path'] = img_path_text if img_path_text != "未設定" else None
            # id, category, history はここでは更新しない

            # 更新処理実行
            if update_item(self.current_category, self.current_item_id, updated_data):
                QMessageBox.information(self, "保存完了", "変更を保存しました。")
                # 保存成功シグナルを発行
                self.dataSaved.emit(self.current_category, self.current_item_id)
                # 保存後もウィンドウは閉じない（ユーザーが閉じるまで）
                # 保存したデータで表示を更新（任意）
                self.item_data.update(updated_data) # ローカルのデータも更新
            else:
                QMessageBox.warning(self, "保存エラー", "変更の保存に失敗しました。")

        except KeyError as e:
             print(f"保存エラー: 必要なウィジェットが見つかりません。キー: {e}")
             QMessageBox.critical(self, "内部エラー", f"保存に必要なUI要素が見つかりませんでした。\nキー: {e}")
        except Exception as e:
             print(f"保存エラー: 予期せぬエラーが発生しました: {e}")
             QMessageBox.critical(self, "内部エラー", f"保存中に予期せぬエラーが発生しました:\n{e}")


    def closeEvent(self, event):
        """ウィンドウが閉じられたときのイベント"""
        print("DetailWindow closed")
        self.windowClosed.emit() # ウィンドウが閉じたことを通知
        event.accept() # 閉じるイベントを受け入れる

