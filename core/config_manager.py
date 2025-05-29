# core/config_manager.py

"""アプリケーションのグローバル設定およびプロジェクト固有設定の管理モジュール。

グローバル設定は 'data/config.json' に、プロジェクト固有設定は
'data/{プロジェクトディレクトリ名}/project_settings.json' に保存されます。

主な機能:
    - グローバル設定の読み込み/保存 (load_global_config, save_global_config)
    - プロジェクト設定の読み込み/保存 (load_project_settings, save_project_settings)
    - プロジェクトディレクトリの一覧取得 (list_project_dir_names)
"""

import json
import os
import shutil

# --- 定数 ---
CONFIG_FILE_PATH = os.path.join("data", "config.json")
"""str: グローバル設定ファイルのパス。"""

PROJECTS_BASE_DIR = "data"
"""str: 全てのプロジェクトディレクトリが格納されるベースディレクトリのパス。"""

PROJECT_SETTINGS_FILENAME = "project_settings.json"
"""str: 各プロジェクトディレクトリ内に作成されるプロジェクト設定ファイルの名前。"""

# --- グローバル設定のデフォルト値 ---
DEFAULT_GLOBAL_CONFIG = {
    "active_project": "default_project",    # 現在アクティブなプロジェクトのディレクトリ名
    "default_model": "gemini-1.5-pro-latest", # 新規プロジェクト作成時のデフォルトモデル
    "available_models": [                   # 利用可能なAIモデルのリスト
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
        "gemini-pro",
        "gemini-1.5-flash",
        "gemini-pro"
    ],
    "generation_temperature": 0.7,
    "generation_top_p": 0.95,
    "generation_top_k": 40,
    "generation_max_output_tokens": 2048,
    "font_family": "MS Gothic",
    "font_size": 10,
    "font_color_user": "#0000FF",       # 青
    "font_color_model": "#008000",      # 緑
    "font_color_model_latest": "#FF0000", # 赤
    "font_line_height": 1.5,
}
"""dict: グローバル設定ファイルが存在しない場合や、キーが不足している場合に使用されるデフォルト値。"""

# --- プロジェクト設定のデフォルト値 ---
DEFAULT_PROJECT_SETTINGS = {
    "project_display_name": "デフォルトプロジェクト", # プロジェクトの表示名 (UI用)
    "main_system_prompt": "あなたは優秀なAIアシスタントです。", # プロジェクトのメインシステムプロンプト
    "model": "gemini-1.5-pro-latest",              # プロジェクトで使用するAIモデル
    "ai_edit_model_name": ""                       # AI編集支援機能で使用するモデル名 (空白時はプロジェクトモデルを使用)
}
"""dict: プロジェクト設定ファイルが存在しない場合や、キーが不足している場合に使用されるデフォルト値。"""

# --- クイックセットのファイル名・スロット数 ---
QUICK_SETS_FILENAME = "quick_sets.json"
NUM_QUICK_SET_SLOTS = 10 # クイックセットのスロット数


# --- グローバル設定の読み書き ---

def load_global_config() -> dict:
    """グローバル設定ファイル (config.json) を読み込みます。

    ファイルが存在しない場合は、デフォルト設定で新規作成し、その内容を返します。
    既存ファイルにキーが不足している場合は、デフォルト値で補完します。

    Returns:
        dict: 読み込まれた、または新規作成されたグローバル設定。
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"グローバル設定ファイルが見つかりません。デフォルト設定で作成します: {CONFIG_FILE_PATH}")
        save_global_config(DEFAULT_GLOBAL_CONFIG.copy()) # 保存してから返す
        return DEFAULT_GLOBAL_CONFIG.copy()
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        # 足りないキーがあればデフォルト値で補完
        for key, default_value in DEFAULT_GLOBAL_CONFIG.items():
            if key not in config:
                config[key] = default_value
        print(f"グローバル設定を読み込みました: {CONFIG_FILE_PATH}")
        return config
    except Exception as e:
        print(f"グローバル設定ファイルの読み込みに失敗しました ({CONFIG_FILE_PATH}): {e}")
        return DEFAULT_GLOBAL_CONFIG.copy() # エラー時はデフォルト値を返す

def save_global_config(config_data: dict) -> bool:
    """グローバル設定データ (config.json) をファイルに保存します。

    Args:
        config_data (dict): 保存するグローバル設定の辞書。

    Returns:
        bool: 保存が成功した場合は True、失敗した場合は False。
    """
    try:
        # 保存先ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        print(f"グローバル設定を保存しました: {CONFIG_FILE_PATH}")
        return True
    except Exception as e:
        print(f"グローバル設定の保存に失敗しました ({CONFIG_FILE_PATH}): {e}")
        return False


# --- プロジェクト設定の読み書き ---

def get_project_dir_path(project_dir_name: str) -> str:
    """指定されたプロジェクトディレクトリ名に対応するフルパスを返します。

    Args:
        project_dir_name (str): プロジェクトのディレクトリ名。

    Returns:
        str: プロジェクトディレクトリのフルパス。
    """
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name)

def get_project_settings_path(project_dir_name: str) -> str:
    """指定されたプロジェクトディレクトリ名に対応する設定ファイルのフルパスを返します。

    Args:
        project_dir_name (str): プロジェクトのディレクトリ名。

    Returns:
        str: プロジェクト設定ファイル (project_settings.json) のフルパス。
    """
    return os.path.join(get_project_dir_path(project_dir_name), PROJECT_SETTINGS_FILENAME)

def load_project_settings(project_dir_name: str) -> dict | None:
    """指定されたプロジェクトの設定ファイル (project_settings.json) を読み込みます。

    プロジェクトディレクトリまたは設定ファイルが存在しない場合は、
    デフォルト設定で新規作成（ディレクトリも含む）し、その内容を返します。
    読み込みや作成に失敗した場合は None を返します。

    Args:
        project_dir_name (str): 読み込むプロジェクトのディレクトリ名。

    Returns:
        dict | None: 読み込まれた、または新規作成されたプロジェクト設定。
                     失敗した場合は None。
    """
    project_settings_file = get_project_settings_path(project_dir_name)
    project_dir = os.path.dirname(project_settings_file)

    if not os.path.exists(project_settings_file):
        print(f"プロジェクト設定ファイルが見つかりません: {project_settings_file}")
        if not os.path.exists(project_dir):
            print(f"  プロジェクトディレクトリも存在しません: {project_dir} (作成を試みます)")
        else:
            print(f"  プロジェクトディレクトリは存在しますが、設定ファイルがありません。 (作成します)")

        # デフォルト設定で新規作成
        default_settings = DEFAULT_PROJECT_SETTINGS.copy()
        # 表示名はディレクトリ名から初期設定 (ユーザーが後で変更可能)
        default_settings["project_display_name"] = project_dir_name
        # 新規プロジェクトのモデルはグローバル設定の default_model を使用
        global_conf = load_global_config() # ここでグローバル設定を一度読む
        default_settings["model"] = global_conf.get("default_model", DEFAULT_PROJECT_SETTINGS["model"])


        if save_project_settings(project_dir_name, default_settings):
            print(f"  デフォルト設定でプロジェクト '{project_dir_name}' を初期化し、保存しました。")
            return default_settings
        else:
            print(f"  プロジェクト '{project_dir_name}' の初期化（デフォルト設定保存）に失敗しました。")
            return None

    try:
        with open(project_settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        # 足りないキーがあればデフォルト値で補完
        for key, default_value in DEFAULT_PROJECT_SETTINGS.items():
            if key not in settings:
                settings[key] = default_value
        # ai_edit_model_nameが古い設定ファイルに存在しない場合の互換性処理
        if "ai_edit_model_name" not in settings:
            settings["ai_edit_model_name"] = DEFAULT_PROJECT_SETTINGS["ai_edit_model_name"]
        print(f"プロジェクト設定を読み込みました: {project_settings_file}")
        return settings
    except Exception as e:
        print(f"プロジェクト設定ファイル ({project_settings_file}) の読み込みに失敗しました: {e}")
        return None # エラー時は None を返す

def save_project_settings(project_dir_name: str, settings_data: dict) -> bool:
    """指定されたプロジェクトの設定データ (project_settings.json) をファイルに保存します。

    プロジェクトディレクトリが存在しない場合は、途中のディレクトリも含めて作成します。

    Args:
        project_dir_name (str): 保存するプロジェクトのディレクトリ名。
        settings_data (dict): 保存するプロジェクト設定の辞書。

    Returns:
        bool: 保存が成功した場合は True、失敗した場合は False。
    """
    project_settings_file = get_project_settings_path(project_dir_name)
    project_dir = os.path.dirname(project_settings_file)
    try:
        os.makedirs(project_dir, exist_ok=True) # ディレクトリがなければ作成
        with open(project_settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=4, ensure_ascii=False)
        print(f"プロジェクト設定を保存しました: {project_settings_file}")
        return True
    except Exception as e:
        print(f"プロジェクト設定 ({project_settings_file}) の保存に失敗しました: {e}")
        return False

# --- プロジェクト一覧取得 ---

def list_project_dir_names() -> list[str]:
    """data フォルダ直下の有効なプロジェクトディレクトリ名のリストを返します。

    PROJECTS_BASE_DIR ('data') の直下にあるディレクトリのうち、
    実際にプロジェクトディレクトリとみなせるもの（例: '.' で始まらないなど、
    将来的なフィルタリングも考慮可能）をソートして返します。

    Returns:
        list[str]: 見つかったプロジェクトディレクトリ名のソート済みリスト。
                   ベースディレクトリが存在しない場合は空リスト。
    """
    if not os.path.exists(PROJECTS_BASE_DIR):
        print(f"プロジェクトベースディレクトリが見つかりません: {PROJECTS_BASE_DIR}")
        return []
    try:
        project_dirs = [
            d for d in os.listdir(PROJECTS_BASE_DIR)
            if os.path.isdir(os.path.join(PROJECTS_BASE_DIR, d))
            # ここにさらにフィルタ条件を追加可能 (例: d.startswith('.') でないもの)
        ]
        # print(f"検出されたプロジェクトディレクトリ候補: {project_dirs}")
        return sorted(project_dirs)
    except Exception as e:
        print(f"プロジェクトディレクトリのリスト取得に失敗しました ({PROJECTS_BASE_DIR}): {e}")
        return []


# --- プロジェクトディレクトリ削除 ---
def delete_project_directory(project_dir_name: str) -> bool:
    """指定されたプロジェクトのディレクトリ全体を削除します。

    これには、プロジェクト設定ファイル、サブプロンプトファイル、
    gamedataディレクトリなど、プロジェクトに関連する全てのファイルと
    フォルダが含まれます。操作は元に戻せません。

    Args:
        project_dir_name (str): 削除するプロジェクトのディレクトリ名。

    Returns:
        bool: ディレクトリの削除に成功した場合は True、
              ディレクトリが存在しない場合や削除に失敗した場合は False。
    """
    if not project_dir_name:
        print("Error: Project directory name cannot be empty for deletion.")
        return False

    project_path_to_delete = get_project_dir_path(project_dir_name)

    if not os.path.exists(project_path_to_delete) or not os.path.isdir(project_path_to_delete):
        print(f"Info: Project directory to delete not found or not a directory: {project_path_to_delete}")
        return False # 削除対象がない

    try:
        shutil.rmtree(project_path_to_delete)
        print(f"Project directory '{project_path_to_delete}' and all its contents have been deleted.")
        return True
    except Exception as e:
        print(f"Error deleting project directory '{project_path_to_delete}': {e}")
        return False


if __name__ == '__main__':
    """モジュールのテスト実行用コード。"""
    print("--- Config Manager テスト ---")

    # 1. グローバル設定テスト
    print("\n1. グローバル設定テスト:")
    global_cfg = load_global_config()
    print(f"   読み込み時: {global_cfg}")
    original_active_project = global_cfg.get("active_project")
    global_cfg["active_project"] = "test_global_save_project"
    save_global_config(global_cfg)
    reloaded_global_cfg = load_global_config()
    print(f"   保存・再読み込み後: {reloaded_global_cfg}")
    # テスト後は元に戻す (任意)
    if original_active_project:
        reloaded_global_cfg["active_project"] = original_active_project
        save_global_config(reloaded_global_cfg)

    # 2. プロジェクト設定テスト (新規作成と読み込み)
    print("\n2. 新規プロジェクト設定テスト (project_alpha):")
    project_alpha_name = "project_alpha"
    # まずは存在しない状態でロード (デフォルトで作成されるはず)
    alpha_settings = load_project_settings(project_alpha_name)
    if alpha_settings:
        print(f"   {project_alpha_name} (初回ロード/作成時): {alpha_settings}")
        # 内容を変更して保存
        alpha_settings["main_system_prompt"] = "Alphaプロジェクトのカスタムプロンプト。"
        alpha_settings["project_display_name"] = "アルファ計画"
        save_project_settings(project_alpha_name, alpha_settings)
        reloaded_alpha_settings = load_project_settings(project_alpha_name)
        print(f"   {project_alpha_name} (変更保存・再読み込み後): {reloaded_alpha_settings}")
        if reloaded_alpha_settings and reloaded_alpha_settings["project_display_name"] == "アルファ計画":
            print("   プロジェクト設定の保存・読み込みテスト成功。")
        else:
            print("   プロジェクト設定の保存・読み込みテスト失敗。")
    else:
        print(f"   {project_alpha_name} の設定の読み込み/作成に失敗しました。")

    # 3. 既存の 'default_project' のテスト (存在すれば読み込み、なければ作成)
    print("\n3. 'default_project' 設定テスト:")
    default_proj_settings = load_project_settings("default_project")
    if default_proj_settings:
        print(f"   default_project 設定: {default_proj_settings}")
    else:
        print(f"   default_project の設定の読み込み/作成に失敗しました。")


    # 4. プロジェクト一覧テスト
    print("\n4. プロジェクト一覧テスト:")
    all_projects = list_project_dir_names()
    print(f"   検出されたプロジェクトディレクトリ: {all_projects}")
    if project_alpha_name in all_projects and "default_project" in all_projects:
        print("   プロジェクト一覧の取得は期待通りです。")
    elif not all_projects:
        print("   プロジェクトはまだ作成されていません。")
    else:
        print(f"   プロジェクト一覧の取得結果が一部期待と異なります: {all_projects}")


    # 5. 存在しないプロジェクト設定ファイルの読み込みエラーテスト (ディレクトリはあるがファイルなし)
    print("\n5. 破損/不正なプロジェクト設定ファイルテスト (project_beta):")
    project_beta_name = "project_beta"
    project_beta_dir = get_project_dir_path(project_beta_name)
    os.makedirs(project_beta_dir, exist_ok=True) # ディレクトリだけ作成
    project_beta_settings_file = get_project_settings_path(project_beta_name)
    # 不正なJSONファイルを作成
    with open(project_beta_settings_file, 'w', encoding='utf-8') as f:
        f.write("{ \"project_display_name\": \"Beta\", \"model\": ") # 途中で切れたJSON
    
    beta_settings_corrupted = load_project_settings(project_beta_name)
    if beta_settings_corrupted is None: # JSONDecodeError などで None が返ることを期待
        print(f"   {project_beta_name} (不正なJSONファイル時): 読み込み失敗 (None) - 期待通り。")
    else:
        print(f"   {project_beta_name} (不正なJSONファイル時): 読み込み結果 {beta_settings_corrupted} - 期待外れ。")
    # テスト用に作成したディレクトリとファイルを削除 (任意)
    if os.path.exists(project_beta_settings_file): os.remove(project_beta_settings_file)
    if os.path.exists(project_beta_dir) and not os.listdir(project_beta_dir): os.rmdir(project_beta_dir)


    print("\n--- テスト完了 ---")
