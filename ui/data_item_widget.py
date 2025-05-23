# ui/data_item_widget.py

"""データ管理ウィジェットのアイテムリストに表示される各項目用のカスタムウィジェット。

このウィジェットは、アイテム名、チェックボックス、および詳細表示ボタンを含みます。
チェック状態の変更や詳細表示要求をシグナルで通知します。
"""

from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QCheckBox, QPushButton, QStyle,
    QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

class DataItemWidget(QWidget):
    """データアイテムリストの単一行を表すカスタムウィジェット。

    アイテム名、チェックボックス、詳細表示ボタンを提供します。

    Attributes:
        checkStateChanged (pyqtSignal): チェックボックスの状態が変更されたときに
                                        発行されるシグナル。bool型の状態を渡します。
        detailRequested (pyqtSignal): 詳細表示ボタンがクリックされたときに
                                      発行されるシグナル。
    """
    checkStateChanged = pyqtSignal(bool)
    """pyqtSignal: チェックボックスの状態が変更されたときに発行されます。
    
    シグナルは引数として bool (True: チェック済み, False: 未チェック) を渡します。
    """

    detailRequested = pyqtSignal()
    """pyqtSignal: 詳細表示ボタンがクリックされたときに発行されます。"""

    def __init__(self, item_name: str, item_id: str, is_checked: bool = False, parent: QWidget | None = None):
        """DataItemWidgetのコンストラクタ。

        Args:
            item_name (str): 表示するアイテムの名前。
            item_id (str): このアイテムの一意なID。主に内部処理で使用。
            is_checked (bool, optional): チェックボックスの初期状態。
                                         デフォルトは False。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
        """
        super().__init__(parent)
        self.item_id = item_id
        """str: このウィジェットが表すアイテムの一意なID。"""
        self.item_name = item_name
        """str: 表示されているアイテムの名前。"""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2) # 上下左右の余白を小さめに設定

        # チェックボックス (アイテム名を表示)
        self.checkbox = QCheckBox(self.item_name)
        self.checkbox.setChecked(is_checked)
        self.checkbox.stateChanged.connect(self._on_check_state_changed)
        # チェックボックスが利用可能なスペースを最大限に使うようにする
        self.checkbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.checkbox)

        # 詳細表示ボタン
        self.detail_button = QPushButton()
        # 標準アイコンを使用 (例: 情報アイコンや編集アイコンなど)
        # SP_DialogApplyButton, SP_FileDialogDetailedView, SP_ToolBarHorizontalExtensionButton
        self.detail_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogInfoView)) # SP_FileDialogDetailedView
        self.detail_button.setToolTip(f"「{self.item_name}」の詳細を表示/編集")
        self.detail_button.setFixedSize(24, 24) # ボタンサイズを固定
        self.detail_button.clicked.connect(self.detailRequested.emit)
        layout.addWidget(self.detail_button)

        self.setLayout(layout)

    def _on_check_state_changed(self, state: int):
        """チェックボックスの状態が変更されたときに内部的に呼ばれるスロット。

        `checkStateChanged` シグナルを発行します。

        Args:
            state (int): Qt.Checked または Qt.Unchecked の状態。
        """
        is_checked_bool = (state == Qt.Checked)
        self.checkStateChanged.emit(is_checked_bool)

    def set_name(self, name: str):
        """ウィジェットに表示されるアイテム名を更新します。

        Args:
            name (str): 新しいアイテム名。
        """
        self.item_name = name
        self.checkbox.setText(self.item_name)
        self.detail_button.setToolTip(f"「{self.item_name}」の詳細を表示/編集")


    def set_checked_state(self, checked: bool):
        """チェックボックスの状態をプログラムから設定します。

        このメソッドは `checkStateChanged` シグナルを発行しません。
        UIからの操作と区別するためです。

        Args:
            checked (bool): 新しいチェック状態 (True: チェック済み, False: 未チェック)。
        """
        # シグナルループを防ぐために一時的にブロックする (任意だが安全)
        # self.checkbox.blockSignals(True)
        self.checkbox.setChecked(checked)
        # self.checkbox.blockSignals(False)
        self.checkbox.repaint() # ★★★ update() から repaint() に変更 ★★★

    def is_checked(self) -> bool:
        """現在のチェックボックスの状態を返します。

        Returns:
            bool: チェックされていれば True、そうでなければ False。
        """
        return self.checkbox.isChecked()

if __name__ == '__main__':
    """DataItemWidgetのテスト用実行コード。"""
    import sys
    from PyQt5.QtWidgets import QApplication, QListWidget, QListWidgetItem

    app = QApplication(sys.argv)

    # テスト用のQListWidgetを作成
    list_widget = QListWidget()
    list_widget.setWindowTitle("DataItemWidget Test")
    list_widget.setMinimumSize(300, 200)

    # いくつかのDataItemWidgetを追加
    items_data = [
        {"name": "戦士アルド", "id": "char-001", "checked": True},
        {"name": "魔法使いリナ", "id": "char-002", "checked": False},
        {"name": "ポーション", "id": "item-001", "checked": True},
        {"name": "古い地図", "id": "item-002", "checked": False},
    ]

    for item_d in items_data:
        data_item = DataItemWidget(item_d["name"], item_d["id"], item_d["checked"])

        # シグナル接続テスト (コンソールに出力)
        data_item.checkStateChanged.connect(
            lambda checked, name=item_d["name"]: print(f"Check state changed for '{name}': {checked}")
        )
        data_item.detailRequested.connect(
            lambda name=item_d["name"]: print(f"Detail requested for '{name}'")
        )

        list_item_container = QListWidgetItem(list_widget) # QListWidgetItemが必要
        list_item_container.setSizeHint(data_item.sizeHint())
        list_widget.addItem(list_item_container)
        list_widget.setItemWidget(list_item_container, data_item)


    # DataItemWidgetのメソッドテスト (例: 最初のアイテムの名前とチェック状態を変更)
    if list_widget.count() > 0:
        first_list_item = list_widget.item(0)
        first_data_widget = list_widget.itemWidget(first_list_item) # itemWidgetで取得
        if isinstance(first_data_widget, DataItemWidget):
            print("\nTesting set_name() and set_checked_state() on the first item...")
            first_data_widget.set_name("勇者アルド")
            first_data_widget.set_checked_state(False) # シグナルは発行されないはず
            print(f"First item new name: {first_data_widget.item_name}")
            print(f"First item new checked state (from is_checked()): {first_data_widget.is_checked()}")


    list_widget.show()
    sys.exit(app.exec_())

