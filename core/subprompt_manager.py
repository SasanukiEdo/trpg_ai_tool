# core/subprompt_manager.py

"""プロジェクトごとのサブプロンプトデータの読み書きを管理するモジュール。

サブプロンプトは、プロジェクトディレクトリ内の 'subprompts.json' という名前の
JSONファイルに保存されます。各サブプロンプトはカテゴリ別にグループ化され、
プロンプト本文と使用するAIモデル名（任意）を持ちます。

主な機能:
    - load_subprompts: 指定されたプロジェクトのサブプロンプトを読み込む。
    - save_subprompts: 指定されたプロジェクトのサブプロンプトを保存する。
"""

import json
import os

# --- 定数 ---
PROJECTS_BASE_DIR = "data"
"""str: 全てのプロジェクトディレクトリが格納されるベースディレクトリのパス。
config_manager.py と共通。
"""

SUBPROMPTS_FILENAME = "subprompts.json"
"""str: 各プロジェクトディレクトリ内に作成されるサブプロンプトファイルの名前。"""

# --- デフォルトのサブプロンプトデータ ---
DEFAULT_SUBPROMPTS_DATA = {}
"""dict: サブプロンプトファイルが存在しない場合や、
ファイル内容が不正な場合に返されるデフォルトのデータ（空の辞書）。
"""

def get_subprompts_file_path(project_dir_name: str) -> str:
    """指定されたプロジェクトディレクトリ名に対応するサブプロンプトファイルのフルパスを返します。

    Args:
        project_dir_name (str): プロジェクトのディレクトリ名。

    Returns:
        str: サブプロンプトファイル (subprompts.json) のフルパス。
    """
    if not project_dir_name:
        # プロジェクト名が空の場合は、デフォルトのパスを返すかエラーを出すか検討。
        # ここでは、呼び出し元が有効なプロジェクト名を渡すことを期待する。
        # もしエラーにするなら: raise ValueError("Project directory name cannot be empty.")
        print("Warning: project_dir_name is empty in get_subprompts_file_path. Returning path based on empty name.")
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name, SUBPROMPTS_FILENAME)

def load_subprompts(project_dir_name: str) -> dict:
    """指定されたプロジェクトのサブプロンプトをファイルから読み込みます。

    ファイルが存在しない場合は、デフォルトの空のデータでファイルを作成し、それを返します。
    JSONのデコードに失敗した場合なども、デフォルトの空データを返します。

    Args:
        project_dir_name (str): 読み込むサブプロンプトが含まれるプロジェクトのディレクトリ名。

    Returns:
        dict: 読み込まれたサブプロンプトデータ。
              キーはカテゴリ名、値はそのカテゴリ内のサブプロンプト名と詳細の辞書。
              例: {"カテゴリ1": {"プロンプト名1": {"prompt": "...", "model": "..."}}}
    """
    if not project_dir_name:
        print("Error: Project directory name is required to load subprompts.")
        return DEFAULT_SUBPROMPTS_DATA.copy()

    file_path = get_subprompts_file_path(project_dir_name)
    project_path = os.path.dirname(file_path)

    if not os.path.exists(file_path):
        print(f"サブプロンプトファイルが見つかりません: {file_path}")
        if not os.path.exists(project_path):
            print(f"  プロジェクトディレクトリも存在しません: {project_path} (作成を試みます)")
            try:
                os.makedirs(project_path, exist_ok=True)
                print(f"  プロジェクトディレクトリを作成しました: {project_path}")
            except Exception as e:
                print(f"  プロジェクトディレクトリの作成に失敗しました ({project_path}): {e}")
                return DEFAULT_SUBPROMPTS_DATA.copy()

        print(f"  デフォルトのサブプロンプトファイル ({SUBPROMPTS_FILENAME}) を作成します。")
        if save_subprompts(project_dir_name, DEFAULT_SUBPROMPTS_DATA.copy()): # 空のデータを保存
            print(f"  デフォルトのサブプロンプトファイルを作成・保存しました: {file_path}")
            return DEFAULT_SUBPROMPTS_DATA.copy()
        else:
            print(f"  デフォルトのサブプロンプトファイルの作成に失敗しました ({file_path})。")
            return DEFAULT_SUBPROMPTS_DATA.copy()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            subprompts = json.load(f)
        print(f"サブプロンプトを読み込みました: {file_path}")
        # データ構造のバリデーション (任意だが推奨)
        # 例えば、各サブプロンプトが "prompt" キーを持つかなど
        if not isinstance(subprompts, dict):
            print(f"Warning: サブプロンプトファイルのルートが辞書形式ではありません ({file_path})。デフォルトデータを返します。")
            return DEFAULT_SUBPROMPTS_DATA.copy()
        return subprompts
    except json.JSONDecodeError:
        print(f"エラー: サブプロンプトファイル ({file_path}) のJSON形式が正しくありません。デフォルトデータを返します。")
        return DEFAULT_SUBPROMPTS_DATA.copy()
    except Exception as e:
        print(f"サブプロンプトファイルの読み込み中に予期せぬエラーが発生しました ({file_path}): {e}")
        return DEFAULT_SUBPROMPTS_DATA.copy()

def save_subprompts(project_dir_name: str, subprompts_data: dict) -> bool:
    """指定されたプロジェクトのサブプロンプトデータをファイルに保存します。

    プロジェクトディレクトリが存在しない場合は、途中のディレクトリも含めて作成します。

    Args:
        project_dir_name (str): 保存するサブプロンプトが含まれるプロジェクトのディレクトリ名。
        subprompts_data (dict): 保存するサブプロンプトデータ。
                                  キーはカテゴリ名、値はそのカテゴリ内のサブプロンプト名と詳細の辞書。

    Returns:
        bool: 保存が成功した場合は True、失敗した場合は False。
    """
    if not project_dir_name:
        print("Error: Project directory name is required to save subprompts.")
        return False

    file_path = get_subprompts_file_path(project_dir_name)
    project_dir_path = os.path.dirname(file_path)
    try:
        os.makedirs(project_dir_path, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(subprompts_data, f, indent=4, ensure_ascii=False)
        print(f"サブプロンプトを保存しました: {file_path}")
        return True
    except Exception as e:
        print(f"サブプロンプトの保存に失敗しました ({file_path}): {e}")
        return False

if __name__ == '__main__':
    """モジュールの基本的な動作をテストするためのコード。"""
    print("--- SubPrompt Manager テスト ---")

    test_project_name = "test_project_for_subprompts"

    # 1. 初回読み込みテスト (プロジェクトディレクトリとファイルがなければ作成される)
    print(f"\n1. 初回読み込みテスト (プロジェクト: {test_project_name})")
    initial_subprompts = load_subprompts(test_project_name)
    print(f"   読み込まれたデータ (初回): {initial_subprompts}")
    if initial_subprompts == DEFAULT_SUBPROMPTS_DATA:
        print("   初回読み込みは期待通りデフォルトデータです。")
    else:
        print("   エラー: 初回読み込みデータが期待と異なります。")

    # 2. サブプロンプトデータの作成と保存
    print(f"\n2. データ保存テスト (プロジェクト: {test_project_name})")
    sample_subprompts = {
        "一般": {
            "挨拶": {"prompt": "こんにちは、マスター！", "model": "gemini-1.5-flash-latest"},
            "感謝": {"prompt": "いつもありがとうございます。", "model": ""}
        },
        "状況説明": {
            "天気": {"prompt": "今日の天気は晴れです。", "model": "gemini-1.5-pro-latest"}
        }
    }
    save_success = save_subprompts(test_project_name, sample_subprompts)
    if save_success:
        print("   サンプルデータの保存に成功しました。")
    else:
        print("   エラー: サンプルデータの保存に失敗しました。")

    # 3. 保存後の再読み込みテスト
    print(f"\n3. 再読み込みテスト (プロジェクト: {test_project_name})")
    reloaded_subprompts = load_subprompts(test_project_name)
    print(f"   読み込まれたデータ (保存後): {reloaded_subprompts}")
    if reloaded_subprompts == sample_subprompts:
        print("   保存と再読み込みが正しく行われました。")
    else:
        print("   エラー: 保存されたデータが期待と異なります。")

    # 4. 空のプロジェクト名でのテスト (エラーまたは警告を期待)
    print("\n4. 空のプロジェクト名テスト")
    empty_project_name_result_load = load_subprompts("")
    print(f"   空プロジェクト名でのload結果: {empty_project_name_result_load} (デフォルトデータのはず)")
    empty_project_name_result_save = save_subprompts("", {"test": "data"})
    print(f"   空プロジェクト名でのsave結果: {empty_project_name_result_save} (Falseのはず)")


    # 既存の 'default_project' があれば、それに対する操作もテスト可能
    print("\n5. 'default_project' のサブプロンプト操作テスト")
    default_project_subprompts = load_subprompts("default_project")
    print(f"   default_project の現在のサブプロンプト: {default_project_subprompts}")
    # 何か追加してみる
    default_project_subprompts.setdefault("テストカテゴリ", {})["テストプロンプト"] = {"prompt": "テストです"}
    if save_subprompts("default_project", default_project_subprompts):
        print("   default_project にテストデータを保存しました。")
        loaded_after_save = load_subprompts("default_project")
        if "テストカテゴリ" in loaded_after_save and "テストプロンプト" in loaded_after_save["テストカテゴリ"]:
            print("   default_project への保存と再読み込み成功。")
        else:
            print("   エラー: default_project への保存・再読み込みに失敗。")

    print("\n--- テスト完了 ---")
