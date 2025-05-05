# ui/data_widget.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QTabWidget, QMessageBox, QInputDialog, QListWidgetItem,
    QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- core モジュールインポート ---
from core.data_manager import (
    list_categories, list_items, get_item, add_item, update_item, delete_item,
    create_category, load_data_category
)
# --- ui モジュールインポート ---
from ui.detail_window import DetailWindow
from ui.data_item_widget import DataItemWidget

# ==============================================================================
# データ管理ウィジェット (タブ形式 + 別ウィンドウ詳細)
# ==============================================================================
class DataManagementWidget(QWidget):
    checkedItemsChanged = pyqtSignal(dict)
    # ★★★ カテゴリ追加/アイテム追加要求シグナルを追加 ★★★
    addCategoryRequested = pyqtSignal()
    addItemRequested = pyqtSignal(str) # category

    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_item_lists = {}
        self.checked_data_items = {}
        self._detail_window = None
        self._last_detail_item = {"category": None, "id": None}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- 上部: カテゴリ操作ボタン ---
        category_button_layout = QHBoxLayout()
        self.add_category_button = QPushButton("カテゴリ追加")
        # --- ★★★ QInputDialogではなくシグナルを発行 ★★★
        self.add_category_button.clicked.connect(self.addCategoryRequested.emit)
        category_button_layout.addWidget(self.add_category_button)
        category_button_layout.addStretch()
        main_layout.addLayout(category_button_layout)

        # --- 中央: カテゴリタブ ---
        self.category_tab_widget = QTabWidget()
        self.category_tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.category_tab_widget)

        # --- 下部: アイテム操作ボタン ---
        item_button_layout = QHBoxLayout()
        self.add_item_button = QPushButton("アイテム追加")
        # --- ★★★ QInputDialogではなくシグナルを発行 ★★★
        self.add_item_button.clicked.connect(self._request_add_item)
        self.delete_checked_items_button = QPushButton("チェックしたアイテムを削除")
        self.delete_checked_items_button.clicked.connect(self.delete_checked_items)
        item_button_layout.addWidget(self.add_item_button)
        item_button_layout.addWidget(self.delete_checked_items_button)
        item_button_layout.addStretch()
        main_layout.addLayout(item_button_layout)

        # --- 初期化 ---
        self.refresh_categories_and_tabs() # 初回読み込み
        self.ensure_detail_window_exists()

    # --- カテゴリとタブの管理 ---
    def refresh_categories_and_tabs(self):
        """カテゴリ一覧を読み込み、タブを再構築し、各リストを更新する"""
        self.category_tab_widget.blockSignals(True) # シグナルブロック開始

        current_tab_text = self.category_tab_widget.tabText(self.category_tab_widget.currentIndex())
        print(f"\n--- DEBUG: Refreshing categories and tabs. Previous tab: '{current_tab_text}' ---")

        self.category_item_lists.clear()
        print(f"  Cleared self.category_item_lists.")
        self.category_tab_widget.clear()
        print(f"  Cleared tabs.")

        categories = list_categories()
        print(f"  Loaded categories from data_manager: {categories}")
        if not categories:
             if create_category("未分類"):
                  categories.append("未分類")
                  print(f"  Created default category '未分類'.")

        self.checked_data_items = {cat: self.checked_data_items.get(cat, set()) for cat in categories}
        print(f"  Initialized/cleaned checked_data_items: {self.checked_data_items}")

        new_tab_index = -1
        print(f"  Starting loop to create tabs...")
        for i, category in enumerate(categories):
            print(f"    Processing category '{category}' (Index {i})...")
            list_widget = QListWidget() # 親指定なし
            print(f"      QListWidget created: {list_widget}")
            self.category_item_lists[category] = list_widget
            print(f"      Stored list_widget into self.category_item_lists for '{category}'.")

            # ★★★ ここでのリスト更新呼び出しは削除 ★★★
            # print(f"      Refreshing item list for '{category}' BEFORE adding tab...")
            # self.refresh_item_list_for_category(category)

            self.category_tab_widget.addTab(list_widget, category)
            print(f"      Added tab '{category}' with its list widget to category_tab_widget.")

            if category == current_tab_text:
                new_tab_index = i
                print(f"      '{category}' matches previous tab text. Index set to {i}.")

        print(f"  Finished processing categories. self.category_item_lists keys: {list(self.category_item_lists.keys())}")

        # --- ★★★ 先にタブを設定 ---
        print(f"  Setting current tab index to: {new_tab_index}")
        target_index = 0 # デフォルトは最初のタブ
        if new_tab_index != -1:
            target_index = new_tab_index
        elif self.category_tab_widget.count() > 0:
            target_index = 0
        else:
            target_index = -1 # タブがない場合

        if target_index != -1:
             print(f"  Setting current tab index to {target_index} BEFORE unblocking signals.")
             self.category_tab_widget.setCurrentIndex(target_index)
        else:
             print(f"  No tabs exist.")

        # --- シグナルブロック解除 ---
        self.category_tab_widget.blockSignals(False)

        # --- ★★★ 起動時/リフレッシュ時に最初のタブのリストを更新 ---
        if target_index != -1:
            initial_category = self.category_tab_widget.tabText(target_index)
            print(f"  Refreshing list for initially selected tab: '{initial_category}'")
            self.refresh_item_list_for_category(initial_category)
        else:
            print(f"  No initial list to refresh.")

        self._update_checked_items_signal() # シグナル発行
        print(f"--- DEBUG: Finished refreshing categories and tabs ---")


    def add_new_category_result(self, category_name):
        """MainWindowからカテゴリ名を受け取ってカテゴリを作成"""
        if category_name:
             if create_category(category_name):
                  self.refresh_categories_and_tabs()
                  # 作成したタブを選択
                  for i in range(self.category_tab_widget.count()):
                       if self.category_tab_widget.tabText(i) == category_name:
                            self.category_tab_widget.setCurrentIndex(i)
                            break
             else:
                  QMessageBox.warning(self, "エラー", f"カテゴリ '{category_name}' の作成に失敗しました。")


    def _on_tab_changed(self, index):
        """タブが切り替わったときの処理"""
        # --- ★★★ 実装を戻す ★★★ ---
        if index != -1:
             category = self.category_tab_widget.tabText(index)
             print(f"\n--- DEBUG: Data tab changed to index {index}: '{category}'. Refreshing list...")
             # ★ 表示中のタブのアイテムリストを更新する
             self.refresh_item_list_for_category(category)
        else:
             print(f"\n--- DEBUG: Data tab changed to index -1 (no tab selected) ---")


    def refresh_item_list_for_category(self, category):
        """指定されたカテゴリのアイテムリストウィジェットを更新"""
        print(f"\n--- DEBUG: Attempting to refresh item list for category: '{category}' ---")
        print(f"  Accessing self.category_item_lists (ID: {id(self.category_item_lists)})")

        list_widget = self.category_item_lists.get(category)
        if list_widget is not None:
            print(f"  Found QListWidget for '{category}' in dictionary: ID={id(list_widget)}")
        else:
            # ★★★ ここでエラーになるのは依然として問題 ★★★
            print(f"  ★★★ WARNING: QListWidget for '{category}' is None in dictionary.")
            print(f"    Current self.category_item_lists keys: {list(self.category_item_lists.keys())}")
            print(f"--- DEBUG: Finished refreshing item list for category '{category}' (Widget not found) ---")
            return # ウィジェットが見つからない場合は処理中断

        # ここに到達した場合、list_widget は存在するはず
        print(f"  Target QListWidget found: {list_widget}")
        list_widget.clear()
        print(f"  List widget cleared.")

        try:
            print(f"  Calling list_items('{category}')...")
            items_info = list_items(category)
            print(f"  list_items('{category}') returned ({len(items_info)} items): {items_info}")

            checked_ids = self.checked_data_items.get(category, set())

            if not items_info:
                print("  -> No items found or returned for this category. List will be empty.")
            else:
                print(f"  -> Found {len(items_info)} items. Starting loop...")
                for i, item_info in enumerate(items_info):
                    item_id = None
                    try:
                        if not isinstance(item_info, dict):
                            print(f"    Warning: Item info is not a dictionary, skipping: {item_info}")
                            continue
                        item_id = item_info.get('id', None)
                        item_name = item_info.get('name', 'N/A')
                        # print(f"    Loop {i+1}: Processing item ID='{item_id}', Name='{item_name}'")
                        if item_id is None: continue
                        is_checked = item_id in checked_ids
                        if list_widget is None: continue # 念のため
                        list_item = QListWidgetItem(list_widget)
                        item_widget = DataItemWidget(item_name, item_id, is_checked)
                        item_widget.checkStateChanged.connect(
                            lambda checked, cat=category, iid=item_id: \
                                self._handle_item_check_change(cat, iid, checked)
                        )
                        item_widget.detailRequested.connect(
                            lambda cat=category, iid=item_id: self.show_detail_window(cat, iid)
                        )
                        hint = item_widget.sizeHint()
                        list_item.setSizeHint(hint)
                        list_widget.addItem(list_item)
                        list_widget.setItemWidget(list_item, item_widget)
                        # print(f"      Item widget set successfully for ID='{item_id}'.")
                    except Exception as e_inner:
                        print(f"    ★★★ Error during widget creation/setting for item ID='{item_id}': {e_inner}")
                        import traceback; traceback.print_exc()
        except Exception as e_outer:
            print(f"★★★ Error in refresh_item_list_for_category for '{category}': {e_outer}")
            import traceback; traceback.print_exc()

        print(f"--- DEBUG: Finished refreshing item list for category: '{category}' ---")

    # --- (_handle_item_check_change, _update_checked_items_signal, get_checked_items は変更なし) ---
    def _handle_item_check_change(self, category, item_id, is_checked):
        print(f"Data Item Check changed: Category='{category}', ID='{item_id}', Checked={is_checked}")
        if category not in self.checked_data_items: self.checked_data_items[category] = set()
        if is_checked:
            self.checked_data_items[category].add(item_id)
            self.show_detail_window(category, item_id)
        else:
            self.checked_data_items[category].discard(item_id)
        print(f"Updated checked_data_items: {self.checked_data_items}")
        self._update_checked_items_signal()

    def _update_checked_items_signal(self):
        self.checkedItemsChanged.emit(self.checked_data_items.copy())

    def get_checked_items(self):
        return self.checked_data_items.copy()

    # --- アイテム追加はシグナル発行に変更 ---
    def _request_add_item(self):
        """アイテム追加要求シグナルを発行"""
        current_index = self.category_tab_widget.currentIndex()
        if current_index != -1:
            current_category = self.category_tab_widget.tabText(current_index)
            self.addItemRequested.emit(current_category)
        else:
            QMessageBox.warning(self, "カテゴリ未選択", "アイテムを追加するカテゴリを選択してください。")

    def add_new_item_result(self, category, item_name):
        """MainWindowからアイテム名を受け取ってアイテムを追加"""
        if category and item_name:
            new_data = {"name": item_name, "description": "", "history": [], "tags": [], "image_path": None}
            new_id = add_item(category, new_data)
            if new_id:
                self.refresh_item_list_for_category(category) # リスト更新
                # 追加したアイテムを選択状態にするかは任意
                # self.show_detail_window(category, new_id) # 詳細表示
            else:
                QMessageBox.warning(self, "エラー", f"アイテム '{item_name}' の追加に失敗しました。")


    def delete_checked_items(self):
        """現在表示中のカテゴリでチェックされているアイテムを削除"""
        current_index = self.category_tab_widget.currentIndex()
        if current_index == -1:
            QMessageBox.warning(self, "カテゴリ未選択", "アイテムを削除するカテゴリを選択してください。")
            return
        current_category = self.category_tab_widget.tabText(current_index)
        checked_ids = self.checked_data_items.get(current_category, set())

        if not checked_ids:
            QMessageBox.warning(self, "アイテム未選択", "削除するアイテムにチェックを入れてください。")
            return

        # 削除対象の名前を取得 (表示用)
        items_to_delete_names = []
        list_widget = self.category_item_lists.get(current_category)
        if list_widget:
             for i in range(list_widget.count()):
                  item = list_widget.item(i)
                  widget = list_widget.itemWidget(item)
                  if isinstance(widget, DataItemWidget) and widget.item_id in checked_ids:
                       items_to_delete_names.append(widget.name)

        reply = QMessageBox.question(self, '削除確認',
                                   f"カテゴリ '{current_category}' のチェックされたアイテム:\n{', '.join(items_to_delete_names)}\nを削除しますか？",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            deleted_count = 0
            # カテゴリの全データをロード (削除はID指定なのでこれでOK)
            category_data = load_data_category(current_category)
            ids_actually_deleted = []

            for item_id in checked_ids:
                if item_id in category_data:
                    del category_data[item_id]
                    ids_actually_deleted.append(item_id)
                    deleted_count += 1

            if deleted_count > 0:
                if save_data_category(current_category, category_data):
                    # チェック状態からも削除
                    self.checked_data_items[current_category].difference_update(ids_actually_deleted)
                    # リストを再描画
                    self.refresh_item_list_for_category(current_category)
                    # 詳細ウィンドウが削除されたアイテムを表示していたらクリア
                    if self._detail_window and self._detail_window.current_item_id in ids_actually_deleted:
                         self._detail_window.clear_view()
                    self._update_checked_items_signal() # チェック状態変更シグナル発行
                    print(f"{deleted_count}個のアイテムをカテゴリ '{current_category}' から削除しました。")
                else:
                     QMessageBox.warning(self, "エラー", "アイテムの削除に失敗しました（保存エラー）。")


    # --- 詳細ウィンドウの管理 ---
    def ensure_detail_window_exists(self):
        """詳細ウィンドウが存在しない場合、作成して接続する"""
        if self._detail_window is None:
            self._detail_window = DetailWindow()
            # 詳細ウィンドウが保存されたら、メインリストを更新
            self._detail_window.dataSaved.connect(self._handle_detail_saved)
            # 詳細ウィンドウが閉じられたら参照をリセット
            self._detail_window.windowClosed.connect(self._handle_detail_closed)

    def show_detail_window(self, category, item_id):
        """指定されたアイテムの詳細ウィンドウを表示/更新し、位置を調整"""
        self.ensure_detail_window_exists()
        self._last_detail_item = {"category": category, "id": item_id}

        # --- ★★★ 位置とサイズ調整処理を修正 ★★★ ---
        main_window = self.window()
        if main_window:
            # メインウィンドウのスクリーンを取得し、利用可能領域を取得
            screen = main_window.screen()
            if screen: # スクリーンが取得できた場合のみ
                screen_geo = screen.availableGeometry() # 利用可能な領域

                # --- 修正: main_window.geometry() を使用 ---
                main_geo = main_window.geometry() # geometry() を使う
                main_right = main_geo.right()
                main_top = main_geo.top()
                main_height = main_geo.height()
                # --------------------------------------

                detail_width = 500 # 希望幅
                detail_height = main_height # 高さを合わせる

                # 初期位置をメインウィンドウの右隣に設定
                new_x = main_right + 5
                new_y = main_top # ★ メインウィンドウの上端に合わせる

                # 右にはみ出す場合の調整
                if new_x + detail_width > screen_geo.right():
                    new_x = main_geo.left() - detail_width - 5 # 左隣に
                    if new_x < screen_geo.left(): # それでも左にはみ出す場合
                        new_x = screen_geo.left() # 画面左端

                # 上下のはみ出し調整
                if new_y < screen_geo.top():
                    new_y = screen_geo.top()
                if new_y + detail_height > screen_geo.bottom():
                    # 下にはみ出す場合は高さを調整
                    detail_height = screen_geo.bottom() - new_y
                    if detail_height < 100: # 最小高さ保証 (任意)
                         detail_height = 100
                         # 高さを縮めても上にはみ出す場合は上にずらす
                         if new_y + detail_height > screen_geo.bottom():
                              new_y = screen_geo.bottom() - detail_height

                print(f"  Moving/Resizing detail window to X:{new_x}, Y:{new_y}, W:{detail_width}, H:{detail_height}")
                # --- 修正: setGeometry を使用 ---
                self._detail_window.setGeometry(new_x, new_y, detail_width, detail_height)
            else:
                print("  Warning: Could not get screen geometry.")
                self._detail_window.resize(500, 600)
        else:
             print("  Warning: Could not get main window for positioning.")
             self._detail_window.resize(500, 600)
        # -----------------------------------------

        self._detail_window.load_data(category, item_id)
        if not self._detail_window.isVisible():
            self._detail_window.show()
        self._detail_window.activateWindow()
        self._detail_window.raise_()


    def _handle_detail_saved(self, category, item_id):
        """詳細ウィンドウでの保存完了シグナルを処理"""
        print(f"Detail saved for: Category='{category}', ID='{item_id}'")
        # 対応するカテゴリのアイテムリストをリフレッシュして名前の変更などを反映
        # ただし、現在表示中のタブが異なっていても更新してしまうので注意
        if category in self.category_item_lists:
             self.refresh_item_list_for_category(category)
             # もしキャッシュを使っているなら、ここでキャッシュも更新する
             # self.item_data_cache[category][item_id] = get_item(category, item_id)

    def _handle_detail_closed(self):
        """詳細ウィンドウが閉じられたときの処理"""
        print("Detail window reference reset.")
        self._detail_window = None # ウィンドウが閉じられたら参照を消す

    # 親ウィジェットが閉じられるときに詳細ウィンドウも閉じる（任意）
    def closeEvent(self, event):
        if self._detail_window:
            self._detail_window.close()
        super().closeEvent(event)

