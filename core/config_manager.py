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
import re # reモジュールをインポート
import sys

# --- 実行ファイルの場所を基準にしたデータディレクトリのパス設定 ---
def get_base_dir():
    """実行ファイルまたはスクリプトの場所を取得"""
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた実行ファイルの場合
        return os.path.dirname(sys.executable)
    else:
        # 通常のPythonスクリプト実行の場合
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_dir()
CONFIG_FILE_PATH = os.path.join(BASE_DIR, "data", "config.json")
"""str: グローバル設定ファイルのパス。"""

PROJECTS_BASE_DIR = os.path.join(BASE_DIR, "data")
"""str: 全てのプロジェクトディレクトリが格納されるベースディレクトリのパス。"""

PROJECT_SETTINGS_FILENAME = "project_settings.json"
"""str: 各プロジェクトディレクトリ内に作成されるプロジェクト設定ファイルの名前。"""

# --- グローバル設定のデフォルト値 ---
DEFAULT_GLOBAL_CONFIG = {
    "active_project": "default_project",    # 現在アクティブなプロジェクトのディレクトリ名
    "default_model": "gemini-1.5-flash-latest", # 新規プロジェクト作成時のデフォルトモデル
    "available_models": [                   # 利用可能なAIモデルのリスト
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
        "gemini-1.0-pro-latest", # 古いモデルも例として残す
        # "gemini-ultra-latest" # 必要に応じて追加
    ],
    "send_on_enter_mode": True, # TrueならEnterで送信、FalseならCtrl+Enterで送信
    "generation_temperature": 0.7,
    "generation_top_p": 0.95,
    "generation_top_k": 40,
    "generation_max_output_tokens": 2048,
    "font_family": "MS Gothic",
    "font_size": 10,
    "font_color_user": "#444444",       # ユーザー発言のデフォルト文字色
    "font_color_model": "rgb(0, 85, 177)", # AI応答のデフォルト文字色
    "font_color_model_latest": "rgb(0, 100, 200)", # 最新のAI応答のデフォルト文字色
    "font_line_height": 1.5,
    "history_range_for_prompt": 25, # ★ 追加: 送信履歴範囲のデフォルト値
    "enable_streaming": True        # ★ 追加: ストリーミング有効化のデフォルト値
}
"""dict: グローバル設定ファイルが存在しない場合や、キーが不足している場合に使用されるデフォルト値。"""

# --- プロジェクト設定のデフォルト値 ---
DEFAULT_PROJECT_SETTINGS = {
    "project_display_name": "デフォルトプロジェクト", # プロジェクトの表示名 (UI用)
    "main_system_prompt": "あなたは優秀なAIアシスタントです。", # プロジェクトのメインシステムプロンプト
    "model": "gemini-1.5-pro-latest",              # プロジェクトで使用するAIモデル
    "ai_edit_model_name": "",                       # AI編集支援機能で使用するモデル名 (空白時はプロジェクトモデルを使用)
    # ★★★ AI編集支援用プロンプトテンプレートのデフォルト値 ★★★
    "ai_edit_prompts": {
        "description_edit": """あなたはTRPGのデータ管理を行うアシスタントです。
以下の「現在の説明/メモ」に基づいて、現在の状況を考慮して「{item_name}」の新しい「説明/メモ」を作成してください。
元の情報で重要なものが失われないようにし、説明/メモ以外の余計な情報は出力しないようにしてください。

現在の説明/メモ:
--------------------
{current_text}
--------------------
""",
        "description_new": """あなたはTRPGのデータ管理を行うアシスタントです。
「{item_name}」の「説明/メモ」を新規に作成します。
提示された項目テンプレートに基づいて内容を記述してください。
説明/メモ以外の余計な情報は出力しないでください。

項目テンプレート：
{empty_description_template}
""",
        "history_entry_add": """あなたはTRPGのデータ管理を行うアシスタントです。
ユーザーの指示に従い、「{item_name}」の履歴情報に追加するエントリーを作成してください。
エントリー内容のみを生成し、余計な情報は出力しないようにしてください。

## まとめて欲しい情報:
--------------------
[記述例]
主人公と{item_name}の現在の関係性をまとめてください。
{item_name}との会話内容をまとめてください。
クエストの進行状況をまとめてください。
現在階層のモンスター情報をまとめてください。
--------------------


### 「{item_name}」の参考情報:

説明/メモ（ここに書かれている情報は固定情報として別途保存されているため、履歴に含める必要は無い）：
--------------------
{item_description}
--------------------

直近の履歴（最大{max_item_history_entries}件）：
--------------------
{item_existing_history}
--------------------
"""
    },
    # ★★★ 「説明/メモ」空白時の項目テンプレートのデフォルト値 ★★★
    "empty_description_template": """<キャラクター>
- 種族：
- 性格：
- 口調：
- 見た目：
- 好感度：
- 性経験：
- 性感帯：
- その他情報：
- 主人公との関係性：
</キャラクター>

<アイテム>
- 種別：
- 能力・効果：
- 金額：
- その他情報：
</アイテム>

<クエスト>
- クエスト概要：
- 報酬：
- 難易度：
- 詳細なクエストシナリオ（ユーザーに分からないよう英語で記述）：
</クエスト>

<デフォルト>
自由にまとめてください。
</デフォルト>
"""
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
        # print(f"グローバル設定を読み込みました: {CONFIG_FILE_PATH}")
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
        # print(f"グローバル設定を保存しました: {CONFIG_FILE_PATH}")
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
            # print(f"  デフォルト設定でプロジェクト '{project_dir_name}' を初期化し、保存しました。")
            return default_settings
        else:
            # print(f"  プロジェクト '{project_dir_name}' の初期化（デフォルト設定保存）に失敗しました。")
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
        
        # ★★★ AI編集支援用プロンプトテンプレートの互換性処理 ★★★
        if "ai_edit_prompts" not in settings:
            settings["ai_edit_prompts"] = DEFAULT_PROJECT_SETTINGS["ai_edit_prompts"].copy()
        else: # ai_edit_prompts自体は存在する場合、中の各キーを確認
            for t_key, t_default_val in DEFAULT_PROJECT_SETTINGS["ai_edit_prompts"].items():
                if t_key not in settings["ai_edit_prompts"]:
                    settings["ai_edit_prompts"][t_key] = t_default_val
        
        # ★★★ 「説明/メモ」空白時項目テンプレートの互換性処理 ★★★
        if "empty_description_template" not in settings:
            settings["empty_description_template"] = DEFAULT_PROJECT_SETTINGS["empty_description_template"]
            
        # print(f"プロジェクト設定を読み込みました: {project_settings_file}")
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
        # print(f"プロジェクト設定を保存しました: {project_settings_file}")
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
    """指定されたプロジェクトディレクトリ全体を削除します。

    Args:
        project_dir_name (str): 削除するプロジェクトのディレクトリ名。

    Returns:
        bool: 削除が成功した場合は True、失敗した場合は False。
    """
    project_path = get_project_dir_path(project_dir_name)
    if not os.path.exists(project_path):
        print(f"削除対象のプロジェクトディレクトリが見つかりません: {project_path}")
        return False
    if project_dir_name == "default_project": # デフォルトプロジェクトは削除禁止
        print(f"デフォルトプロジェクト '{project_dir_name}' は削除できません。")
        return False

    try:
        shutil.rmtree(project_path)
        # print(f"プロジェクトディレクトリを削除しました: {project_path}")
        return True
    except Exception as e:
        print(f"プロジェクトディレクトリの削除に失敗しました ({project_path}): {e}")
        return False

def get_category_template(category_name: str, template_string: str) -> str:
    """
    与えられたテンプレート文字列から、指定されたカテゴリに一致するテンプレート内容を抽出します。

    カテゴリ名は `<カテゴリ名>テンプレート内容</カテゴリ名>` の形式で記述されていることを期待します。
    カテゴリ名の大文字・小文字は区別せず、前後の空白は無視して比較されます。

    一致するカテゴリが見つからない場合、またはカテゴリ名が空の場合は、
    どのカテゴリタグにも囲まれていない部分をデフォルトテンプレートとして返します。
    デフォルトテンプレートも見つからない場合は空文字列を返します。

    Args:
        category_name (str): 抽出したいカテゴリの名前。
        template_string (str): カテゴリ別テンプレートが記述された文字列。

    Returns:
        str: 抽出されたテンプレート内容。見つからなければデフォルトテンプレートまたは空文字列。
    """
    if not template_string:
        return ""

    normalized_category_name = category_name.strip().lower() if category_name else ""
    default_tag_names = ["default", "デフォルト"] # 検索するデフォルトタグ名（小文字）

    pattern = re.compile(r"<([^>]+)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
    
    specific_category_template = ""
    default_tagged_template = ""
    untagged_parts = []
    last_end = 0

    for match in pattern.finditer(template_string):
        tag_name_original = match.group(1)
        tag_name_normalized = tag_name_original.strip().lower()
        content = match.group(2).strip()
        
        untagged_parts.append(template_string[last_end:match.start()].strip())
        last_end = match.end()

        if normalized_category_name and tag_name_normalized == normalized_category_name:
            specific_category_template = content
            # 指定カテゴリが見つかったら即座に返す
            return specific_category_template 
        
        if not default_tagged_template: # まだデフォルトタグの内容が見つかっていなければ
            for dt_name in default_tag_names:
                if tag_name_normalized == dt_name:
                    default_tagged_template = content
                    break # 内側のループを抜ける

    untagged_parts.append(template_string[last_end:].strip())
    
    # 優先順位に基づいて返す値を決定
    if specific_category_template: # 通常ここには到達しないはず (上でreturnするため)
        return specific_category_template

    if default_tagged_template: # <default> タグの内容があればそれを返す
        return default_tagged_template
    
    # <default> タグがなければ、タグなし部分を結合して返す
    combined_untagged = "\n".join(part for part in untagged_parts if part).strip()
    if combined_untagged:
        return combined_untagged

    return "" # それでも何も見つからなければ空文字列


if __name__ == '__main__':
    """モジュールのテスト実行用コード。"""
    # print("--- Config Manager テスト ---")

    # 1. グローバル設定テスト
    # print("\n1. グローバル設定テスト:")
    global_cfg = load_global_config()
    # print(f"   読み込み時: {global_cfg}")
    original_active_project = global_cfg.get("active_project")
    global_cfg["active_project"] = "test_global_save_project"
    save_global_config(global_cfg)
    reloaded_global_cfg = load_global_config()
    # print(f"   保存・再読み込み後: {reloaded_global_cfg}")
    # テスト後は元に戻す (任意)
    if original_active_project:
        reloaded_global_cfg["active_project"] = original_active_project
        save_global_config(reloaded_global_cfg)

    # 2. プロジェクト設定テスト (新規作成と読み込み)
    # print("\n2. 新規プロジェクト設定テスト (project_alpha):")
    project_alpha_name = "project_alpha"
    # まずは存在しない状態でロード (デフォルトで作成されるはず)
    alpha_settings = load_project_settings(project_alpha_name)
    if alpha_settings:
        # print(f"   {project_alpha_name} (初回ロード/作成時): {alpha_settings}")
        # 内容を変更して保存
        alpha_settings["main_system_prompt"] = "Alphaプロジェクトのカスタムプロンプト。"
        alpha_settings["project_display_name"] = "アルファ計画"
        save_project_settings(project_alpha_name, alpha_settings)
        reloaded_alpha_settings = load_project_settings(project_alpha_name)
        # print(f"   {project_alpha_name} (変更保存・再読み込み後): {reloaded_alpha_settings}")
        if reloaded_alpha_settings and reloaded_alpha_settings["project_display_name"] == "アルファ計画":
            # print("   プロジェクト設定の保存・読み込みテスト成功。")
            pass
        else:
            # print("   プロジェクト設定の保存・読み込みテスト失敗。")
            pass
    else:
        # print(f"   {project_alpha_name} の設定の読み込み/作成に失敗しました。")
        pass

    # 3. 既存の 'default_project' のテスト (存在すれば読み込み、なければ作成)
    # print("\n3. 'default_project' 設定テスト:")
    default_proj_settings = load_project_settings("default_project")
    if default_proj_settings:
        # print(f"   default_project 設定: {default_proj_settings}")
        pass
    else:
        # print(f"   default_project の設定の読み込み/作成に失敗しました。")
        pass


    # 4. プロジェクト一覧テスト
    # print("\n4. プロジェクト一覧テスト:")
    all_projects = list_project_dir_names()
    # print(f"   検出されたプロジェクトディレクトリ: {all_projects}")
    if project_alpha_name in all_projects and "default_project" in all_projects:
        # print("   プロジェクト一覧の取得は期待通りです。")
        pass
    elif not all_projects:
        # print("   プロジェクトはまだ作成されていません。")
        pass
    else:
        # print(f"   プロジェクト一覧の取得結果が一部期待と異なります: {all_projects}")
        pass


    # 5. 存在しないプロジェクト設定ファイルの読み込みエラーテスト (ディレクトリはあるがファイルなし)
    # print("\n5. 破損/不正なプロジェクト設定ファイルテスト (project_beta):")
    project_beta_name = "project_beta"
    project_beta_dir = get_project_dir_path(project_beta_name)
    os.makedirs(project_beta_dir, exist_ok=True) # ディレクトリだけ作成
    project_beta_settings_file = get_project_settings_path(project_beta_name)
    # 不正なJSONファイルを作成
    with open(project_beta_settings_file, 'w', encoding='utf-8') as f:
        f.write("{ \"project_display_name\": \"Beta\", \"model\": ") # 途中で切れたJSON
    
    beta_settings_corrupted = load_project_settings(project_beta_name)
    if beta_settings_corrupted is None: # JSONDecodeError などで None が返ることを期待
        # print(f"   {project_beta_name} (不正なJSONファイル時): 読み込み失敗 (None) - 期待通り。")
        pass
    else:
        # print(f"   {project_beta_name} (不正なJSONファイル時): 読み込み結果 {beta_settings_corrupted} - 期待外れ。")
        pass
    # テスト用に作成したディレクトリとファイルを削除 (任意)
    if os.path.exists(project_beta_settings_file): os.remove(project_beta_settings_file)
    if os.path.exists(project_beta_dir) and not os.listdir(project_beta_dir): os.rmdir(project_beta_dir)


    # print("\n--- テスト完了 ---")
