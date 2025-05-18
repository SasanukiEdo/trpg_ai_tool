# core/shared_instances.py

"""
アプリケーション全体で共有されるインスタンス参照を保持するモジュール。
主に MainWindow のインスタンスを他から参照可能にするために使用します。
"""

from typing import Optional, TYPE_CHECKING

# --- 型チェック時のみ MainWindow をインポート ---
# これにより、実行時の循環参照を避けつつ、開発時の型ヒントの恩恵を受けられます。
if TYPE_CHECKING:
    from ui.main_window import MainWindow # ui.main_window から MainWindow クラスをインポート

# --- 共有されるインスタンスを保持する内部変数 ---
_main_window_instance_internal: Optional['MainWindow'] = None
"""MainWindow のインスタンスを保持する内部変数。
直接アクセスせず、getter/setter を介して操作します。
型ヒント 'MainWindow' は前方参照文字列です。
"""

def set_main_window_instance(instance: Optional['MainWindow']):
    """共有する MainWindow のインスタンスを設定します。

    Args:
        instance (Optional['MainWindow']): 設定する MainWindow のインスタンス。
                                        None を設定することも可能です。
    """
    global _main_window_instance_internal
    _main_window_instance_internal = instance
    if instance is not None:
        print(f"shared_instances: MainWindow instance set: {instance}")
    else:
        print("shared_instances: MainWindow instance cleared (set to None).")


def get_main_window_instance() -> Optional['MainWindow']:
    """共有されている MainWindow のインスタンスを取得します。

    Returns:
        Optional['MainWindow']: 共有されている MainWindow のインスタンス。
                               設定されていなければ None を返します。
    """
    global _main_window_instance_internal
    # print(f"shared_instances: get_main_window_instance called, returning: {_main_window_instance_internal}") # デバッグ用
    return _main_window_instance_internal
