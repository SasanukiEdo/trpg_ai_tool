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
    create_category # load_data_category, save_data_category は data_manager 内部で使われる
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
        # --- ★★★ self.category_item_lists を削除 ★★★ ---
        # self.category_item_lists = {} # この辞書による管理をやめる
        self.checked_data_items = {}
        self._detail_window = None
        self._last_detail_item = {"category": None, "id": None}
        print(f"DataManagementWidget __init__ for project '{self.current_project_dir_name}'")
        self.init_ui()

    def set_project(self, project_dir_name):
        print(f"DataManagementWidget: Setting project to '{project_dir_name}'")
        old_project = self.current_project_dir_name
        self.current_project_dir_name = project_dir_name
        self.checked_data_items.clear()
        self.refresh_categories_and_tabs() # これがUIを再構築し、リストも更新する
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
        self.category_tab_widget.currentChanged.connect(self._on_tab_changed)
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
        """カテゴリ一覧を読み込み、タブを再構築し、表示中のタブのリストを更新する"""
        self.category_tab_widget.blockSignals(True)
        print(f"\n--- DataWidget DEBUG: Refreshing categories for project '{self.current_project_dir_name}' ---")

        previous_selected_tab_text = self.category_tab_widget.tabText(self.category_tab_widget.currentIndex())
        self.category_tab_widget.clear() # これによりタブ内のウィジェットも破棄される

        categories = list_categories(self.current_project_dir_name)
        print(f"  Loaded categories: {categories}")
        if not categories:
            if create_category(self.current_project_dir_name, "未分類"):
                categories.append("未分類")
            print(f"    Categories after potential default creation: {categories}")

        self.checked_data_items = {cat: self.checked_data_items.get(cat, set()) for cat in categories}

        idx_to_select = 0 # デフォルトは最初のタブ
        for i, category in enumerate(categories):
            list_widget = QListWidget(self.category_tab_widget) # 親を指定
            print(f"    Creating QListWidget for '{category}': {list_widget}")
            # ★★★ self.category_item_lists への格納をやめる ★★★
            self.category_tab_widget.addTab(list_widget, category)
            print(f"      Added tab for '{category}' with widget {list_widget}")
            if category == previous_selected_tab_text:
                idx_to_select = i

        if self.category_tab_widget.count() > 0:
            self.category_tab_widget.setCurrentIndex(idx_to_select)
            selected_category_for_refresh = self.category_tab_widget.tabText(idx_to_select)
            print(f"  Current tab set to index {idx_to_select} ('{selected_category_for_refresh}') with signals blocked.")
            # --- ★★★ シグナルブロック中にリストを直接更新 ★★★ ---
            print(f"  Manually refreshing list for '{selected_category_for_refresh}' during tab rebuild.")
            self.refresh_item_list_for_category(selected_category_for_refresh) # ★ ここで呼ぶ
        else:
            print(f"  No tabs exist.")
            self._update_checked_items_signal()

        self.category_tab_widget.blockSignals(False)
        print(f"--- DataWidget DEBUG: Finished refreshing categories and tabs for project '{self.current_project_dir_name}' ---")


    def _on_tab_changed(self, index):
        """タブがユーザー操作などで切り替わったときに呼ばれる"""
        if index != -1:
            category = self.category_tab_widget.tabText(index)
            print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index {index}, category '{category}'. Refreshing list... ---")
            self.refresh_item_list_for_category(category)
        else:
            print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index -1 (no tab selected). ---")


    def refresh_item_list_for_category(self, category_name):
        print(f"\n--- DataWidget DEBUG: Attempting to refresh item list for category: '{category_name}' in project '{self.current_project_dir_name}' ---")

        # --- 1. 対象の QListWidget を取得する ---
        target_list_widget = None
        # まず、現在選択されているタブが対象カテゴリか確認
        current_tab_idx = self.category_tab_widget.currentIndex()
        if current_tab_idx != -1 and self.category_tab_widget.tabText(current_tab_idx) == category_name:
            widget_candidate = self.category_tab_widget.widget(current_tab_idx)
            if isinstance(widget_candidate, QListWidget):
                target_list_widget = widget_candidate
                print(f"  Found QListWidget for '{category_name}' (current tab, index {current_tab_idx}): {target_list_widget}")
        
        # もし現在のタブが対象でないか、QListWidgetでなかった場合、全タブを検索 (フォールバック)
        if target_list_widget is None:
            print(f"  Current tab not matching or not a QListWidget. Searching all tabs for '{category_name}'...")
            for i in range(self.category_tab_widget.count()):
                if self.category_tab_widget.tabText(i) == category_name:
                    widget_candidate = self.category_tab_widget.widget(i)
                    if isinstance(widget_candidate, QListWidget):
                        target_list_widget = widget_candidate
                        print(f"  Found QListWidget for '{category_name}' by searching (tab index {i}): {target_list_widget}")
                        break # 見つかったのでループを抜ける
        
        # --- 2. QListWidget が取得できたか最終確認 ---
        if target_list_widget is None:
            print(f"  ★★★ CRITICAL ERROR: Could not definitively find QListWidget for category '{category_name}'. Aborting refresh. ★★★")
            # デバッグ用に全タブ情報を表示
            print(f"    Current QTabWidget has {self.category_tab_widget.count()} tabs:")
            for i in range(self.category_tab_widget.count()):
                tab_text_debug = self.category_tab_widget.tabText(i)
                widget_debug = self.category_tab_widget.widget(i)
                print(f"      Tab {i}: Text='{tab_text_debug}', Widget={widget_debug} (Type: {type(widget_debug)})")
            return

        # --- 3. QListWidget が取得できたら、リストをクリアしてアイテムを追加 ---
        print(f"  Proceeding with target_list_widget: {target_list_widget} (Parent: {target_list_widget.parent()}) for category '{category_name}'")
        target_list_widget.clear()
        print(f"  List widget for '{category_name}' cleared.")

        items_info = list_items(self.current_project_dir_name, category_name)
        checked_ids = self.checked_data_items.get(category_name, set())

        if not items_info:
            print(f"  -> No items found for '{category_name}'.")
        else:
            print(f"  -> Found {len(items_info)} items for '{category_name}'. Adding to list...")
            for item_info in items_info:
                item_id = item_info.get('id')
                item_name = item_info.get('name', 'N/A')
                if not item_id: continue
                is_checked = item_id in checked_ids
                
                list_item_obj = QListWidgetItem(target_list_widget) # 親ListWidgetを指定
                item_widget = DataItemWidget(item_name, item_id, is_checked)
                
                item_widget.checkStateChanged.connect(
                    lambda checked, cat=category_name, iid=item_id: \
                        self._handle_item_check_change(cat, iid, checked)
                )
                item_widget.detailRequested.connect(
                    lambda cat=category_name, iid=item_id: self.show_detail_window(cat, iid)
                )
                
                list_item_obj.setSizeHint(item_widget.sizeHint())
                # target_list_widget.addItem(list_item_obj) # QListWidgetItem作成時に親を指定したので不要
                target_list_widget.setItemWidget(list_item_obj, item_widget)
        print(f"--- DataWidget DEBUG: Finished refreshing item list for '{category_name}' ---")
        

    def add_new_category_result(self, category_name):
        if category_name:
             if create_category(self.current_project_dir_name, category_name):
                  self.refresh_categories_and_tabs()
                  for i in range(self.category_tab_widget.count()):
                       if self.category_tab_widget.tabText(i) == category_name:
                            self.category_tab_widget.setCurrentIndex(i); break
             else: QMessageBox.warning(self, "エラー", f"カテゴリ '{category_name}' の作成に失敗しました。")

    def _handle_item_check_change(self, category, item_id, is_checked):
        # ... (変更なし)
        print(f"Data Item Check changed: Project='{self.current_project_dir_name}', Category='{category}', ID='{item_id}', Checked={is_checked}")
        if category not in self.checked_data_items: self.checked_data_items[category] = set()
        if is_checked:
            self.checked_data_items[category].add(item_id)
            self.show_detail_window(category, item_id)
        else:
            self.checked_data_items[category].discard(item_id)
        self._update_checked_items_signal()

    def _update_checked_items_signal(self):
        self.checkedItemsChanged.emit(self.checked_data_items.copy())

    def get_checked_items(self):
        return self.checked_data_items.copy()

    def _request_add_item(self):
        # ... (変更なし)
        current_index = self.category_tab_widget.currentIndex()
        if current_index != -1:
            current_category = self.category_tab_widget.tabText(current_index)
            self.addItemRequested.emit(current_category)
        else:
            QMessageBox.warning(self, "カテゴリ未選択", "アイテムを追加するカテゴリを選択してください。")

    def add_new_item_result(self, category, item_name):
        # ... (変更なし、add_item が project_dir_name を取るように修正済み)
        if category and item_name:
            new_data = {"name": item_name, "description": "", "history": [], "tags": [], "image_path": None}
            new_id = add_item(self.current_project_dir_name, category, new_data)
            if new_id:
                self.refresh_item_list_for_category(category)
            else: QMessageBox.warning(self, "エラー", f"アイテム '{item_name}' の追加に失敗しました。")

    def delete_checked_items(self):
        # ... (変更なし、load_data_category, save_data_category が project_dir_name を取るように修正済み)
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
            # data_manager の関数はプロジェクト名を引数に取る
            from core.data_manager import load_data_category as dm_load_cat, save_data_category as dm_save_cat
            category_data = dm_load_cat(self.current_project_dir_name, current_category)
            if category_data is None:
                QMessageBox.warning(self, "エラー", f"カテゴリ '{current_category}' のデータ読み込みに失敗しました。")
                return

            temp_data = category_data.copy()
            for item_id in ids_to_delete:
                if item_id in temp_data:
                    del temp_data[item_id]
                    deleted_count += 1
            if deleted_count > 0:
                if dm_save_cat(self.current_project_dir_name, current_category, temp_data):
                    QMessageBox.information(self, "削除完了", f"{deleted_count} 個のアイテムを削除しました。")
                    self.checked_data_items[current_category].clear()
                    self.refresh_item_list_for_category(current_category)
                    self._update_checked_items_signal()
                else:
                    QMessageBox.warning(self, "保存エラー", "アイテム削除後のデータ保存に失敗しました。")
            else:
                QMessageBox.information(self, "削除なし", "削除対象のアイテムが見つかりませんでした。")

    # 詳細ウィンドウ関連も、基本的には DetailWindow 側がデータ操作を data_manager に依頼する形なので
    # DataManagementWidget は project_dir_name を意識しなくて良いはず。
    # DetailWindow の初期化時に渡す main_config に、プロジェクト固有のモデル名が入っていればOK。
    def ensure_detail_window_exists(self):
        # ... (変更なし、MainWindow からプロジェクト設定が渡るように修正済み)
        if self._detail_window is None:
            main_window_instance = self.window()
            main_config_to_pass = {}
            if main_window_instance and hasattr(main_window_instance, 'current_project_settings'):
                project_settings = main_window_instance.current_project_settings
                default_global_model = ""
                if hasattr(main_window_instance, 'global_config'):
                    default_global_model = main_window_instance.global_config.get("default_model", "gemini-1.5-pro-latest")

                main_config_to_pass = {
                    "model": project_settings.get("model", default_global_model),
                }
            self._detail_window = DetailWindow(main_config=main_config_to_pass, project_dir_name=self.current_project_dir_name) # ★ project_dir_name も渡す
            self._detail_window.dataSaved.connect(self._handle_detail_saved)
            self._detail_window.windowClosed.connect(self._handle_detail_closed)


    def show_detail_window(self, category, item_id):
        # ... (変更なし、ensure_detail_window_existsでproject_dir_nameは渡されている)
        self.ensure_detail_window_exists()
        self._last_detail_item = {"category": category, "id": item_id}

        # DetailWindowに渡すmain_config (主にモデル名) を最新に保つ
        main_window_instance = self.window()
        current_project_model = None
        if main_window_instance and hasattr(main_window_instance, 'current_project_settings'):
            current_project_model = main_window_instance.current_project_settings.get('model')
        if not current_project_model and main_window_instance and hasattr(main_window_instance, 'global_config'):
            current_project_model = main_window_instance.global_config.get('default_model')
        if self._detail_window and current_project_model:
             self._detail_window.main_config["model"] = current_project_model
        # ★ DetailWindow にプロジェクト名も渡っているので、load_data はカテゴリとIDだけで良いはず
        # self._detail_window.current_project_dir_name = self.current_project_dir_name # DetailWindow側で保持させる

        # 位置調整ロジック
        main_window = self.window()
        if main_window:
            screen = main_window.screen()
            if screen:
                screen_geo = screen.availableGeometry()
                main_top_left_global = main_window.mapToGlobal(QPoint(0, 0))
                main_width = main_window.width()
                main_height = main_window.height()
                detail_width = 500; detail_height = main_height
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

        self._detail_window.load_data(category, item_id) # DetailWindow が自身のプロジェクト名を使う
        if not self._detail_window.isVisible(): self._detail_window.show()
        self._detail_window.activateWindow(); self._detail_window.raise_()

    def _handle_detail_saved(self, category, item_id):
        print(f"DataWidget: Detail saved for '{category}' - '{item_id}' in project '{self.current_project_dir_name}'. Refreshing list.")
        self.refresh_item_list_for_category(category)

    def _handle_detail_closed(self):
        self._last_detail_item = {"category": None, "id": None}

