# main.py の内容 (アプリケーション起動用)

import sys
import os
from PyQt5.QtWidgets import QApplication

# --- プロジェクトルートをパスに追加 ---
# main.py がルートにあるので、この操作は厳密には不要かもしれないが、
# 他のモジュールが正しく core や ui を見つけられるように念のため入れておく
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- メインウィンドウをインポート ---
# ui パッケージの main_window モジュールから MainWindow クラスをインポート
from ui.main_window import MainWindow

# --- アプリケーションの起動 ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
    
