# core/config_manager.py

import json
import os

# --- 定数 ---
CONFIG_FILE_PATH = os.path.join("data", "config.json")
PROJECTS_BASE_DIR = "data"
PROJECT_SETTINGS_FILENAME = "project_settings.json"

# --- グローバル設定のデフォルト ---
DEFAULT_GLOBAL_CONFIG = {
    "active_project": "default_project",
    "default_model": "gemini-1.5-pro-latest"
}

# --- プロジェクト設定のデフォルト ---
DEFAULT_PROJECT_SETTINGS = {
    "project_display_name": "デフォルトプロジェクト",
    "main_system_prompt": "あなたは優秀なAIアシスタントです。",
    "model": "gemini-1.5-pro-latest"
}

# --- グローバル設定の読み書き (変更なし) ---
def load_global_config():
    # ... (前回のコードのまま)
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"グローバル設定ファイルが見つかりません。デフォルト設定で作成します: {CONFIG_FILE_PATH}")
        save_global_config(DEFAULT_GLOBAL_CONFIG)
        return DEFAULT_GLOBAL_CONFIG.copy()
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            for key, value in DEFAULT_GLOBAL_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        print(f"グローバル設定ファイルの読み込みに失敗しました: {e}")
        return DEFAULT_GLOBAL_CONFIG.copy()

def save_global_config(config_data):
    # ... (前回のコードのまま)
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        print(f"グローバル設定を保存しました: {CONFIG_FILE_PATH}")
        return True
    except Exception as e:
        print(f"グローバル設定の保存に失敗しました: {e}")
        return False

# --- プロジェクト設定の読み書き ---
def get_project_settings_path(project_dir_name):
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name, PROJECT_SETTINGS_FILENAME)

# --- ★★★ 修正箇所 ★★★ ---
def load_project_settings(project_dir_name):
    """指定されたプロジェクトの設定 (project_settings.json) を読み込む"""
    project_settings_file = get_project_settings_path(project_dir_name)
    project_dir_path = os.path.dirname(project_settings_file)

    if not os.path.exists(project_settings_file):
        print(f"プロジェクト設定ファイルが見つかりません: {project_settings_file}")
        # プロジェクトフォルダが存在しない場合でも、save_project_settings が作成を試みる
        if not os.path.exists(project_dir_path):
             print(f"  プロジェクトフォルダも現時点では存在しません: {project_dir_path} (作成を試みます)")
        else:
            print(f"  プロジェクトフォルダは存在しますが、設定ファイルがありません: {project_dir_path} (作成します)")

        print(f"  デフォルトのプロジェクト設定ファイルを作成・保存します。")
        default_settings_for_project = DEFAULT_PROJECT_SETTINGS.copy()
        # プロジェクトディレクトリ名を表示名として初期設定
        default_settings_for_project["project_display_name"] = project_dir_name
        # model はグローバル設定の default_model を参照しても良いが、
        # ここでは DEFAULT_PROJECT_SETTINGS の model を使う
        # default_settings_for_project["model"] = load_global_config().get("default_model", DEFAULT_PROJECT_SETTINGS["model"])


        # save_project_settings を呼び出してファイルを作成（この関数内でフォルダも作成される）
        if save_project_settings(project_dir_name, default_settings_for_project):
            print(f"  デフォルト設定でプロジェクト '{project_dir_name}' を初期化（保存完了）。")
            return default_settings_for_project # 保存成功したので、その内容を返す
        else:
            print(f"  プロジェクト '{project_dir_name}' の初期化（デフォルト設定保存）に失敗しました。")
            return None # 保存失敗

    # 設定ファイルが存在する場合の処理 (変更なし)
    try:
        with open(project_settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            for key, value in DEFAULT_PROJECT_SETTINGS.items(): # デフォルト値で補完
                if key not in settings:
                    settings[key] = value
            return settings
    except Exception as e:
        print(f"プロジェクト設定ファイル ({project_settings_file}) の読み込みに失敗しました: {e}")
        # 読み込みエラー時、Noneを返すか、デフォルトを返すか検討。
        # ここではNoneを返し、呼び出し元でエラーハンドリングする余地を残す。
        return None
# --- ★★★ 修正箇所ここまで ★★★ ---

def save_project_settings(project_dir_name, settings_data):
    """指定されたプロジェクトの設定 (project_settings.json) を保存する"""
    project_settings_file = get_project_settings_path(project_dir_name)
    try:
        project_dir_path = os.path.dirname(project_settings_file)
        os.makedirs(project_dir_path, exist_ok=True) # フォルダがなければ作成 (exist_ok=True は重要)
        with open(project_settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=4, ensure_ascii=False)
        print(f"プロジェクト設定を保存しました: {project_settings_file}")
        return True
    except Exception as e:
        print(f"プロジェクト設定 ({project_settings_file}) の保存に失敗しました: {e}")
        return False

# --- プロジェクト一覧取得 (変更なし) ---
def list_project_dir_names():
    # ... (前回のコードのまま)
    if not os.path.exists(PROJECTS_BASE_DIR):
        return []
    try:
        project_dirs = [
            d for d in os.listdir(PROJECTS_BASE_DIR)
            if os.path.isdir(os.path.join(PROJECTS_BASE_DIR, d))
        ]
        return sorted(project_dirs)
    except Exception as e:
        print(f"プロジェクトディレクトリのリスト取得に失敗しました: {e}")
        return []

# --- テストコード (変更なし) ---
if __name__ == '__main__':
    # ... (前回のテストコードのままで、修正後の load_project_settings の動作を確認)
    print("--- グローバル設定テスト ---")
    g_config = load_global_config()
    print(f"読み込み: {g_config}")
    g_config["active_project"] = "test_project_1"
    save_global_config(g_config)
    g_config_reloaded = load_global_config()
    print(f"再読み込み: {g_config_reloaded}")

    print("\n--- プロジェクト設定テスト (my_test_campaign) ---")
    test_project_name_1 = "my_test_campaign"
    p_settings_1 = load_project_settings(test_project_name_1)
    if p_settings_1:
        print(f"読み込み/作成結果 ({test_project_name_1}): {p_settings_1}")
        p_settings_1["main_system_prompt"] = "これはテストキャンペーンのメインプロンプトです。"
        p_settings_1["model"] = "gemini-pro"
        p_settings_1["project_display_name"] = "私のテストキャンペーン"
        save_project_settings(test_project_name_1, p_settings_1)
        p_settings_1_reloaded = load_project_settings(test_project_name_1)
        print(f"再読み込み ({test_project_name_1}): {p_settings_1_reloaded}")
    else:
        print(f"プロジェクト '{test_project_name_1}' の設定の読み込み/作成に失敗しました。")


    print("\n--- プロジェクト一覧テスト ---")
    projects = list_project_dir_names()
    print(f"現在のプロジェクトディレクトリ: {projects}")

    print("\n--- default_project の初期設定テスト ---")
    # default_project がなければ作成されるはず
    dp_settings = load_project_settings("default_project")
    if dp_settings:
         print(f"default_project の設定: {dp_settings}")
    else:
        print("default_project の設定の読み込み/作成に失敗しました。")

    projects_after = list_project_dir_names()
    print(f"最終的なプロジェクトディレクトリ: {projects_after}")
