# ui/detail_window.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QScrollArea, QFormLayout, QFileDialog, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- core モジュールインポート ---
# update_item や get_item は DataManagementWidget 経由で呼び出す方が良いかも
from core.data_manager import update_item, get_item, add_history_entry

# ==============================================================================
# データ詳細ウィンドウ
# ==============================================================================
class DetailWindow(QWidget):
    # シグナル定義
    dataSaved = pyqtSignal(str, str) # category, item_id (保存が完了したことを通知)
    windowClosed = pyqtSignal()      # ウィンドウが閉じられたことを通知

    def __init__(self, parent=None):
        super().__init__(parent)
        # 通常のウィンドウとして表示 (独立したウィンドウ)
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("詳細情報")
        
        # self.setGeometry(100, 100, 500, 600) # --- 削除: 固定のsetGeometryを削除 ---
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

        # 初期状態のメッセージ
        self.detail_layout.addRow(QLabel("データ管理タブでアイテムを選択してください"))

        # 保存ボタンをウィンドウ下部に配置 (任意)
        self.save_button = QPushButton("変更を保存")
        self.save_button.clicked.connect(self.save_details)
        self.save_button.setEnabled(False) # 初期状態は無効
        main_layout.addWidget(self.save_button)

        # --- 追加: 最小幅を設定 (任意) ---
        self.setMinimumWidth(400)


    def load_data(self, category, item_id):
        """指定されたアイテムのデータを読み込んで表示"""
        print(f"DetailWindow: Loading data for Category='{category}', ID='{item_id}'")

        item_data = get_item(category, item_id)
        if not item_data:
            QMessageBox.warning(self, "エラー", f"アイテム (ID: {item_id}) のデータの読み込みに失敗しました。")
            # エラー時は明示的にクリアを呼ぶ（任意）
            self.clear_view()
            return

        self.current_category = category
        self.current_item_id = item_id
        self.item_data = item_data.copy()

        self.setWindowTitle(f"詳細: {self.item_data.get('name', 'N/A')} ({category})")
        self.update_view() # ★ ここでUIがクリアされ、新しい内容が表示される
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
        # 古いウィジェットをクリア
        while self.detail_layout.count():
            self.detail_layout.removeRow(0)
        self.detail_widgets = {}

        if not self.item_data:
             # ★ データがない場合のメッセージ表示
             self.detail_layout.addRow(QLabel("データ管理タブでアイテムを選択してください"))
             return

        # --- ウィジェット生成 (DataManagementWidget.display_item_details と同様) ---
        # ID (読み取り専用)
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

