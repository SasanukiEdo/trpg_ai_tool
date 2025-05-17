# main.py の内容 (アプリケーション起動用)

import sys
import os
from PyQt5.QtWidgets import QApplication, qApp
from ui.main_window import MainWindow # MainWindow をインポート

from typing import Optional

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- ★★★ グローバル変数として MainWindow インスタンスを保持 ★★★ ---
main_window_instance: Optional[MainWindow] = None # 型ヒント (Optional)
# --- ★★★ ------------------------------------------------- ★★★ ---

if __name__ == '__main__':
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
    # --- ★★★ --------------------------------------- ★★★ ---

    # --- ★★★ MainWindow インスタンスをグローバル変数に代入 ★★★ ---
    main_window_instance = MainWindow() 

    # ------------------------------------------------------------------------
    # テストコード記述用スペース
    # ------------------------------------------------------------------------
    #print(main_win.get_recent_chat_history_as_string(3))



    # ------------------------------------------------------------------------
    
    # if hasattr(QApplication, 'main_window'):
    #     QApplication.main_window = main_window_instance
    # else:
    #     qApp.main_window = main_window_instance

    main_window_instance.show()
    sys.exit(app.exec_())

