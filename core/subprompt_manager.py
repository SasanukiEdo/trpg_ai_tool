# core/subprompt_manager.py

import json
import os

# --- 定数 ---
PROJECTS_BASE_DIR = "data"  # config_manager と同じベースディレクトリ
SUBPROMPTS_FILENAME = "subprompts.json" # 新しいファイル名

# --- デフォルトのサブプロンプトデータ (空の辞書) ---
DEFAULT_SUBPROMPTS_DATA = {}

def get_subprompts_file_path(project_dir_name):
    """指定されたプロジェクトディレクトリ名に対応するサブプロンプトファイルのパスを返す"""
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name, SUBPROMPTS_FILENAME)

def load_subprompts(project_dir_name):
    """
    指定されたプロジェクトのサブプロンプトをファイルから読み込む。
    ファイルが存在しない場合は、デフォルトの空のデータでファイルを作成し、それを返す。
    """
    file_path = get_subprompts_file_path(project_dir_name)
    project_path = os.path.dirname(file_path) # プロジェクトのディレクトリパス

    if not os.path.exists(file_path):
        print(f"サブプロンプトファイルが見つかりません: {file_path}")
        # プロジェクトフォルダ自体が存在しない場合も考慮 (通常は config_manager で作成済みのはず)
        if not os.path.exists(project_path):
            print(f"  プロジェクトフォルダも存在しません: {project_path} (作成を試みます)")
            try:
                os.makedirs(project_path, exist_ok=True)
                print(f"  プロジェクトフォルダを作成しました: {project_path}")
            except Exception as e:
                print(f"  プロジェクトフォルダの作成に失敗しました: {e}")
                return DEFAULT_SUBPROMPTS_DATA.copy() # エラー時はデフォルトを返す

        print(f"  デフォルトのサブプロンプトファイルを作成します。")
        if save_subprompts(project_dir_name, DEFAULT_SUBPROMPTS_DATA):
            return DEFAULT_SUBPROMPTS_DATA.copy()
        else:
            print(f"  デフォルトのサブプロンプトファイルの作成に失敗しました。")
            return DEFAULT_SUBPROMPTS_DATA.copy() # 保存失敗時もデフォルト

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            subprompts = json.load(f)
            # ここでデータ構造のバリデーションやマイグレーションを行うことも可能
            return subprompts
    except json.JSONDecodeError:
        print(f"エラー: サブプロンプトファイル ({file_path}) のJSON形式が正しくありません。")
        # 破損時はデフォルトで上書きするか、エラーを通知するか検討。
        # 今回はデフォルトを返し、次回保存時に上書きされることを期待。
        return DEFAULT_SUBPROMPTS_DATA.copy()
    except Exception as e:
        print(f"サブプロンプトファイルの読み込み中に予期せぬエラーが発生しました ({file_path}): {e}")
        return DEFAULT_SUBPROMPTS_DATA.copy()

def save_subprompts(project_dir_name, subprompts_data):
    """指定されたプロジェクトのサブプロンプトデータをファイルに保存する"""
    file_path = get_subprompts_file_path(project_dir_name)
    project_dir_path = os.path.dirname(file_path)
    try:
        os.makedirs(project_dir_path, exist_ok=True) # 保存先のディレクトリがなければ作成
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(subprompts_data, f, indent=4, ensure_ascii=False)
        print(f"サブプロンプトを保存しました: {file_path}")
        return True
    except Exception as e:
        print(f"サブプロンプトの保存に失敗しました ({file_path}): {e}")
        return False

if __name__ == '__main__':
    # --- テストコード ---
    test_project = "test_subprompt_project" # テスト用のプロジェクト名

    # 1. 初回読み込み (ファイルとフォルダがなければ作成される)
    print(f"\n--- 初回読み込みテスト ({test_project}) ---")
    loaded_data1 = load_subprompts(test_project)
    print(f"読み込まれたデータ (初回): {loaded_data1}")
    if not loaded_data1: # 空の辞書が返るはず
        print("初回読み込みは空の辞書です。")

    # 2. データの追加と保存
    print(f"\n--- データ追加と保存テスト ({test_project}) ---")
    new_data = {
        "一般": {
            "あいさつ": {"prompt": "こんにちは！", "model": "gemini-1.5-pro-latest"},
            "自己紹介": {"prompt": "私の名前はユノです。", "model": "gemini-1.5-pro-latest"}
        },
        "戦闘": {
            "攻撃ロール": {"prompt": "攻撃します！ {{dice:1d20+5}}", "model": "gemini-1.5-flash-latest"}
        }
    }
    if save_subprompts(test_project, new_data):
        print("データの保存に成功しました。")
    else:
        print("データの保存に失敗しました。")

    # 3. 保存後の再読み込み
    print(f"\n--- 再読み込みテスト ({test_project}) ---")
    loaded_data2 = load_subprompts(test_project)
    print(f"読み込まれたデータ (保存後): {loaded_data2}")
    if loaded_data2 == new_data:
        print("保存と再読み込みが正しく行われました。")
    else:
        print("エラー: 保存されたデータが期待と異なります。")

    # 4. 既存の 'default_project' に対するテスト (config_managerで作成されているはず)
    print(f"\n--- default_project 読み込みテスト ---")
    default_project_subs = load_subprompts("default_project")
    print(f"default_project のサブプロンプト: {default_project_subs}")
    if default_project_subs == {}: # 初回は空のはず
         print("default_project のサブプロンプトは期待通り空です。")
    # default_project に何か保存してみる
    default_project_subs["案内"] = {"ようこそ": {"prompt": "ようこそ、TRPG AI Toolへ！"}}
    save_subprompts("default_project", default_project_subs)
    loaded_default_after_save = load_subprompts("default_project")
    print(f"保存後の default_project のサブプロンプト: {loaded_default_after_save}")

