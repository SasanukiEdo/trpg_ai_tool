# ui/data_widget.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QTabWidget, QMessageBox, QInputDialog, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- core モジュールインポート ---
from core.data_manager import (
    list_categories, list_items, get_item, add_item, update_item, delete_item,
    create_category, load_data_category, save_data_category # save_data_category も必要になる可能性
)
# --- ui モジュールインポート ---
from ui.detail_window import DetailWindow
from ui.data_item_widget import DataItemWidget

# ==============================================================================
# データ管理ウィジェット
# ==============================================================================
class DataManagementWidget(QWidget):
    checkedItemsChanged = pyqtSignal(dict)
    addCategoryRequested = pyqtSignal() # カテゴリ追加要求 (MainWindowへ)
    addItemRequested = pyqtSignal(str) # アイテム追加要求 (MainWindowへ、引数はカテゴリ名)

    # --- ★★★ __init__ に project_dir_name を追加 ★★★ ---
    def __init__(self, project_dir_name, parent=None):
        super().__init__(parent)
        self.current_project_dir_name = project_dir_name # ★ プロジェクトディレクトリ名を保持
        self.category_item_lists = {} # {category_name: QListWidget}
        self.checked_data_items = {}  # {category_name: {item_id1, item_id2}}
        self._detail_window = None
        self._last_detail_item = {"category": None, "id": None}
        self.init_ui()
    # -------------------------------------------------

    def set_project(self, project_dir_name):
        """プロジェクトが変更されたときに呼び出され、表示を更新する"""
        print(f"DataManagementWidget: Setting project to '{project_dir_name}'")
        self.current_project_dir_name = project_dir_name
        self.checked_data_items.clear() # チェック状態をリセット
        self.refresh_categories_and_tabs() # タブとリストを再読み込み
        # 詳細ウィンドウもリセットまたは閉じる (任意)
        if self._detail_window and self._detail_window.isVisible():
            self._detail_window.close() # または clear_view() など
            self._last_detail_item = {"category": None, "id": None}
        self._update_checked_items_signal() # チェック状態変更シグナル発行


    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        category_button_layout = QHBoxLayout()
        self.add_category_button = QPushButton("カテゴリ追加")
        self.add_category_button.clicked.connect(self.addCategoryRequested.emit) # MainWindowに通知
        category_button_layout.addWidget(self.add_category_button)
        category_button_layout.addStretch()
        main_layout.addLayout(category_button_layout)

        self.category_tab_widget = QTabWidget()
        self.category_tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.category_tab_widget)

        item_button_layout = QHBoxLayout()
        self.add_item_button = QPushButton("アイテム追加")
        self.add_item_button.clicked.connect(self._request_add_item) # MainWindowに通知
        self.delete_checked_items_button = QPushButton("チェックしたアイテムを削除")
        self.delete_checked_items_button.clicked.connect(self.delete_checked_items)
        item_button_layout.addWidget(self.add_item_button)
        item_button_layout.addWidget(self.delete_checked_items_button)
        item_button_layout.addStretch()
        main_layout.addLayout(item_button_layout)

        self.refresh_categories_and_tabs() # 初期読み込み
        self.ensure_detail_window_exists()

    # --- カテゴリとタブの管理 (project_dir_name を使用) ---
    def refresh_categories_and_tabs(self):
        self.category_tab_widget.blockSignals(True)
        current_tab_text = self.category_tab_widget.tabText(self.category_tab_widget.currentIndex())
        print(f"\n--- DataWidget DEBUG: Refreshing categories for project '{self.current_project_dir_name}'. Prev tab: '{current_tab_text}' ---")

        self.category_tab_widget.clear()
        self.category_item_lists.clear() # ★ 辞書もクリア

        categories = list_categories(self.current_project_dir_name)
        print(f"  Loaded categories: {categories}")
        if not categories:
             if create_category(self.current_project_dir_name, "未分類"):
                  categories.append("未分類")
                  print(f"  Created default category '未分類'.")

        self.checked_data_items = {cat: self.checked_data_items.get(cat, set()) for cat in categories}
        new_tab_index = -1
        # --- ★★★ QListWidget 作成時に親を指定する試み ★★★ ---
        created_list_widgets_temp = {} # 一時的に保持する辞書

        for i, category in enumerate(categories):
            # list_widget = QListWidget() # 古いコード
            list_widget = QListWidget(self.category_tab_widget) # ★ 親ウィジェットとしてタブウィジェットを指定
            print(f"  Created QListWidget for '{category}' with parent: {list_widget}")
            # self.category_item_lists[category] = list_widget # ★ すぐには格納しない
            created_list_widgets_temp[category] = list_widget # ★ 一時辞書に格納

            self.category_tab_widget.addTab(list_widget, category)
            print(f"    Added tab '{category}' to category_tab_widget with list_widget: {list_widget}")
            if category == current_tab_text: new_tab_index = i

        # --- ★★★ ループ完了後、一時辞書の内容を self.category_item_lists にコピー ★★★ ---
        self.category_item_lists = created_list_widgets_temp.copy()
        print(f"  Copied list widgets to self.category_item_lists. Keys: {list(self.category_item_lists.keys())}")
        for cat_name, lw in self.category_item_lists.items():
             print(f"    For category '{cat_name}', QListWidget is: {lw}")
        # ----------------------------------------------------------

        target_initial_load_category = None
        if self.category_tab_widget.count() > 0:
            if new_tab_index != -1:
                self.category_tab_widget.setCurrentIndex(new_tab_index)
                target_initial_load_category = self.category_tab_widget.tabText(new_tab_index)
            else:
                self.category_tab_widget.setCurrentIndex(0)
                target_initial_load_category = self.category_tab_widget.tabText(0)
        else:
            self._update_checked_items_signal()

        self.category_tab_widget.blockSignals(False) # シグナルブロック解除

        if target_initial_load_category:
            print(f"  DataWidget: Explicitly attempting to refresh list for '{target_initial_load_category}' after tab setup (in refresh_categories_and_tabs).")
            self.refresh_item_list_for_category(target_initial_load_category) # ★ ここで呼ぶ

        print(f"--- DataWidget DEBUG: Finished refreshing categories and tabs for project '{self.current_project_dir_name}' ---")


    def add_new_category_result(self, category_name):
        """MainWindowからカテゴリ名を受け取ってカテゴリを作成"""
        if category_name:
             # ★★★ create_category に project_dir_name ★★★
             if create_category(self.current_project_dir_name, category_name):
                  self.refresh_categories_and_tabs()
                  for i in range(self.category_tab_widget.count()):
                       if self.category_tab_widget.tabText(i) == category_name:
                            self.category_tab_widget.setCurrentIndex(i); break
             else: QMessageBox.warning(self, "エラー", f"カテゴリ '{category_name}' の作成に失敗しました。")

    def _on_tab_changed(self, index):
        if index != -1:
             category = self.category_tab_widget.tabText(index)
             print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index {index}, category '{category}' for project '{self.current_project_dir_name}'. Refreshing list... ---")
             self.refresh_item_list_for_category(category)
        else:
             print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index -1 (no tab selected) for project '{self.current_project_dir_name}'. ---")

    # --- アイテムリストの管理 (project_dir_name を使用) ---
    def refresh_item_list_for_category(self, category):
        print(f"\n--- DataWidget DEBUG: Refreshing item list for category '{category}' in project '{self.current_project_dir_name}' ---")
        list_widget = self.category_item_lists.get(category)
        if not list_widget:
            print(f"  ★★★ WARNING: QListWidget for '{category}' not found.")
            return
        list_widget.clear()

        # ★★★ list_items に project_dir_name ★★★
        items_info = list_items(self.current_project_dir_name, category)
        print(f"  list_items returned ({len(items_info)} items): {items_info}")
        checked_ids = self.checked_data_items.get(category, set())

        if not items_info: print("  -> No items found.")
        else:
            print(f"  -> Found {len(items_info)} items. Adding to list...")
            for item_info in items_info:
                item_id = item_info.get('id')
                item_name = item_info.get('name', 'N/A')
                if not item_id: continue
                is_checked = item_id in checked_ids
                list_item_obj = QListWidgetItem(list_widget) # QListWidgetItem を item とは別の名前に
                item_widget = DataItemWidget(item_name, item_id, is_checked)
                item_widget.checkStateChanged.connect(
                    lambda checked, cat=category, iid=item_id: \
                        self._handle_item_check_change(cat, iid, checked)
                )
                item_widget.detailRequested.connect(
                    lambda cat=category, iid=item_id: self.show_detail_window(cat, iid)
                )
                list_item_obj.setSizeHint(item_widget.sizeHint())
                list_widget.addItem(list_item_obj)
                list_widget.setItemWidget(list_item_obj, item_widget)
        print(f"--- DataWidget DEBUG: Finished refreshing item list for '{category}' ---")


    def _handle_item_check_change(self, category, item_id, is_checked):
        print(f"Data Item Check changed: Project='{self.current_project_dir_name}', Category='{category}', ID='{item_id}', Checked={is_checked}")
        if category not in self.checked_data_items: self.checked_data_items[category] = set()
        if is_checked:
            self.checked_data_items[category].add(item_id)
            self.show_detail_window(category, item_id) # チェック時に詳細表示
        else:
            self.checked_data_items[category].discard(item_id)
        self._update_checked_items_signal()

    def _update_checked_items_signal(self):
        self.checkedItemsChanged.emit(self.checked_data_items.copy())

    def get_checked_items(self):
        return self.checked_data_items.copy()

    # --- アイテム操作 (project_dir_name を使用) ---
    def _request_add_item(self):
        current_index = self.category_tab_widget.currentIndex()
        if current_index != -1:
            current_category = self.category_tab_widget.tabText(current_index)
            self.addItemRequested.emit(current_category) # MainWindow へ通知
        else:
            QMessageBox.warning(self, "カテゴリ未選択", "アイテムを追加するカテゴリを選択してください。")

    def add_new_item_result(self, category, item_name):
        """MainWindowからアイテム名を受け取ってアイテムを追加"""
        if category and item_name:
            new_data = {"name": item_name, "description": "", "history": [], "tags": [], "image_path": None}
            # ★★★ add_item に project_dir_name ★★★
            new_id = add_item(self.current_project_dir_name, category, new_data)
            if new_id:
                self.refresh_item_list_for_category(category)
            else: QMessageBox.warning(self, "エラー", f"アイテム '{item_name}' の追加に失敗しました。")

    def delete_checked_items(self):
        current_tab_index = self.category_tab_widget.currentIndex()
        if current_tab_index == -1:
            QMessageBox.warning(self, "カテゴリ未選択", "削除するアイテムが含まれるカテゴリを選択してください。")
            return
        current_category = self.category_tab_widget.tabText(current_tab_index)
        ids_to_delete = self.checked_data_items.get(current_category, set()).copy()
        if not ids_to_delete:
            QMessageBox.information(self, "アイテム未選択", "削除するアイテムがチェックされていません。")
            return

        reply = QMessageBox.question(self, "削除確認",
                                   f"カテゴリ '{current_category}' のチェックされた {len(ids_to_delete)} 個のアイテムを削除しますか？\nこの操作は元に戻せません。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            deleted_count = 0
            # ★★★ load_data_category と save_data_category に project_dir_name ★★★
            category_data = load_data_category(self.current_project_dir_name, current_category)
            if category_data is None:
                QMessageBox.warning(self, "エラー", f"カテゴリ '{current_category}' のデータ読み込みに失敗しました。")
                return

            temp_data = category_data.copy() # 変更用にコピー
            for item_id in ids_to_delete:
                if item_id in temp_data:
                    del temp_data[item_id]
                    deleted_count += 1
            if deleted_count > 0:
                if save_data_category(self.current_project_dir_name, current_category, temp_data):
                    QMessageBox.information(self, "削除完了", f"{deleted_count} 個のアイテムを削除しました。")
                    self.checked_data_items[current_category].clear() # チェック状態をクリア
                    self.refresh_item_list_for_category(current_category) # リスト更新
                    self._update_checked_items_signal()
                else:
                    QMessageBox.warning(self, "保存エラー", "アイテム削除後のデータ保存に失敗しました。")
            else:
                QMessageBox.information(self, "削除なし", "削除対象のアイテムが見つかりませんでした。")


    # --- 詳細ウィンドウの管理 (project_dir_name を使用) ---
    def ensure_detail_window_exists(self):
        if self._detail_window is None:
            main_window_instance = self.window()
            main_config_to_pass = {}
            if main_window_instance and hasattr(main_window_instance, 'global_config'): # MainWindow側のconfig変数名に注意
                # DetailWindow に渡すのはプロジェクト設定とグローバルデフォルトモデル
                project_settings = {}
                if hasattr(main_window_instance, 'current_project_settings'):
                    project_settings = main_window_instance.current_project_settings
                main_config_to_pass = {
                    "model": project_settings.get("model", main_window_instance.global_config.get("default_model")),
                    # 他に DetailWindow がグローバル設定を参照する必要があれば追加
                }
            self._detail_window = DetailWindow(main_config=main_config_to_pass)
            self._detail_window.dataSaved.connect(self._handle_detail_saved)
            self._detail_window.windowClosed.connect(self._handle_detail_closed)

    def show_detail_window(self, category, item_id):
        self.ensure_detail_window_exists()
        self._last_detail_item = {"category": category, "id": item_id}

        # DetailWindow に渡す main_config を再設定 (プロジェクト固有モデルなど)
        main_window_instance = self.window()
        current_project_model = None
        if main_window_instance and hasattr(main_window_instance, 'current_project_settings'):
            current_project_model = main_window_instance.current_project_settings.get('model')
        if not current_project_model and main_window_instance and hasattr(main_window_instance, 'global_config'):
            current_project_model = main_window_instance.global_config.get('default_model')

        if self._detail_window and current_project_model: # main_config を更新
             self._detail_window.main_config["model"] = current_project_model

        # 位置調整ロジック (変更なし)
        main_window = self.window()
        if main_window:
            screen = main_window.screen()
            if screen:
                screen_geo = screen.availableGeometry()
                main_top_left_global = main_window.mapToGlobal(QPoint(0, 0))
                main_width = main_window.width()
                main_height = main_window.height()
                detail_width = 500
                detail_height = main_height
                new_x = main_top_left_global.x() + main_width + 5
                new_y = main_top_left_global.y()
                if new_x + detail_width > screen_geo.right(): new_x = main_top_left_global.x() - detail_width - 5
                if new_x < screen_geo.left(): new_x = screen_geo.left()
                if new_y < screen_geo.top(): new_y = screen_geo.top()
                if new_y + detail_height > screen_geo.bottom():
                    detail_height = screen_geo.bottom() - new_y
                    if detail_height < 100: detail_height = 100
                    if new_y + detail_height > screen_geo.bottom(): new_y = screen_geo.bottom() - detail_height
                self._detail_window.setGeometry(new_x, new_y, detail_width, detail_height)

        # ★★★ DetailWindow の load_data には project_dir_name は不要 (DetailWindowは知らない) ★★★
        self._detail_window.load_data(category, item_id)
        if not self._detail_window.isVisible(): self._detail_window.show()
        self._detail_window.activateWindow()
        self._detail_window.raise_()

    def _handle_detail_saved(self, category, item_id):
        """詳細ウィンドウでデータが保存されたときの処理"""
        print(f"DataWidget: Detail saved for '{category}' - '{item_id}' in project '{self.current_project_dir_name}'. Refreshing list.")
        self.refresh_item_list_for_category(category)
        # 必要ならチェック状態なども更新

    def _handle_detail_closed(self):
        """詳細ウィンドウが閉じられたときの処理"""
        self._last_detail_item = {"category": None, "id": None}
        # print("DataWidget: Detail window closed.")
