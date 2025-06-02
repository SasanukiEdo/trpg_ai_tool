# main.py の内容 (アプリケーション起動用)

import sys
import os
from PyQt5.QtWidgets import QApplication, qApp
from PyQt5.QtCore import Qt
from typing import Optional # Optional をインポート
from ui.main_window import MainWindow # MainWindow をインポート
# --- ★★★ 共有インスタンスモジュールからセッターをインポート ★★★ ---
from core.shared_instances import set_main_window_instance 
# --- ★★★ ------------------------------------------------- ★★★ ---

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)



if __name__ == '__main__':
    # --- ★★★ 高DPI対応設定 ★★★ ---
    # 高DPIディスプレイでの適切なスケーリングを有効化
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # --- ★★★ ---------------- ★★★ ---
    
    app = QApplication(sys.argv)

    # --- ★★★ 外部スタイルシートの読み込みと適用 ★★★ ---
    qss_file_path = os.path.join(project_root, "ui", "style.qss")
    try:
        with open(qss_file_path, "r", encoding="utf-8") as f: # encoding を指定 [1]
            style_sheet_content = f.read()
            app.setStyleSheet(style_sheet_content) # アプリケーション全体に適用 [1][5][9]
            print(f"Stylesheet loaded from: {qss_file_path}")
    except FileNotFoundError:
        print(f"Warning: Stylesheet file not found at {qss_file_path}. Using default styles.")
    except Exception as e:
        print(f"Error loading stylesheet: {e}")
    # --- --------------------------------------- ---
    
    main_win = MainWindow() # MainWindow インスタンスを作成
    
    # --- ★★★ 作成したインスタンスを共有モジュールにセット ★★★ ---
    set_main_window_instance(main_win)



    # ------------------------------------------------------------------------
    # テストコード記述用スペース
    # ------------------------------------------------------------------------
    #print(main_win.get_recent_chat_history_as_string(3))



    # ------------------------------------------------------------------------
    
    # DetailWindow から qApp.main_window で参照する古い方法は完全に不要になる
    # if hasattr(QApplication, 'main_window'):
    #     QApplication.main_window = main_win 
    # else:
    #     qApp.main_window = main_win

    main_win.show()
    sys.exit(app.exec_())
