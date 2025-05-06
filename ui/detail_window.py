# ui/detail_window.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QScrollArea, QFormLayout, QFileDialog, QMessageBox, QApplication,
    QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint # QPoint も必要なら

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- core モジュールインポート ---
from core.data_manager import update_item, get_item, add_history_entry
from core.gemini_handler import generate_response, is_configured

# --- ui モジュールインポート ---
from ui.ai_text_edit_dialog import AITextEditDialog 

# ==============================================================================
# データ詳細ウィンドウ
# ==============================================================================
class DetailWindow(QWidget):
    # シグナル定義
    dataSaved = pyqtSignal(str, str) # category, item_id (保存が完了したことを通知)
    windowClosed = pyqtSignal()      # ウィンドウが閉じられたことを通知

    def __init__(self, parent=None):

        # 通常のウィンドウとして表示 (独立したウィンドウ)
        super().__init__(parent)

        # --- ★★★ MainWindow の config を受け取るための準備 ★★★ ---
        self.main_config = {} # メインウィンドウの設定を保持
        if parent and hasattr(parent, 'config'): # MainWindowインスタンスかチェック
             self.main_config = parent.config
        # ------------------------------------------------------
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
        # --- ★★★ MainWindow の config を更新 ★★★ ---
        if main_config_ref:
             self.main_config = main_config_ref
        # -----------------------------------------
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
        if not is_configured(): # Gemini API設定確認
             QMessageBox.warning(self, "API未設定", "Gemini APIが設定されていません。メイン画面の「設定」からAPIキーを入力してください。")
             return

        current_description = self.item_data.get('description', '')

        # ユーザーに指示を求める
        user_instruction, ok = QInputDialog.getMultiLineText(
            self,
            "AIへの指示",
            "現在の「説明/メモ」に対するAIへの指示を入力してください。\n"
            "例1: 「レベルが7になり、スキル『強打』を覚えたことを追記して。」\n"
            "例2: 「この内容を簡潔に要約して。」",
            "" # 初期値は空
        )

        if not ok or not user_instruction.strip():
            return # キャンセルまたは入力なし

        # AIに送信するプロンプトの準備
        # ここでは MainWindow の config を参照してモデル名を取得
        target_model_name = self.main_config.get("model", "gemini-1.5-pro-latest") # デフォルトも指定

        # プロンプトテンプレート
        prompt_template = (
            "あなたはTRPGのキャラクターシートを管理するアシスタントです。\n"
            "以下の「現在の説明/メモ」と「ユーザーの指示」に基づいて、新しい「説明/メモ」を作成してください。\n"
            "元の情報で重要なものが失われないように、かつユーザーの指示を正確に反映してください。\n\n"
            "現在の説明/メモ:\n"
            "--------------------\n"
            "{current_desc}\n"
            "--------------------\n\n"
            "ユーザーの指示:\n"
            "--------------------\n"
            "{instruction}\n"
            "--------------------\n\n"
            "新しい説明/メモ:\n"
        )
        final_prompt = prompt_template.format(current_desc=current_description, instruction=user_instruction)

        # メインウィンドウの応答表示エリアに処理中メッセージを表示（任意）
        main_window = self.parent() # 親ウィジェット(MainWindow)を取得
        if main_window and hasattr(main_window, 'response_display'):
             main_window.response_display.append("🤖 AIが説明/メモを編集中...")
        QApplication.processEvents() # UIの応答性を保つ

        # AIに送信
        print(f"--- Sending to AI for description update (Model: {target_model_name}) ---")
        # print(final_prompt) # デバッグ用にプロンプト全体を表示しても良い
        ai_response_text, error_message = generate_response(target_model_name, final_prompt)

        if error_message:
            QMessageBox.critical(self, "AIエラー", f"AIからの応答取得中にエラーが発生しました:\n{error_message}")
            if main_window and hasattr(main_window, 'response_display'):
                main_window.response_display.append(f"<font color='red'>AI処理エラー: {error_message}</font>")
            return
        if ai_response_text is None:
            QMessageBox.warning(self, "AI応答なし", "AIから有効な応答が得られませんでした。")
            if main_window and hasattr(main_window, 'response_display'):
                main_window.response_display.append("<font color='orange'>AI応答なし</font>")
            return

        # 結果確認ダイアログを表示
        edited_description = AITextEditDialog.get_ai_edited_text(
            self,
            current_description,
            ai_response_text,
            title="AIによる「説明/メモ」編集提案"
        )

        if edited_description is not None: # OKが押された
            # データを更新して保存
            update_payload = {'description': edited_description}
            if update_item(self.current_category, self.current_item_id, update_payload):
                QMessageBox.information(self, "更新完了", "「説明/メモ」を更新しました。")
                # ローカルデータと表示を更新
                self.item_data['description'] = edited_description
                # self.update_view() # load_data経由で更新されるか、シグナルで親に通知
                self.dataSaved.emit(self.current_category, self.current_item_id) # 親に通知
            else:
                QMessageBox.warning(self, "保存エラー", "「説明/メモ」の更新内容の保存に失敗しました。")
        else: # キャンセルされた
            if main_window and hasattr(main_window, 'response_display'):
                main_window.response_display.append("<i>AIによる説明/メモ編集はキャンセルされました。</i>")
    # -----------------------------------------


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

