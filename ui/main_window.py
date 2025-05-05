# ui/main_window.py

import sys
import os

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- PyQtインポート ---
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QTextBrowser, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView,
    QTabWidget, QApplication, QDialog, QSplitter, QFrame, QCheckBox,
    QSizePolicy, QStyle, qApp, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize

# --- coreモジュールインポート ---
from core.config_manager import load_config, save_config
from core.subprompt_manager import load_subprompts, save_subprompts

# --- uiモジュールインポート ---
from ui.settings_dialog import SettingsDialog
from ui.subprompt_dialog import SubPromptEditDialog
from ui.data_widget import DataManagementWidget     # データウィジェット

# --- Gemini API ハンドラー ---
from core.gemini_handler import configure_gemini_api, is_configured, generate_response


# ==============================================================================
# サブプロンプト項目用カスタムウィジェット
# ==============================================================================
class SubPromptItemWidget(QWidget):
    # シグナル定義 (変更なし)
    checkStateChanged = pyqtSignal(bool) # is_checked
    editRequested = pyqtSignal()      # 引数なし
    deleteRequested = pyqtSignal()    # 引数なし

    def __init__(self, name, is_checked=False, parent=None):
        super().__init__(parent)
        self.name = name

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(is_checked)
        # --- 修正: 接続先のメソッドをこれから定義する ---
        self.checkbox.stateChanged.connect(self._on_check_state_changed)
        layout.addWidget(self.checkbox)

        self.label = QLabel(name)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.label)

        self.edit_button = QPushButton()
        edit_icon = qApp.style().standardIcon(QStyle.SP_FileDialogContentsView)
        self.edit_button.setIcon(edit_icon)
        self.edit_button.setFixedSize(QSize(24, 24))
        self.edit_button.setToolTip("編集")
        self.edit_button.clicked.connect(self._on_edit_requested) # 接続先は定義済み
        layout.addWidget(self.edit_button)

        self.delete_button = QPushButton()
        delete_icon = qApp.style().standardIcon(QStyle.SP_TrashIcon)
        self.delete_button.setIcon(delete_icon)
        self.delete_button.setFixedSize(QSize(24, 24))
        self.delete_button.setToolTip("削除")
        self.delete_button.clicked.connect(self._on_delete_requested) # 接続先は定義済み
        layout.addWidget(self.delete_button)

        self.setLayout(layout)

    # --- ★★★ 追加: 接続先のメソッドを定義 ★★★ ---
    def _on_check_state_changed(self, state):
        """チェックボックスの状態が変わったら checkStateChanged シグナルを発行"""
        # QCheckBox.stateChanged は int (0, 1, 2) を送る
        is_checked = (state == Qt.Checked) # Qt.Checked は 2
        self.checkStateChanged.emit(is_checked) # bool 値を発行

    # --- _on_edit_requested, _on_delete_requested は変更なし ---
    def _on_edit_requested(self):
        self.editRequested.emit()

    def _on_delete_requested(self):
        self.deleteRequested.emit()

    # --- setChecked, isChecked, mousePressEvent は変更なし ---
    def setChecked(self, is_checked):
        self.checkbox.setChecked(is_checked)

    def isChecked(self):
        return self.checkbox.isChecked()

    def mousePressEvent(self, event):
        if not (self.edit_button.geometry().contains(event.pos()) or
                self.delete_button.geometry().contains(event.pos())):
             self.checkbox.toggle()


# ==============================================================================
# メインウィンドウクラス
# ==============================================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.subprompts = load_subprompts()
        self.gemini_configured = False
        self.checked_subprompts = {}
        # self.checked_data_items = {} # データアイテムのチェック状態は DataManagementWidget が持つ
        self.init_ui()
        self.configure_gemini()

    def init_ui(self):
        self.setWindowTitle("AI TRPG Master Tool")
        self.resize(900, 700)

        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # --- 左側エリア (変更なし) ---
        left_layout.addWidget(QLabel("ユーザーの発言・行動:"))
        self.user_input = QTextEdit()
        self.user_input.setPlaceholderText("プレイヤーとしての発言や行動を入力...")
        left_layout.addWidget(self.user_input, 3)
        self.send_button = QPushButton("AIに送信")
        self.send_button.clicked.connect(self.on_send_button_clicked)
        left_layout.addWidget(self.send_button)
        left_layout.addWidget(QLabel("AIの応答履歴:"))
        self.response_display = QTextBrowser()
        self.response_display.setPlaceholderText("ここにAIからの応答が表示されます...")
        self.response_display.setOpenExternalLinks(True)
        left_layout.addWidget(self.response_display, 7)

        # --- 右側エリア ---
        settings_button = QPushButton("設定")
        settings_button.clicked.connect(self.open_settings_dialog)
        right_layout.addWidget(settings_button)

        splitter = QSplitter(Qt.Vertical)
        right_layout.addWidget(splitter)

        # --- 1. 上部エリア (サブシステムプロンプト) ---
        subprompt_area = QWidget()
        subprompt_layout = QVBoxLayout(subprompt_area)
        subprompt_layout.setContentsMargins(0,0,0,0)
        subprompt_layout.addWidget(QLabel("サブシステムプロンプト (クリックで行選択/トグル):"))
        self.subprompt_tab_widget = QTabWidget()
        self.subprompt_lists = {}
        self.refresh_subprompt_tabs()
        subprompt_layout.addWidget(self.subprompt_tab_widget)
        self.add_subprompt_button = QPushButton("新しいサブプロンプトを追加")
        self.add_subprompt_button.clicked.connect(self.add_subprompt)
        subprompt_layout.addWidget(self.add_subprompt_button)

        # --- 2. 下部エリア (データ管理) ---
        self.data_management_widget = DataManagementWidget()
        # --- ★★★ シグナルを接続 ★★★ ---
        self.data_management_widget.addCategoryRequested.connect(self._handle_add_category_request)
        self.data_management_widget.addItemRequested.connect(self._handle_add_item_request)
        # self.data_management_widget.checkedItemsChanged.connect(self.handle_data_check_change)

        splitter.addWidget(subprompt_area)
        splitter.addWidget(self.data_management_widget)
        splitter.setSizes([300, 350])

        main_layout.addLayout(left_layout, 7)
        main_layout.addLayout(right_layout, 3)

    # --- ★★★ 追加: カテゴリ追加ダイアログ表示スロット ★★★ ---
    def _handle_add_category_request(self):
        category_name, ok = QInputDialog.getText(self, "カテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name:
            # 結果を data_management_widget に渡す
            self.data_management_widget.add_new_category_result(category_name)
        elif ok:
            QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")

    # --- ★★★ 追加: アイテム追加ダイアログ表示スロット ★★★ ---
    def _handle_add_item_request(self, category):
        item_name, ok = QInputDialog.getText(self, "アイテム追加", f"カテゴリ '{category}' に追加するアイテムの名前:")
        if ok and item_name:
            # 結果を data_management_widget に渡す
            self.data_management_widget.add_new_item_result(category, item_name)
        elif ok:
            QMessageBox.warning(self, "入力エラー", "アイテム名を入力してください。")

    # --- handle_data_check_change (データチェック変更時の処理 - 任意) ---
    # def handle_data_check_change(self, checked_data):
    #     print("Checked data items updated in MainWindow:", checked_data)
    #     # 必要ならここで何か処理

    # --- configure_gemini, open_settings_dialog (変更なし) ---
    def configure_gemini(self):
        api_key = self.config.get("api_key")
        if api_key:
            success, message = configure_gemini_api(api_key)
            if success:
                print(f"Gemini API設定完了 (Default Model: {self.config.get('model')})")
                self.gemini_configured = True
            else:
                self.response_display.append(f"<font color='red'><b>Gemini API設定エラー:</b> {message}</font>")
                print(f"Gemini API設定エラー: {message}")
                self.gemini_configured = False
        else:
            self.response_display.append("<font color='orange'>警告: APIキーが設定されていません。「設定」からAPIキーを入力してください。</font>")
            self.gemini_configured = False
            configure_gemini_api(None)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config = dialog.get_config()
            if save_config(self.config):
                 self.configure_gemini()
                 print("設定を保存しました。")
                 self.response_display.append("<i>設定を更新しました。</i>")


    # --- refresh_subprompt_tabs, _handle_subprompt_check_change (変更なし) ---
    def refresh_subprompt_tabs(self):
        # --- 修正: 比較対象のタブウィジェット名を修正 ---
        current_tab_text = None # 以前のタブ名を保持する変数
        current_tab_index = self.subprompt_tab_widget.currentIndex()
        if current_tab_index != -1:
             current_tab_text = self.subprompt_tab_widget.tabText(current_tab_index) # 以前のタブ名を取得

        # (クリア処理は変更なし)
        self.subprompt_tab_widget.clear()
        self.subprompt_lists.clear()
        # (カテゴリ取得、チェック状態初期化も変更なし)
        categories = sorted(self.subprompts.keys())
        if not categories:
             if "一般" not in self.subprompts:
                  self.subprompts["一般"] = {}
                  categories.append("一般")
             if save_subprompts(self.subprompts): print("デフォルトカテゴリ'一般'を作成しました。")
        self.checked_subprompts = {cat: self.checked_subprompts.get(cat, set()) for cat in categories}

        new_tab_index = -1 # 再度選択するためのインデックス
        for i, category in enumerate(categories):
            list_widget = QListWidget()
            self.subprompt_lists[category] = list_widget
            checked_names = self.checked_subprompts.get(category, set())
            subprompt_names = sorted(self.subprompts[category].keys())
            for name in subprompt_names:
                is_checked = name in checked_names
                item = QListWidgetItem(list_widget)
                item_widget = SubPromptItemWidget(name, is_checked)
                # (シグナル接続は変更なし)
                item_widget.checkStateChanged.connect(
                    lambda checked_state, current_name=name, current_category=category: \
                        self._handle_subprompt_check_change(current_category, current_name, checked_state)
                )
                item_widget.editRequested.connect(
                    lambda current_name=name, current_category=category: self.edit_subprompt(current_category, current_name)
                )
                item_widget.deleteRequested.connect(
                    lambda current_name=name, current_category=category: self.delete_subprompt(current_category, [current_name])
                )
                item.setSizeHint(item_widget.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, item_widget)

            self.subprompt_tab_widget.addTab(list_widget, category)
            # --- ★★★ 修正箇所 ★★★ ---
            if category == current_tab_text: # 保存しておいた以前のタブテキストと比較
                new_tab_index = i # 一致したらインデックスを保持
            # --------------------------

        # (タブインデックス復元は変更なし)
        if new_tab_index != -1:
             self.subprompt_tab_widget.setCurrentIndex(new_tab_index)
        elif self.subprompt_tab_widget.count() > 0:
             self.subprompt_tab_widget.setCurrentIndex(0)

    def _handle_subprompt_check_change(self, category, name, is_checked):
        print(f"Subprompt Check changed: Category='{category}', Name='{name}', Checked={is_checked}")
        if category not in self.subprompts: return
        if category not in self.checked_subprompts: self.checked_subprompts[category] = set()
        try:
            if is_checked: self.checked_subprompts[category].add(name)
            else: self.checked_subprompts[category].discard(name)
        except KeyError: self.checked_subprompts[category] = set()
        print(f"Updated checked_subprompts: {self.checked_subprompts}")

    # --- on_send_button_clicked (データアイテムのプロンプト組み込み追加) ---
    def on_send_button_clicked(self):
        if not is_configured():
             QMessageBox.warning(self, "API未設定", "Gemini APIが設定されていません。「設定」からAPIキーを入力してください。")
             return
        user_text = self.user_input.toPlainText().strip()
        if not user_text:
            self.response_display.append("<font color='orange'>ユーザーの発言・行動を入力してください。</font>")
            return

        final_prompt = ""
        target_model_name = self.config.get("model")
        target_api_key = self.config.get("api_key")
        main_system_prompt = self.config.get("main_system_prompt", "")
        prompt_parts = []
        if main_system_prompt: prompt_parts.append(main_system_prompt)

        # --- サブプロンプトの収集 (変更なし) ---
        selected_subprompts_info = []
        current_sub_tab_index = self.subprompt_tab_widget.currentIndex()
        if current_sub_tab_index != -1:
            current_sub_category = self.subprompt_tab_widget.tabText(current_sub_tab_index)
            checked_sub_names = self.checked_subprompts.get(current_sub_category, set())
            if checked_sub_names:
                for name in sorted(list(checked_sub_names)):
                    sub_data = self.subprompts.get(current_sub_category, {}).get(name)
                    if sub_data:
                        content = sub_data.get("content", "")
                        if content: prompt_parts.append(content)
                        if sub_data.get("model"): target_model_name = sub_data["model"]
                        selected_subprompts_info.append(name)

        # --- ★データアイテムの収集とプロンプトへの組み込み ---
        checked_data_items_dict = self.data_management_widget.get_checked_items()
        selected_data_items_info = [] # 表示用
        data_prompt_parts = [] # データアイテム用のプロンプト部品リスト

        for category, checked_ids in checked_data_items_dict.items():
            if checked_ids:
                 category_header = f"--- {category} 情報 ---" # カテゴリ名をヘッダーに
                 data_prompt_parts.append(category_header)
                 for item_id in sorted(list(checked_ids)):
                      item_data = get_item(category, item_id) # data_manager から取得
                      if item_data:
                           # プロンプトに含める情報を選択・整形
                           # ここでは例として名前と説明を含める
                           item_str = f"名前: {item_data.get('name', 'N/A')}\n説明/メモ:\n{item_data.get('description', '')}"
                           # TODO: タグ、履歴なども必要に応じて含める
                           # TODO: AIが情報を区別しやすいようにフォーマットを工夫する
                           data_prompt_parts.append(item_str)
                           selected_data_items_info.append(f"{category}:{item_data.get('name', item_id)}") # 表示用に追加
                 data_prompt_parts.append("---") # カテゴリの終わりを示す

        # データアイテム情報をサブプロンプトの後に追加
        if data_prompt_parts:
             prompt_parts.extend(data_prompt_parts)

        # --- ユーザー入力を追加 (変更なし) ---
        prompt_parts.append(user_text)
        final_prompt = "\n\n".join(prompt_parts) # 区切り文字を変更 (任意)

        # (デバッグ出力、API呼び出し、応答表示はほぼ変更なし)
        print("--- 送信するプロンプト ---")
        print(f"使用モデル: {target_model_name}")
        print(final_prompt)
        print("-------------------------")

        self.response_display.append("🤖 AIに送信中...")
        QApplication.processEvents()
        try:
            response_text, error_message = generate_response(target_model_name, final_prompt)
            if error_message:
                self.response_display.append(f"<font color='red'>\n--- APIエラー ---</font>")
                self.response_display.append(f"{error_message}")
                print(f"API Error: {error_message}")
            elif response_text is not None:
                self.response_display.append("---")
                self.response_display.append(f"👤 あなた: {user_text}\n")
                # 使用したサブシステムとデータアイテムを表示
                used_info = []
                if selected_subprompts_info: used_info.append(f"サブ: {', '.join(selected_subprompts_info)}")
                if selected_data_items_info: used_info.append(f"データ: {', '.join(selected_data_items_info)}")
                if used_info: self.response_display.append(f"<small><i>（使用情報: {'; '.join(used_info)}）</i></small><br>")

                self.response_display.append(f"🤖 AI: {response_text}")
            else:
                 self.response_display.append(f"<font color='red'>\n--- 不明なエラー ---</font>")
                 self.response_display.append("APIから応答もエラーも返されませんでした。")
                 print("API Error: Unknown response from generate_response")
        except Exception as e:
            self.response_display.append(f"<font color='red'>\n--- 予期せぬエラー ---</font>")
            self.response_display.append(f"API呼び出し処理中に予期せぬエラーが発生しました: {e}")
            print(f"Unexpected Error during API call: {e}")
        self.response_display.verticalScrollBar().setValue(self.response_display.verticalScrollBar().maximum())


    # --- サブプロンプト追加/編集/削除メソッド (変更なし) ---
    def add_subprompt(self):
        current_category = None
        current_index = self.subprompt_tab_widget.currentIndex()
        if current_index != -1: current_category = self.subprompt_tab_widget.tabText(current_index)
        categories = list(self.subprompts.keys())
        dialog = SubPromptEditDialog(categories, current_category=current_category, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            result = dialog.get_data()
            if result:
                category = result['category']
                name = result['name']
                data = result['data']
                if category not in self.subprompts: self.subprompts[category] = {}
                if name in self.subprompts[category]:
                     QMessageBox.warning(self, "名前の重複", f"カテゴリ '{category}' には既に '{name}' という名前のサブプロンプトが存在します。")
                     return
                self.subprompts[category][name] = data
                if save_subprompts(self.subprompts):
                    self.refresh_subprompt_tabs()
                    print(f"サブプロンプト '{name}' をカテゴリ '{category}' に追加しました。")

    def edit_subprompt(self, category, name):
        print(f"Editing Subprompt: Category='{category}', Name='{name}'")
        subprompt_data_to_edit = self.subprompts.get(category, {}).get(name)
        if not subprompt_data_to_edit:
             QMessageBox.critical(self, "エラー", f"編集対象のデータ ('{category}'/'{name}') が見つかりません。")
             return
        edit_data = subprompt_data_to_edit.copy()
        edit_data['name'] = name
        categories = list(self.subprompts.keys())
        dialog = SubPromptEditDialog(categories, current_category=category, subprompt_data=edit_data, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            result = dialog.get_data()
            if result:
                new_category = result['category']
                new_name = result['name']
                new_data = result['data']
                original_category = result['original_category']
                original_name = result['original_name']
                needs_delete_old = (new_category != original_category) or (new_name != original_name)
                if new_category not in self.subprompts: self.subprompts[new_category] = {}
                if new_name in self.subprompts.get(new_category, {}) and needs_delete_old:
                    QMessageBox.warning(self, "名前の重複", f"カテゴリ '{new_category}' には既に '{new_name}' という名前のサブプロンプトが存在します。")
                    return
                if needs_delete_old and original_category in self.checked_subprompts:
                     self.checked_subprompts[original_category].discard(original_name)
                self.subprompts[new_category][new_name] = new_data
                if needs_delete_old:
                    if original_category in self.subprompts and original_name in self.subprompts[original_category]:
                         del self.subprompts[original_category][original_name]
                         if not self.subprompts[original_category]:
                              del self.subprompts[original_category]
                              if original_category in self.checked_subprompts: del self.checked_subprompts[original_category]
                if new_category in self.checked_subprompts: self.checked_subprompts[new_category].discard(new_name)
                if save_subprompts(self.subprompts):
                    self.refresh_subprompt_tabs()
                    print(f"サブプロンプト '{original_name}' を編集しました (新しい名前/カテゴリ: '{new_name}'/'{new_category}')。")

    def edit_subprompt_on_doubleclick(self, item):
        list_widget = self.sender()
        item_widget = list_widget.itemWidget(item)
        if isinstance(item_widget, SubPromptItemWidget):
             current_index = self.subprompt_tab_widget.currentIndex()
             if current_index != -1:
                  category = self.subprompt_tab_widget.tabText(current_index)
                  self.edit_subprompt(category, item_widget.name)
             else: print("Error: Could not determine current category on double click.")

    def delete_subprompt(self, category, names_to_delete):
        if not names_to_delete: return
        names_str = ", ".join(names_to_delete)
        reply = QMessageBox.question(self, '削除確認',
                                   f"カテゴリ '{category}' のサブプロンプト:\n'{names_str}'\nを削除しますか？",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            deleted_count = 0
            if category in self.subprompts:
                for name in names_to_delete:
                    if name in self.subprompts[category]:
                        del self.subprompts[category][name]
                        if category in self.checked_subprompts: self.checked_subprompts[category].discard(name)
                        deleted_count += 1
                if not self.subprompts[category]:
                    del self.subprompts[category]
                    if category in self.checked_subprompts: del self.checked_subprompts[category]
                    print(f"カテゴリ '{category}' が空になったため削除しました。")
                if deleted_count > 0:
                    if save_subprompts(self.subprompts):
                        self.refresh_subprompt_tabs()
                        print(f"{deleted_count}個のサブプロンプトをカテゴリ '{category}' から削除しました。")

# --- アプリケーション起動部分 (main.py に移動済み) ---

