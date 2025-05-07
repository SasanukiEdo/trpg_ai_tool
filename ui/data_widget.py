# ui/data_widget.py

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QTabWidget, QMessageBox, QInputDialog, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path: sys.path.insert(0, project_root)

from core.data_manager import (
    list_categories, list_items, get_item, add_item, update_item, delete_item,
    create_category, load_data_category, save_data_category
)
from ui.detail_window import DetailWindow
from ui.data_item_widget import DataItemWidget

class DataManagementWidget(QWidget):
    checkedItemsChanged = pyqtSignal(dict)
    addCategoryRequested = pyqtSignal()
    addItemRequested = pyqtSignal(str)

    def __init__(self, project_dir_name, parent=None):
        super().__init__(parent)
        self.current_project_dir_name = project_dir_name
        # ★★★ self.category_item_lists はタブウィジェットが持つウィジェットを直接参照する方針も検討したが、
        #     まずは辞書で管理する従来の方針で、生成と参照のタイミングを厳密にする。
        self.category_item_lists = {}
        self.checked_data_items = {}
        self._detail_window = None
        self._last_detail_item = {"category": None, "id": None}
        print(f"DataManagementWidget __init__: self.category_item_lists (ID: {id(self.category_item_lists)}) created for project '{self.current_project_dir_name}'")
        self.init_ui()

    def set_project(self, project_dir_name):
        print(f"DataManagementWidget: Setting project to '{project_dir_name}'")
        old_project = self.current_project_dir_name
        self.current_project_dir_name = project_dir_name
        self.checked_data_items.clear()
        # ★★★ refresh_categories_and_tabs を呼び出す前に self.category_item_lists もクリアする ★★★
        self.category_item_lists.clear() # プロジェクト変更時は辞書もクリア
        print(f"  DataManagementWidget set_project: Cleared self.category_item_lists (ID: {id(self.category_item_lists)})")
        self.refresh_categories_and_tabs()
        if self._detail_window and self._detail_window.isVisible():
            self._detail_window.close()
        self._update_checked_items_signal()
        print(f"  DataManagementWidget set_project: Project changed from '{old_project}' to '{self.current_project_dir_name}'. UI refreshed.")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # ... (ボタンレイアウトなどは変更なし) ...
        category_button_layout = QHBoxLayout()
        self.add_category_button = QPushButton("カテゴリ追加")
        self.add_category_button.clicked.connect(self.addCategoryRequested.emit)
        category_button_layout.addWidget(self.add_category_button)
        category_button_layout.addStretch()
        main_layout.addLayout(category_button_layout)

        self.category_tab_widget = QTabWidget()
        self.category_tab_widget.currentChanged.connect(self._on_tab_changed) # シグナル接続
        main_layout.addWidget(self.category_tab_widget)

        item_button_layout = QHBoxLayout()
        self.add_item_button = QPushButton("アイテム追加")
        self.add_item_button.clicked.connect(self._request_add_item)
        self.delete_checked_items_button = QPushButton("チェックしたアイテムを削除")
        self.delete_checked_items_button.clicked.connect(self.delete_checked_items)
        item_button_layout.addWidget(self.add_item_button)
        item_button_layout.addWidget(self.delete_checked_items_button)
        item_button_layout.addStretch()
        main_layout.addLayout(item_button_layout)

        self.refresh_categories_and_tabs() # 初期読み込み
        self.ensure_detail_window_exists()

    def refresh_categories_and_tabs(self):
        """カテゴリ一覧を読み込み、タブを再構築し、リストを更新する"""
        # --- ★★★ 0. シグナルをブロック ---
        self.category_tab_widget.blockSignals(True)
        print(f"\n--- DataWidget DEBUG: Refreshing categories for project '{self.current_project_dir_name}' ---")
        print(f"  Phase 0: Signals blocked. Current self.category_item_lists (ID: {id(self.category_item_lists)}) keys: {list(self.category_item_lists.keys())}")

        # --- ★★★ 1. 既存のタブとリストウィジェット参照をクリア ---
        previous_selected_tab_text = self.category_tab_widget.tabText(self.category_tab_widget.currentIndex())
        self.category_tab_widget.clear() # これによりタブ内のウィジェットも破棄されるはず
        self.category_item_lists.clear() # ★ 必ずクリアする
        print(f"  Phase 1: Tabs and self.category_item_lists (ID: {id(self.category_item_lists)}) cleared.")

        # --- ★★★ 2. カテゴリをロード ---
        categories = list_categories(self.current_project_dir_name)
        print(f"  Phase 2: Loaded categories: {categories}")
        if not categories:
            if create_category(self.current_project_dir_name, "未分類"):
                categories.append("未分類")
            print(f"    Categories after potential default creation: {categories}")

        self.checked_data_items = {cat: self.checked_data_items.get(cat, set()) for cat in categories}

        # --- ★★★ 3. 新しいタブとリストウィジェットを作成し、辞書に格納 ---
        newly_created_list_widgets = {} # ローカル変数で作成
        for i, category in enumerate(categories):
            list_widget = QListWidget(self.category_tab_widget) # ★ 親を指定
            print(f"    Creating QListWidget for '{category}': {list_widget} (Parent: {list_widget.parent()})")
            newly_created_list_widgets[category] = list_widget # ★ ローカル辞書に格納
            self.category_tab_widget.addTab(list_widget, category)
            print(f"      Added tab for '{category}' with widget {list_widget}")

        # --- ★★★ 4. 作成したリストウィジェットを self.category_item_lists に一括で設定 ---
        self.category_item_lists = newly_created_list_widgets # ★ ここでインスタンス変数に代入
        print(f"  Phase 4: self.category_item_lists (ID: {id(self.category_item_lists)}) populated. Keys: {list(self.category_item_lists.keys())}")
        for cat_name, lw_debug in self.category_item_lists.items():
            print(f"    Verify: Category '{cat_name}', Widget in dict: {lw_debug}")


        # --- ★★★ 5. 表示するタブを選択 (まだシグナルはブロック中) ---
        selected_category_for_refresh = None
        if self.category_tab_widget.count() > 0:
            idx_to_select = 0
            if previous_selected_tab_text: # 前に選択していたタブがあればそれを再選択
                for i in range(self.category_tab_widget.count()):
                    if self.category_tab_widget.tabText(i) == previous_selected_tab_text:
                        idx_to_select = i
                        break
            self.category_tab_widget.setCurrentIndex(idx_to_select)
            selected_category_for_refresh = self.category_tab_widget.tabText(idx_to_select)
            print(f"  Phase 5: Current tab set to index {idx_to_select} ('{selected_category_for_refresh}') with signals blocked.")
        else:
            print(f"  Phase 5: No tabs exist.")
            self._update_checked_items_signal()


        # --- ★★★ 6. シグナルブロックを解除 ---
        self.category_tab_widget.blockSignals(False)
        print(f"  Phase 6: Signals unblocked.")

        # --- ★★★ 7. 選択されているタブのリストを明示的に更新 ---
        # setCurrentIndex がシグナルブロック中に呼ばれたため、_on_tab_changed はトリガーされない。
        # したがって、ここで明示的にリストを更新する必要がある。
        if selected_category_for_refresh:
            print(f"  Phase 7: Manually refreshing list for '{selected_category_for_refresh}'.")
            self.refresh_item_list_for_category(selected_category_for_refresh)
        else:
            print(f"  Phase 7: No category selected for refresh.")

        print(f"--- DataWidget DEBUG: Finished refreshing categories and tabs for project '{self.current_project_dir_name}' ---")


    def _on_tab_changed(self, index):
        """タブがユーザー操作などで切り替わったときに呼ばれる"""
        if index != -1:
            category = self.category_tab_widget.tabText(index)
            print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index {index}, category '{category}' for project '{self.current_project_dir_name}'. Refreshing list... ---")
            print(f"  _on_tab_changed: Current self.category_item_lists (ID: {id(self.category_item_lists)}) keys: {list(self.category_item_lists.keys())}")
            for cat_name_debug, lw_debug in self.category_item_lists.items():
                print(f"    _on_tab_changed debug dump: Category '{cat_name_debug}', Widget: {lw_debug}")
            self.refresh_item_list_for_category(category)
        else:
            print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index -1 (no tab selected) for project '{self.current_project_dir_name}'. ---")


    def refresh_item_list_for_category(self, category):
        """指定されたカテゴリのアイテムリストウィジェットを更新"""
        print(f"\n--- DataWidget DEBUG: Attempting to refresh item list for category: '{category}' in project '{self.current_project_dir_name}' ---")
        print(f"  refresh_item_list_for_category: Accessing self.category_item_lists (ID: {id(self.category_item_lists)})")
        for cat_name_debug, lw_debug in self.category_item_lists.items():
            print(f"    refresh_item_list_for_category debug dump: Category '{cat_name_debug}', Widget: {lw_debug}")

        list_widget = self.category_item_lists.get(category)
        if not list_widget:
            print(f"  ★★★ CRITICAL ERROR: QListWidget for '{category}' not found in self.category_item_lists. Aborting refresh. ★★★")
            # フォールバックも試みる (デバッグ用)
            current_idx = self.category_tab_widget.currentIndex()
            if current_idx != -1 and self.category_tab_widget.tabText(current_idx) == category:
                widget_from_tab = self.category_tab_widget.widget(current_idx)
                print(f"    Fallback attempt: Widget from QTabWidget.widget({current_idx}) is {widget_from_tab} (type: {type(widget_from_tab)})")
                if isinstance(widget_from_tab, QListWidget):
                     print(f"    FALLBACK SUCCESSFUL: Using widget directly from QTabWidget for '{category}'.")
                     list_widget = widget_from_tab # これで動けば辞書管理に問題
            if not list_widget: # それでもダメなら諦める
                return

        print(f"  Target QListWidget for '{category}' is: {list_widget} (Parent: {list_widget.parent() if list_widget else 'N/A'})")
        list_widget.clear()
        print(f"  List widget for '{category}' cleared.")

        items_info = list_items(self.current_project_dir_name, category)
        # ... (アイテム追加のループは変更なし) ...
        checked_ids = self.checked_data_items.get(category, set())
        if not items_info: print(f"  -> No items found for '{category}'.")
        else:
            print(f"  -> Found {len(items_info)} items for '{category}'. Adding to list...")
            for item_info in items_info:
                item_id = item_info.get('id')
                item_name = item_info.get('name', 'N/A')
                if not item_id: continue
                is_checked = item_id in checked_ids
                list_item_obj = QListWidgetItem(list_widget)
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

    # --- (add_new_category_result 以降のメソッドは、self.current_project_dir_name を使うように適宜修正済みと仮定) ---
    # ... (変更が多い場合は、それらも提示しますが、まずは上記でリスト表示が解決するか確認したい)
    # 既存の _handle_item_check_change, _update_checked_items_signal, get_checked_items,
    # _request_add_item, add_new_item_result, delete_checked_items,
    # ensure_detail_window_exists, show_detail_window, _handle_detail_saved, _handle_detail_closed
    # は、内部で data_manager の関数を呼ぶ際に self.current_project_dir_name を渡すように
    # 前回までの修正で対応済みのはずです。

