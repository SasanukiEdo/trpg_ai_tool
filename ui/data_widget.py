# ui/data_widget.py

"""データ管理エリア全体のUIとロジックを提供するモジュール。

このモジュールは `DataManagementWidget` クラスを定義しており、
カテゴリ別のタブ表示、各カテゴリ内のアイテムリスト表示、
アイテムの追加・削除、詳細表示ウィンドウの呼び出しといった
データ管理に関する主要なユーザーインターフェースを提供します。

`MainWindow` からプロジェクト名を受け取り、それに基づいて表示内容を更新します。
アイテムのチェック状態の管理や、カテゴリ・アイテム追加要求のシグナル発行も行います。
"""

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QTabWidget, QMessageBox, QInputDialog, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from typing import Optional, List, Dict, Tuple

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.data_manager import (
    list_categories, list_items, get_item, add_item, update_item, delete_item,
    create_category, load_data_category, save_data_category # 明示的に使用するものをインポート
)
# --- uiモジュールインポート ---
from ui.detail_window import DetailWindow
from ui.data_item_widget import DataItemWidget

class DataManagementWidget(QWidget):
    """データ管理UIを提供するメインウィジェットクラス。

    カテゴリタブ、アイテムリスト、追加/削除ボタンなどを持ち、
    ユーザーがプロジェクト内のデータを視覚的に操作できるようにします。

    Attributes:
        checkedItemsChanged (pyqtSignal): チェックされたアイテムの集合が変更されたときに
                                        発行されるシグナル。
                                        引数として dict (カテゴリ名 ->アイテムIDのset) を渡します。
        addCategoryRequested (pyqtSignal): 「カテゴリ追加」ボタンがクリックされたときに
                                           発行されるシグナル。
        addItemRequested (pyqtSignal): 「アイテム追加」ボタンがクリックされたときに発行されるシグナル。
                                       引数として str (現在のカテゴリ名) を渡します。
        current_project_dir_name (str): 現在操作対象のプロジェクトのディレクトリ名。
        category_tab_widget (QTabWidget): カテゴリを表示するためのタブウィジェット。
        checked_data_items (dict): {カテゴリ名: {アイテムIDのセット}} の形式で、
                                   チェックされているアイテムを保持します。
        _detail_window (DetailWindow | None): アイテム詳細表示用のウィンドウインスタンス。
    """
    checkedItemsChanged = pyqtSignal(dict)
    """pyqtSignal: チェックされたアイテムの集合が変更されたときに発行されます。
    
    引数:
        checked_items (dict): {category_name (str): set_of_item_ids (set[str])}
    """
    addCategoryRequested = pyqtSignal()
    """pyqtSignal: 「カテゴリ追加」ボタンがクリックされたときに発行されます。"""
    addItemRequested = pyqtSignal(str)
    """pyqtSignal: 「アイテム追加」ボタンがクリックされたときに発行されます。
    
    引数:
        category_name (str): アイテムを追加する対象の現在のカテゴリ名。
    """

    def __init__(self, project_dir_name: str, parent: QWidget | None = None):
        """DataManagementWidgetのコンストラクタ。

        Args:
            project_dir_name (str): 初期表示するプロジェクトのディレクトリ名。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
        """
        super().__init__(parent)
        self.current_project_dir_name: str = project_dir_name
        """str: 現在このウィジェットが表示・操作しているプロジェクトのディレクトリ名。"""
        # self.category_item_lists は廃止 (QTabWidgetから直接取得)
        self.checked_data_items: dict[str, set[str]] = {}
        """dict[str, set[str]]: {カテゴリ名: {アイテムIDのセット}} の形式で、
        チェックされているアイテムを保持します。
        """
        self._detail_window: DetailWindow | None = None
        """DetailWindow | None: アイテム詳細表示用のウィンドウのインスタンス。
        必要になるまで作成されません (遅延初期化)。
        """
        self._last_detail_item: dict[str, str | None] = {"category": None, "id": None}
        """dict[str, str | None]: 最後に詳細表示したアイテムのカテゴリとID。"""

        print(f"DataManagementWidget __init__ for project '{self.current_project_dir_name}'")
        self.init_ui()

    def set_project(self, project_dir_name: str):
        """表示・操作対象のプロジェクトを変更し、UIを更新します。

        MainWindowなど、外部から呼び出されることを想定しています。

        Args:
            project_dir_name (str): 新しく設定するプロジェクトのディレクトリ名。
        """
        print(f"DataManagementWidget: Setting project to '{project_dir_name}'")
        old_project = self.current_project_dir_name
        self.current_project_dir_name = project_dir_name
        self.checked_data_items.clear() # プロジェクト変更時はチェック状態をリセット
        self.refresh_categories_and_tabs() # UI全体を再構築・更新

        # 詳細ウィンドウが開いていれば閉じる (または内容をクリアする)
        if self._detail_window and self._detail_window.isVisible():
            self._detail_window.close()
            self._last_detail_item = {"category": None, "id": None} # 最後に表示したアイテム情報もリセット

        self._update_checked_items_signal() # チェック状態変更シグナルを発行 (空になったことを通知)
        print(f"  DataManagementWidget set_project: Project changed from '{old_project}' to '{self.current_project_dir_name}'. UI refreshed.")

    def init_ui(self):
        """UI要素を初期化し、レイアウトを設定します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # ウィジェット自身の余白はなし

        # --- カテゴリ追加ボタン ---
        category_button_layout = QHBoxLayout()
        self.add_category_button = QPushButton("カテゴリ追加")
        self.add_category_button.setToolTip("新しいデータカテゴリを作成します。")
        self.add_category_button.clicked.connect(self.addCategoryRequested.emit)
        category_button_layout.addWidget(self.add_category_button)
        category_button_layout.addStretch() # ボタンを左寄せ
        main_layout.addLayout(category_button_layout)

        # --- カテゴリタブウィジェット ---
        self.category_tab_widget = QTabWidget()
        self.category_tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.category_tab_widget)

        # --- アイテム操作ボタン ---
        item_button_layout = QHBoxLayout()
        self.add_item_button = QPushButton("アイテム追加")
        self.add_item_button.setToolTip("現在のカテゴリに新しいアイテムを追加します。")
        self.add_item_button.clicked.connect(self._request_add_item)
        item_button_layout.addWidget(self.add_item_button)

        self.delete_checked_items_button = QPushButton("チェックしたアイテムを削除")
        self.delete_checked_items_button.setToolTip("現在のカテゴリでチェックされているアイテムを全て削除します。")
        self.delete_checked_items_button.clicked.connect(self.delete_checked_items)
        item_button_layout.addWidget(self.delete_checked_items_button)
        item_button_layout.addStretch() # ボタンを左寄せ
        main_layout.addLayout(item_button_layout)

        self.refresh_categories_and_tabs() # 初期データ表示
        self.ensure_detail_window_exists() # 詳細ウィンドウのインスタンスを準備 (表示はしない)

    def refresh_categories_and_tabs(self):
        """カテゴリ一覧を読み込み、タブを再構築し、表示中のタブのアイテムリストを更新します。"""
        self.category_tab_widget.blockSignals(True) # 更新中のシグナル発行を抑制
        print(f"\n--- DataWidget DEBUG: Refreshing categories for project '{self.current_project_dir_name}' ---")

        previous_selected_tab_text = self.category_tab_widget.tabText(self.category_tab_widget.currentIndex())
        self.category_tab_widget.clear() # 既存のタブとそれに含まれるウィジェットを全て削除

        categories = list_categories(self.current_project_dir_name)
        print(f"  Loaded categories: {categories}")
        if not categories: # カテゴリが一つもなければデフォルトで「未分類」を作成
            if create_category(self.current_project_dir_name, "未分類"):
                categories.append("未分類")
            print(f"    Categories after potential default creation: {categories}")

        # チェック状態辞書から、存在しなくなったカテゴリのエントリを削除 (任意)
        self.checked_data_items = {
            cat: ids for cat, ids in self.checked_data_items.items() if cat in categories
        }

        idx_to_select = 0 # 新しく選択するタブのインデックス
        if categories: # カテゴリが存在する場合のみタブを作成
            for i, category_name in enumerate(categories):
                list_widget_for_tab = QListWidget(self.category_tab_widget) # 親をタブウィジェットに指定
                # list_widget_for_tab.setObjectName(f"listWidget_{category_name.replace(' ', '_')}") # デバッグ用
                self.category_tab_widget.addTab(list_widget_for_tab, category_name)
                if category_name == previous_selected_tab_text:
                    idx_to_select = i # 前に選択していたタブを再選択
        else: # カテゴリが一つもない場合
            idx_to_select = -1 # 選択するタブなし

        selected_category_for_initial_refresh = None
        if idx_to_select != -1:
            self.category_tab_widget.setCurrentIndex(idx_to_select) # タブを選択
            selected_category_for_initial_refresh = self.category_tab_widget.tabText(idx_to_select)
            print(f"  Current tab set to index {idx_to_select} ('{selected_category_for_initial_refresh}') with signals blocked.")
            # シグナルブロック中にリストを直接更新 (setCurrentIndexのシグナルは発行されないため)
            print(f"  Manually refreshing list for '{selected_category_for_initial_refresh}' during tab rebuild.")
            self.refresh_item_list_for_category(selected_category_for_initial_refresh)
        else:
            print(f"  No tabs exist or to be selected.")
            self._update_checked_items_signal() # タブがない場合もチェック状態(空)を通知

        self.category_tab_widget.blockSignals(False) # シグナル発行を再開
        print(f"--- DataWidget DEBUG: Finished refreshing categories and tabs for project '{self.current_project_dir_name}' ---")

    def _on_tab_changed(self, index: int):
        """カテゴリタブがユーザー操作などで切り替わったときに呼び出されるスロット。

        Args:
            index (int): 新しく選択されたタブのインデックス。選択が外れた場合は -1。
        """
        if index != -1:
            category_name = self.category_tab_widget.tabText(index)
            print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index {index}, category '{category_name}'. Refreshing list... ---")
            self.refresh_item_list_for_category(category_name)
        else: # 通常はタブが0個にならない限り-1にはならない
            print(f"\n--- DataWidget DEBUG: _on_tab_changed: Tab changed to index -1 (no tab selected). ---")

    def refresh_item_list_for_category(self, category_name: str):
        """指定されたカテゴリのアイテムリストウィジェットの内容を更新します。

        Args:
            category_name (str): アイテムリストを更新するカテゴリの名前。
        """
        print(f"\n--- DataWidget DEBUG: Attempting to refresh item list for category: '{category_name}' in project '{self.current_project_dir_name}' ---")

        list_widget_to_update = None
        # 指定されたカテゴリ名に一致するタブのQListWidgetを取得
        for i in range(self.category_tab_widget.count()):
            if self.category_tab_widget.tabText(i) == category_name:
                widget_candidate = self.category_tab_widget.widget(i)
                if isinstance(widget_candidate, QListWidget):
                    list_widget_to_update = widget_candidate
                    print(f"  Found QListWidget for '{category_name}' (tab index {i}): {list_widget_to_update}")
                    break # 見つかったのでループ終了
        
        if list_widget_to_update is None:
            print(f"  ★★★ CRITICAL ERROR: QListWidget for category '{category_name}' could not be found in QTabWidget. Aborting refresh. ★★★")
            return

        list_widget_to_update.clear()
        print(f"  List widget for '{category_name}' cleared.")

        items_info = list_items(self.current_project_dir_name, category_name)
        checked_ids_in_category = self.checked_data_items.get(category_name, set())

        if not items_info:
            print(f"  -> No items found for '{category_name}'.")
        else:
            print(f"  -> Found {len(items_info)} items for '{category_name}'. Adding to list...")
            for item_info in items_info:
                item_id = item_info.get('id')
                item_name = item_info.get('name', 'N/A')
                if not item_id: continue # IDがないデータは無視

                is_checked = item_id in checked_ids_in_category
                
                list_item_container = QListWidgetItem(list_widget_to_update) # QListWidgetにアイテムコンテナを追加
                custom_item_widget = DataItemWidget(item_name, item_id, is_checked) # カスタムウィジェット作成
                
                # シグナル接続
                custom_item_widget.checkStateChanged.connect(
                    lambda checked_state, cat=category_name, iid=item_id:
                        self._handle_item_check_change(cat, iid, checked_state)
                )
                custom_item_widget.detailRequested.connect(
                    lambda cat=category_name, iid=item_id:
                        self.show_detail_window(cat, iid)
                )
                
                list_item_container.setSizeHint(custom_item_widget.sizeHint())
                list_widget_to_update.setItemWidget(list_item_container, custom_item_widget) # コンテナにカスタムウィジェットをセット
        print(f"--- DataWidget DEBUG: Finished refreshing item list for '{category_name}' ---")


    def add_new_category_result(self, category_name: str):
        """MainWindowからのカテゴリ名入力結果を受けて、カテゴリを作成しUIを更新します。

        Args:
            category_name (str): 作成する新しいカテゴリの名前。
        """
        if category_name: # 空でないことを確認
            if create_category(self.current_project_dir_name, category_name):
                self.refresh_categories_and_tabs() # カテゴリタブを再構築
                # 新しく追加されたタブを選択状態にする
                for i in range(self.category_tab_widget.count()):
                    if self.category_tab_widget.tabText(i) == category_name:
                        self.category_tab_widget.setCurrentIndex(i)
                        break
            else: # 作成失敗 (既に存在する場合など)
                QMessageBox.warning(self, "カテゴリ作成エラー",
                                    f"カテゴリ '{category_name}' の作成に失敗しました。\n既に存在する可能性があります。")
        # else: 空の場合は何もしない (MainWindow側で警告済みのはず)

    def _handle_item_check_change(self, category: str, item_id: str, is_checked: bool):
        """アイテムのチェック状態が変更されたときの内部処理。

        `self.checked_data_items` を更新し、`checkedItemsChanged` シグナルを発行します。
        アイテムがチェックされた場合は、詳細ウィンドウも表示します。

        Args:
            category (str): チェック状態が変更されたアイテムのカテゴリ名。
            item_id (str): チェック状態が変更されたアイテムのID。
            is_checked (bool): 新しいチェック状態 (True: チェック済み, False: 未チェック)。
        """
        print(f"Data Item Check changed: Project='{self.current_project_dir_name}', Category='{category}', ID='{item_id}', Checked={is_checked}")
        if category not in self.checked_data_items:
            self.checked_data_items[category] = set()

        if is_checked:
            self.checked_data_items[category].add(item_id)
            self.show_detail_window(category, item_id) # チェック時に詳細表示
        else:
            self.checked_data_items[category].discard(item_id)
        
        self._update_checked_items_signal()

    def _update_checked_items_signal(self):
        """`checkedItemsChanged` シグナルを発行します。"""
        self.checkedItemsChanged.emit(self.checked_data_items.copy()) # コピーを渡す

    def get_checked_items(self) -> dict[str, set[str]]:
        """現在チェックされているアイテムの情報を取得します。

        Returns:
            dict[str, set[str]]: {カテゴリ名: {アイテムIDのセット}} の形式の辞書。
        """
        return self.checked_data_items.copy() # 内部状態のコピーを返す

    def _request_add_item(self):
        """「アイテム追加」ボタンがクリックされたときの処理。

        現在のカテゴリ名を引数として `addItemRequested` シグナルを発行します。
        """
        current_index = self.category_tab_widget.currentIndex()
        if current_index != -1:
            current_category_name = self.category_tab_widget.tabText(current_index)
            self.addItemRequested.emit(current_category_name)
        else:
            QMessageBox.warning(self, "カテゴリ未選択", "アイテムを追加するカテゴリを選択してください。\nカテゴリがない場合は、まず「カテゴリ追加」から作成してください。")

    def add_new_item_result(self, category_name: str, item_name: str):
        """MainWindowからのアイテム名入力結果を受けて、アイテムを追加しUIを更新します。

        Args:
            category_name (str): アイテムを追加するカテゴリの名前。
            item_name (str): 作成する新しいアイテムの名前。
        """
        if category_name and item_name: # 両方とも空でないことを確認
            # 新規アイテムのデフォルトデータ構造
            new_item_data = {
                "name": item_name,
                "description": "", # 初期は空
                "history": [],
                "tags": [],
                "image_path": None
            }
            new_item_id = add_item(self.current_project_dir_name, category_name, new_item_data)
            if new_item_id:
                self.refresh_item_list_for_category(category_name) # リストを更新
                # オプション: 追加したアイテムをチェック状態にするなど
            else:
                QMessageBox.warning(self, "アイテム追加エラー",
                                    f"アイテム '{item_name}' のカテゴリ '{category_name}' への追加に失敗しました。")
        # else: 空の場合は何もしない (MainWindow側で警告済みのはず)

    def delete_checked_items(self):
        """現在表示中のカテゴリでチェックされているアイテムを全て削除します。"""
        current_tab_index = self.category_tab_widget.currentIndex()
        if current_tab_index == -1:
            QMessageBox.warning(self, "カテゴリ未選択", "削除するアイテムが含まれるカテゴリを選択してください。")
            return
        current_category_name = self.category_tab_widget.tabText(current_tab_index)
        
        ids_to_delete = self.checked_data_items.get(current_category_name, set()).copy() # コピーして操作
        if not ids_to_delete:
            QMessageBox.information(self, "アイテム未選択", "削除するアイテムがチェックされていません。")
            return

        reply = QMessageBox.question(self, "削除確認",
                                   f"カテゴリ '{current_category_name}' のチェックされた {len(ids_to_delete)} 個のアイテムを本当に削除しますか？\nこの操作は元に戻せません。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            deleted_count = 0
            # カテゴリデータを一度ロードし、メモリ上で変更後、一括で保存する
            category_data = load_data_category(self.current_project_dir_name, current_category_name)
            if category_data is None: # 読み込み失敗
                QMessageBox.critical(self, "データエラー", f"カテゴリ '{current_category_name}' のデータの読み込みに失敗したため、削除処理を中止します。")
                return

            items_actually_deleted_from_data = 0
            for item_id in ids_to_delete:
                if item_id in category_data:
                    del category_data[item_id]
                    items_actually_deleted_from_data +=1
            
            if items_actually_deleted_from_data > 0:
                if save_data_category(self.current_project_dir_name, current_category_name, category_data):
                    QMessageBox.information(self, "削除完了", f"{items_actually_deleted_from_data} 個のアイテムを削除しました。")
                    deleted_count = items_actually_deleted_from_data
                else:
                    QMessageBox.warning(self, "保存エラー", "アイテム削除後のデータ保存に失敗しました。データが不整合な状態になっている可能性があります。")
                    # 失敗時はリフレッシュしない方が良いかもしれない
                    return # 以降の処理を中断
            elif ids_to_delete: # チェックはあったが、データには存在しなかった場合
                 QMessageBox.information(self, "削除なし", "チェックされたアイテムはデータ内に見つかりませんでした（既に削除されたか、データ不整合の可能性）。")


            if deleted_count > 0 or items_actually_deleted_from_data == 0 and ids_to_delete:
                # 削除成功時、または削除対象があったがデータになかった場合 (チェックは外す)
                if current_category_name in self.checked_data_items:
                    self.checked_data_items[current_category_name].clear() # チェック状態をクリア
                self.refresh_item_list_for_category(current_category_name) # リスト更新
                self._update_checked_items_signal()


    def ensure_detail_window_exists(self):
        """`_detail_window` インスタンスが存在し、必要な設定がされていることを保証します。"""
        if self._detail_window is None:
            # MainWindowインスタンスを取得し、そこから設定情報をDetailWindowに渡す
            main_window_instance = self.window() # このウィジェットのトップレベルウィンドウを取得
            main_win_project_settings = {}
            main_win_global_config = {}
            if main_window_instance and hasattr(main_window_instance, 'current_project_settings'):
                main_win_project_settings = main_window_instance.current_project_settings
            if main_window_instance and hasattr(main_window_instance, 'global_config'):
                main_win_global_config = main_window_instance.global_config

            detail_main_config = {
                "model": main_win_project_settings.get("model",
                                                     main_win_global_config.get("default_model", "gemini-1.5-pro-latest"))
                # 他に DetailWindow が必要とするグローバル設定があればここに追加
            }
            self._detail_window = DetailWindow(
                main_config=detail_main_config,
                project_dir_name=self.current_project_dir_name, # ★ ここで渡す
                parent=None # 独立ウィンドウなので親はNoneで良い (または QApplication.activeWindow())
            )
            self._detail_window.dataSaved.connect(self._handle_detail_saved)
            self._detail_window.windowClosed.connect(self._handle_detail_closed)
            print(f"DetailWindow instance created for project '{self.current_project_dir_name}'.")
        elif self._detail_window.current_project_dir_name != self.current_project_dir_name:
            # DetailWindowが既に存在するが、DataManagementWidgetのプロジェクトが変わった場合
            # DetailWindowのプロジェクトも更新する
            self._detail_window.current_project_dir_name = self.current_project_dir_name
            # 必要ならDetailWindowの表示内容もクリア
            self._detail_window.clear_view()
            print(f"DetailWindow project updated to '{self.current_project_dir_name}'.")


    def show_detail_window(self, category: str, item_id: str):
        """指定されたアイテムの詳細表示ウィンドウを表示（またはアクティブ化）します。

        Args:
            category (str): 表示するアイテムのカテゴリ名。
            item_id (str): 表示するアイテムのID。
        """
        self.ensure_detail_window_exists()
        self._last_detail_item = {"category": category, "id": item_id}

        # DetailWindowに渡すmain_config (主にモデル名) を最新に保つ
        # (ensure_detail_window_exists で初期設定されるが、プロジェクトモデル変更後に呼ばれる可能性も考慮)
        main_window_instance = self.window()
        if main_window_instance and hasattr(main_window_instance, 'current_project_settings') and self._detail_window:
            project_model = main_window_instance.current_project_settings.get('model')
            if project_model:
                 self._detail_window.main_config["model"] = project_model

        # 位置調整ロジック (メインウィンドウの右隣に表示)
        main_win_global_pos = self.window().mapToGlobal(QPoint(0,0))
        main_win_width = self.window().width()
        main_win_height = self.window().height()
        screen_geo = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else self.window().geometry()

        detail_width = 500
        detail_height = main_win_height
        new_x = main_win_global_pos.x() + main_win_width + 5
        new_y = main_win_global_pos.y()

        # 画面外にはみ出ないように調整
        if new_x + detail_width > screen_geo.right(): new_x = main_win_global_pos.x() - detail_width - 5
        if new_x < screen_geo.left(): new_x = screen_geo.left()
        if new_y < screen_geo.top(): new_y = screen_geo.top()
        if new_y + detail_height > screen_geo.bottom():
            detail_height = screen_geo.bottom() - new_y
            if detail_height < 200: detail_height = 200 # 最小高さを確保
            if new_y + detail_height > screen_geo.bottom(): new_y = screen_geo.bottom() - detail_height

        self._detail_window.setGeometry(new_x, new_y, detail_width, detail_height)
        self._detail_window.load_data(category, item_id) # DetailWindow が自身のプロジェクト名でロード

        if not self._detail_window.isVisible():
            self._detail_window.show()
        self._detail_window.activateWindow()
        self._detail_window.raise_()


    def _handle_detail_saved(self, category: str, item_id: str):
        """DetailWindowでデータが保存されたときに呼び出されるスロット。

        対応するカテゴリのアイテムリストを更新します。

        Args:
            category (str): 保存されたアイテムのカテゴリ名。
            item_id (str): 保存されたアイテムのID。 (現在は未使用)
        """
        print(f"DataWidget: Detail saved for Category='{category}', ItemID='{item_id}' in project '{self.current_project_dir_name}'. Refreshing list.")
        if self.category_tab_widget.tabText(self.category_tab_widget.currentIndex()) == category:
            self.refresh_item_list_for_category(category) # 現在表示中のタブなら更新
        else:
            # 表示中でないタブのデータが更新された場合、次回そのタブが表示されたときに更新される
            print(f"  (Data for category '{category}' was saved, but it's not the currently active tab. Will refresh when tab becomes active.)")


    def _handle_detail_closed(self):
        """DetailWindowが閉じられたときに呼び出されるスロット。"""
        self._last_detail_item = {"category": None, "id": None}
        print("DataWidget: Detail window closed.")

    # --- ★★★ クイックセット適用用: 全アイテムのチェックを外すメソッド ★★★ ---
    def uncheck_all_items(self):
        """管理している全てのアイテムのチェックを外します。"""
        if not hasattr(self, 'category_tab_widget'):
            print("DataManagementWidget: category_tab_widget not found, cannot uncheck items.")
            return

        for i in range(self.category_tab_widget.count()):
            tab_widget = self.category_tab_widget.widget(i)
            if isinstance(tab_widget, QListWidget):
                list_widget = tab_widget
                for j in range(list_widget.count()):
                    item_widget = list_widget.itemWidget(list_widget.item(j))
                    if isinstance(item_widget, DataItemWidget):
                        item_widget.set_checked_state(False)

        self.checked_data_items.clear()
        self._update_checked_items_signal()
        print("DataManagementWidget: All items unchecked.")

    # --- ★★★ クイックセット適用用: 指定されたアイテムをチェックするメソッド ★★★ ---
    def check_items_by_dict(self, items_to_check: Dict[str, List[str]]):
        """指定されたカテゴリとアイテムIDの辞書に基づいて、アイテムにチェックを入れます。
        このメソッドを呼び出す前に uncheck_all_items() で全てのチェックが
        外されていることを前提とすることが多いです。

        Args:
            items_to_check (Dict[str, List[str]]): 
                チェックを入れるアイテムの辞書。キーはカテゴリ名、値はアイテムIDのリスト。
                例: {"キャラクター": ["char_id_1", "char_id_2"], "場所": ["loc_id_1"]}
        """
        if not hasattr(self, 'category_tab_widget'):
            print("DataManagementWidget: category_tab_widget not found, cannot check items.")
            return
        
        # items_to_check が空の場合でも、以前のチェック状態をクリアして通知する必要がある
        self.checked_data_items.clear() 

        if not items_to_check:
            self._update_checked_items_signal() # 空の状態を通知
            print("DataManagementWidget: No items to check, all checks cleared.")
            return

        print(f"DataManagementWidget: Checking items by dict: {items_to_check}")
        checked_count = 0

        for category_name, item_ids_to_check in items_to_check.items():
            tab_index = -1
            for i in range(self.category_tab_widget.count()):
                if self.category_tab_widget.tabText(i) == category_name:
                    tab_index = i
                    break
            
            if tab_index == -1:
                print(f"  Warning: Category tab '{category_name}' not found.")
                continue

            tab_widget = self.category_tab_widget.widget(tab_index)
            if isinstance(tab_widget, QListWidget):
                list_widget = tab_widget
                # カテゴリが存在し、チェック対象アイテムがある場合、そのカテゴリのチェック状態を初期化
                current_category_checks = self.checked_data_items.setdefault(category_name, set())
                current_category_checks.clear()

                for j in range(list_widget.count()):
                    list_item_q = list_widget.item(j)
                    item_widget = list_widget.itemWidget(list_item_q)

                    if isinstance(item_widget, DataItemWidget):
                        item_id_in_list = item_widget.item_id
                        if item_id_in_list in item_ids_to_check:
                            item_widget.set_checked_state(True)
                            current_category_checks.add(item_id_in_list)
                            checked_count += 1
                        else:
                            item_widget.set_checked_state(False)

        # 存在しないカテゴリが items_to_check に含まれていた場合、そのキーは checked_data_items に残らないようにする
        # (setdefault で作られてしまう可能性があるため、実在するタブのカテゴリのみ保持)
        active_categories_in_tabs = {self.category_tab_widget.tabText(i) for i in range(self.category_tab_widget.count())}
        self.checked_data_items = {
            cat: ids for cat, ids in self.checked_data_items.items() if cat in active_categories_in_tabs and ids
        }

        print(f"  DataManagementWidget: {checked_count} items checked based on the dict.")
        self._update_checked_items_signal()


if __name__ == '__main__':
    """DataManagementWidget の基本的な表示・インタラクションテスト。"""
    app = QApplication(sys.argv)

    # --- テスト用のダミープロジェクトとデータ準備 ---
    test_project_dm_widget = "dm_widget_test_project"
    # core.config_manager のテストとは別のプロジェクト名を使用

    # 既存のテストプロジェクトがあればクリーンアップ
    import shutil
    test_project_base_path = os.path.join("data", test_project_dm_widget)
    if os.path.exists(test_project_base_path):
        shutil.rmtree(test_project_base_path)
    os.makedirs(os.path.join(test_project_base_path, "gamedata"), exist_ok=True) # gamedataも作成

    # ダミーのカテゴリとアイテムを作成 (data_manager を使用)
    # dm_create_cat(test_project_dm_widget, "キャラクター")
    # dm_create_cat(test_project_dm_widget, "魔法")
    # dm_add_item(test_project_dm_widget, "キャラクター", {"id": "char01", "name": "勇者エルウィン"})
    # dm_add_item(test_project_dm_widget, "キャラクター", {"id": "char02", "name": "魔導士ルナ"})
    # dm_add_item(test_project_dm_widget, "魔法", {"id": "spell01", "name": "ファイアボール"})
    # -------------------------------------------------

    # DataManagementWidget のインスタンス作成と表示
    # MainWindow が存在しないテスト環境なので、DetailWindow に渡す config はダミー
    class DummyMainWindow(QWidget): # DetailWindowに渡すためのダミー親
        def __init__(self):
            super().__init__()
            self.current_project_settings = {"model": "gemini-1.5-pro-latest"}
            self.global_config = {"default_model": "gemini-1.5-pro-latest", "available_models": ["gemini-1.5-pro-latest"]}

    dummy_main_win = DummyMainWindow() # DetailWindowがwindow()で参照する想定
    
    data_widget = DataManagementWidget(project_dir_name=test_project_dm_widget, parent=dummy_main_win)
    data_widget.setWindowTitle("Data Management Widget Test")
    data_widget.setMinimumSize(400, 500)

    # シグナル接続テスト (コンソール出力)
    data_widget.checkedItemsChanged.connect(
        lambda items: print(f"\n--- Signal: checkedItemsChanged: {items} ---")
    )
    data_widget.addCategoryRequested.connect(
        lambda: print("\n--- Signal: addCategoryRequested ---")
    )
    data_widget.addItemRequested.connect(
        lambda cat: print(f"\n--- Signal: addItemRequested for Category='{cat}' ---")
    )

    data_widget.show()
    app_exit_code = app.exec_()

    # --- テスト後クリーンアップ ---
    if os.path.exists(test_project_base_path):
        shutil.rmtree(test_project_base_path)
    # ---------------------------
    sys.exit(app_exit_code)
