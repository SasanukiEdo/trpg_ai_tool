# ui/data_item_widget.py

from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QCheckBox, QPushButton, QSizePolicy, QStyle, qApp
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize

# ==============================================================================
# データ項目用カスタムウィジェット
# ==============================================================================
class DataItemWidget(QWidget):
    # シグナル定義
    checkStateChanged = pyqtSignal(bool) # is_checked
    detailRequested = pyqtSignal()   # 詳細表示要求
    # deleteRequested = pyqtSignal() # ここに削除ボタンは付けない（リストの下に配置）

    def __init__(self, name, item_id, is_checked=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.item_id = item_id

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        # チェックボックス
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(is_checked)
        self.checkbox.stateChanged.connect(self._on_check_state_changed)
        layout.addWidget(self.checkbox)

        # アイテム名ラベル
        self.label = QLabel(name)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.label)

        # 詳細表示ボタン (アイコン)
        self.detail_button = QPushButton()
        detail_icon = qApp.style().standardIcon(QStyle.SP_FileDialogInfoView) # 情報アイコン
        self.detail_button.setIcon(detail_icon)
        self.detail_button.setFixedSize(QSize(24, 24))
        self.detail_button.setToolTip("詳細を表示/編集")
        self.detail_button.clicked.connect(self._on_detail_requested)
        layout.addWidget(self.detail_button)

        self.setLayout(layout)

    def _on_check_state_changed(self, state):
        is_checked = (state == Qt.Checked)
        self.checkStateChanged.emit(is_checked)

    def _on_detail_requested(self):
        self.detailRequested.emit()

    def setChecked(self, is_checked):
        self.checkbox.setChecked(is_checked)

    def isChecked(self):
        return self.checkbox.isChecked()

    # 行クリックでトグル
    def mousePressEvent(self, event):
        if not self.detail_button.geometry().contains(event.pos()):
            self.checkbox.toggle()

