# core/data_manager.py

"""プロジェクトごとのゲームデータ（カテゴリ別アイテム）の管理モジュール。

プロジェクトディレクトリ内の 'gamedata' サブディレクトリに、カテゴリごとに
JSONファイルとしてアイテムデータを保存・管理します。
各アイテムは一意のIDを持ち、名前、説明、履歴、タグなどの属性を持つことができます。

主な機能:
    - カテゴリの作成・一覧取得
    - カテゴリ内アイテムのCRUD操作 (作成, 読み取り, 更新, 削除)
    - アイテムの履歴追加、タグ更新
"""

import json
import os
import uuid
import datetime

# --- 定数 ---
PROJECTS_BASE_DIR = "data"
"""str: 全てのプロジェクトディレクトリが格納されるベースディレクトリのパス。"""

GAMEDATA_SUBDIR_NAME = "gamedata"
"""str: 各プロジェクトディレクトリ内で、実際のゲームデータファイル (カテゴリ別JSON)
が格納されるサブディレクトリの名前。
"""

# --- パス取得ヘルパー関数 ---

def get_project_gamedata_path(project_dir_name: str) -> str:
    """指定されたプロジェクトのゲームデータディレクトリ (gamedata/) のフルパスを返します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。

    Returns:
        str: プロジェクトのgamedataディレクトリのフルパス。
    """
    if not project_dir_name:
        # 実運用上、UI側から空のプロジェクト名が渡されることは想定しにくいが、念のためログ出力
        print(f"Warning: project_dir_name is empty in get_project_gamedata_path. Path will be relative to '{PROJECTS_BASE_DIR}'.")
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name, GAMEDATA_SUBDIR_NAME)

def get_category_filepath(project_dir_name: str, category_name: str) -> str:
    """指定されたプロジェクトとカテゴリ名に対応するJSONファイルのフルパスを返します。

    カテゴリ名はそのままファイル名（拡張子 .json を付加）として使用されます。
    ファイル名として不適切な文字が含まれている場合の処理は呼び出し元や
    カテゴリ作成時のバリデーションに依存します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 対象カテゴリの名前。

    Returns:
        str: カテゴリデータJSONファイルのフルパス。
    """
    if not category_name:
        # カテゴリ名が空の場合の扱い。基本的にはUI側で空のカテゴリ名は許可しない想定。
        print(f"Warning: category_name is empty in get_category_filepath for project '{project_dir_name}'.")
    gamedata_dir = get_project_gamedata_path(project_dir_name)
    filename = f"{category_name}.json"
    return os.path.join(gamedata_dir, filename)

# プロジェクト画像ディレクトリ関連ヘルパー
IMAGES_SUBDIR_NAME = "images"
"""str: 各プロジェクトディレクトリ内で、画像ファイルが格納されるサブディレクトリの名前。"""

def get_project_images_path(project_dir_name: str) -> str:
    """指定されたプロジェクトの画像保存用サブディレクトリ (images/) のフルパスを返します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。

    Returns:
        str: プロジェクトの images ディレクトリのフルパス。
    """
    if not project_dir_name:
        print("Warning: project_dir_name is empty in get_project_images_path.")
    # get_project_dir_path は config_manager にあるので、直接 PROJECTS_BASE_DIR を使うか、
    # data_manager 内でプロジェクトルートパスを組み立てる
    # ここでは PROJECTS_BASE_DIR を使う想定 (data_manager.py の先頭で定義されている想定)
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name, IMAGES_SUBDIR_NAME)

def ensure_project_images_dir_exists(project_dir_name: str) -> str | None:
    """指定されたプロジェクトの画像保存用サブディレクトリが存在することを確認し、なければ作成します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。

    Returns:
        str | None: 画像保存用ディレクトリのフルパス。作成に失敗した場合は None。
    """
    images_dir_path = get_project_images_path(project_dir_name)
    try:
        if not os.path.exists(images_dir_path):
            os.makedirs(images_dir_path, exist_ok=True)
            print(f"Created images directory for project '{project_dir_name}': {images_dir_path}")
        return images_dir_path
    except Exception as e:
        print(f"Error ensuring/creating images directory for project '{project_dir_name}': {e}")
        return None


# --- カテゴリ管理 ---

def list_categories(project_dir_name: str) -> list[str]:
    """指定されたプロジェクトのgamedataディレクトリ内のカテゴリリストを返します。

    カテゴリは、gamedataディレクトリ内の拡張子が '.json' であるファイル名から
    拡張子を除いたものとして認識されます。リストはソートされて返されます。

    Args:
        project_dir_name (str): カテゴリリストを取得するプロジェクトのディレクトリ名。

    Returns:
        list[str]: カテゴリ名のソート済みリスト。
                   gamedataディレクトリが存在しない場合は空リスト。
    """
    if not project_dir_name:
        print("Error: Project directory name is required to list categories.")
        return []
    gamedata_dir = get_project_gamedata_path(project_dir_name)
    if not os.path.exists(gamedata_dir):
        # print(f"Info: Gamedata directory not found for project '{project_dir_name}', returning empty category list.")
        return []
    try:
        categories = [
            os.path.splitext(f)[0]
            for f in os.listdir(gamedata_dir)
            if os.path.isfile(os.path.join(gamedata_dir, f)) and f.endswith(".json")
        ]
        # print(f"Found categories in '{gamedata_dir}': {categories}")
        return sorted(categories)
    except Exception as e:
        print(f"Error listing categories for project '{project_dir_name}' in '{gamedata_dir}': {e}")
        return []

def create_category(project_dir_name: str, category_name: str) -> bool:
    """指定されたプロジェクトに新しいカテゴリ（空のJSONファイル）を作成します。

    対応するgamedataディレクトリが存在しない場合は、それも合わせて作成します。
    カテゴリ名が空の場合や、既に同名のカテゴリが存在する場合は作成に失敗します。

    Args:
        project_dir_name (str): カテゴリを作成するプロジェクトのディレクトリ名。
        category_name (str): 新しく作成するカテゴリの名前。

    Returns:
        bool: カテゴリ作成が成功した場合は True、失敗した場合は False。
    """
    if not project_dir_name or not category_name:
        print("Error: Project name and category name cannot be empty for category creation.")
        return False

    filepath = get_category_filepath(project_dir_name, category_name)
    gamedata_dir = os.path.dirname(filepath)

    try:
        if not os.path.exists(gamedata_dir):
            os.makedirs(gamedata_dir, exist_ok=True)
            print(f"Created gamedata directory for project '{project_dir_name}': {gamedata_dir}")

        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({}, f) # 空のJSONオブジェクトで初期化
            print(f"Category '{category_name}' created for project '{project_dir_name}' at {filepath}")
            return True
        else:
            print(f"Info: Category '{category_name}' already exists for project '{project_dir_name}'. No action taken.")
            return False # 既に存在する場合は False (エラーではないが、新規作成はしていない)
    except Exception as e:
        print(f"Error creating category '{category_name}' for project '{project_dir_name}': {e}")
        return False

# --- データ読み込み/保存 (カテゴリ単位) ---

def load_data_category(project_dir_name: str, category_name: str) -> dict | None:
    """指定されたプロジェクトとカテゴリの全アイテムデータをファイルから読み込みます。

    ファイルが存在しない場合は、カテゴリ作成を試み（空のデータで初期化）、
    成功すれば空の辞書を返します。
    JSONの形式が不正な場合は空の辞書を返し、その他の読み込みエラーの場合はNoneを返します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 読み込むデータのカテゴリ名。

    Returns:
        dict | None: 読み込まれたアイテムデータの辞書。
                     キーはアイテムID、値はアイテム詳細の辞書。
                     ファイルが存在せず新規作成成功時やJSON不正時は空の辞書。
                     その他のエラー時は None。
    """
    if not project_dir_name or not category_name:
        print("Error: Project name and category name are required to load category data.")
        return None
    filepath = get_category_filepath(project_dir_name, category_name)

    if not os.path.exists(filepath):
        print(f"Data file for category '{category_name}' in project '{project_dir_name}' not found. Attempting to create.")
        if create_category(project_dir_name, category_name): # 空のカテゴリファイル作成
            return {} # 新規作成成功時は空の辞書
        else:
            print(f"  Failed to create category file for '{category_name}', returning None.")
            return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict): # ルートが辞書でない場合は不正な形式とみなす
            print(f"Warning: Data in '{filepath}' is not a valid dictionary. Returning empty data.")
            return {}
        # print(f"Data loaded for category '{category_name}', project '{project_dir_name}'.")
        return data
    except json.JSONDecodeError:
        print(f"Error: JSON format is incorrect in file {filepath}. Returning empty data to prevent data loss on save.")
        return {} # データ損失を防ぐため、空のデータを返す (次回保存時に上書きされる可能性)
    except Exception as e:
        print(f"Error loading data for category '{category_name}' in project '{project_dir_name}': {e}")
        return None

def save_data_category(project_dir_name: str, category_name: str, data: dict) -> bool:
    """指定されたプロジェクトとカテゴリの全アイテムデータをファイルに保存します。

    保存先のgamedataディレクトリが存在しない場合は作成します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 保存するデータのカテゴリ名。
        data (dict): 保存するアイテムデータの辞書。
                     キーはアイテムID、値はアイテム詳細の辞書。

    Returns:
        bool: 保存が成功した場合は True、失敗した場合は False。
    """
    if not project_dir_name or not category_name:
        print("Error: Project name and category name are required to save category data.")
        return False
    if not isinstance(data, dict):
        print("Error: Data to be saved must be a dictionary.")
        return False

    filepath = get_category_filepath(project_dir_name, category_name)
    gamedata_dir = os.path.dirname(filepath)
    try:
        os.makedirs(gamedata_dir, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        # print(f"Data for category '{category_name}' saved to '{filepath}' in project '{project_dir_name}'.")
        return True
    except Exception as e:
        print(f"Error saving data for category '{category_name}' in project '{project_dir_name}': {e}")
        return False

# --- アイテム操作 ---

def list_items(project_dir_name: str, category_name: str) -> list[dict]:
    """指定されたプロジェクトとカテゴリの全アイテムの要約リストを返します。

    各アイテムはIDと名前を含む辞書として表現されます。リストは名前でソートされます。
    カテゴリデータの読み込みに失敗した場合は空リストを返します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): アイテムリストを取得するカテゴリ名。

    Returns:
        list[dict]: アイテムの要約情報 (id, name) の辞書のリスト。
    """
    data = load_data_category(project_dir_name, category_name)
    if data is None: # 読み込み失敗（またはカテゴリが存在しない）
        return []

    items_list = []
    for item_id_key, item_details in data.items():
        if not isinstance(item_details, dict): # 不正なアイテムデータはスキップ
            print(f"Warning: Invalid item data format for ID '{item_id_key}' in category '{category_name}', project '{project_dir_name}'. Skipping.")
            continue
        item_summary = {
            'id': item_details.get('id', item_id_key), # データ内のidフィールドを優先、なければキーを使用
            'name': item_details.get('name', '名前なし') # nameがない場合はフォールバック
        }
        items_list.append(item_summary)
    return sorted(items_list, key=lambda x: x.get('name', ''))

def get_item(project_dir_name: str, category_name: str, item_id: str) -> dict | None:
    """指定されたプロジェクト、カテゴリ、IDのアイテム詳細データを取得します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 対象アイテムのカテゴリ名。
        item_id (str): 取得するアイテムのID。

    Returns:
        dict | None: アイテムの詳細データの辞書。アイテムが存在しない場合や
                     カテゴリデータの読み込みに失敗した場合は None。
    """
    data = load_data_category(project_dir_name, category_name)
    if data is None:
        return None
    return data.get(item_id) # 指定IDのアイテムを返す (なければNone)

def add_item(project_dir_name: str, category_name: str, item_data: dict) -> str | None:
    """指定されたプロジェクトとカテゴリに新しいアイテムを追加します。

    item_data に 'name' は必須です。'id' が item_data に含まれていなければ自動生成されます。
    成功した場合は新しいアイテムのIDを、失敗した場合はNoneを返します。
    カテゴリデータの読み込み/作成に失敗した場合もNoneを返します。

    Args:
        project_dir_name (str): アイテムを追加するプロジェクトのディレクトリ名。
        category_name (str): アイテムを追加するカテゴリ名。
        item_data (dict): 追加するアイテムのデータ。少なくとも 'name' キーが必要。

    Returns:
        str | None: 正常に追加された場合は新しいアイテムのID。失敗した場合はNone。
    """
    if not project_dir_name or not category_name:
        print("Error: Project name and category name must be provided to add an item.")
        return None
    if not isinstance(item_data, dict) or 'name' not in item_data:
        print("Error: item_data must be a dictionary and contain a 'name' key.")
        return None

    data = load_data_category(project_dir_name, category_name)
    if data is None: # カテゴリファイルの読み込み/作成に失敗
        print(f"Failed to load or create data for category '{category_name}', project '{project_dir_name}'. Cannot add item.")
        return None

    item_id = item_data.get('id')
    if not item_id: # IDが提供されていなければ生成
        # カテゴリ名の最初の3-4文字 (英数字のみ) + UUID短縮形など、より分かりやすいID生成も検討可
        prefix = "".join(filter(str.isalnum, category_name))[:4].lower()
        if not prefix: prefix = "item"
        item_id = f"{prefix}-{uuid.uuid4()}"
    item_data['id'] = item_id # 生成または提供されたIDをデータに確実にセット
    item_data['category'] = category_name # カテゴリ情報もアイテムデータ内に保持

    # 必須ではないが、よく使われるフィールドを初期化 (任意)
    if 'description' not in item_data: item_data['description'] = ""
    if 'history' not in item_data: item_data['history'] = []
    if 'tags' not in item_data: item_data['tags'] = []
    if 'image_path' not in item_data: item_data['image_path'] = None

    data[item_id] = item_data # 新しいアイテムをカテゴリデータに追加
    if save_data_category(project_dir_name, category_name, data):
        print(f"Item '{item_data.get('name')}' (ID: {item_id}) added to category '{category_name}', project '{project_dir_name}'.")
        return item_id
    else:
        print(f"Failed to save data after attempting to add item '{item_data.get('name')}' to category '{category_name}'.")
        return None

def update_item(project_dir_name: str, category_name: str, item_id: str, update_data: dict) -> bool:
    """指定されたプロジェクト、カテゴリ、IDのアイテムデータを更新します。

    `update_data` に含まれるキーと値で、既存のアイテムデータを上書きします。
    アイテムIDとカテゴリ名は変更されません。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 対象アイテムのカテゴリ名。
        item_id (str): 更新するアイテムのID。
        update_data (dict): 更新するデータを含む辞書。
                           この辞書のキーと値が既存アイテムの対応するキーを上書きします。

    Returns:
        bool: 更新と保存が成功した場合は True、失敗した場合は False。
    """
    if not project_dir_name or not category_name or not item_id:
        print("Error: Project name, category name, and item ID are required for update.")
        return False

    data = load_data_category(project_dir_name, category_name)
    if data is None or item_id not in data:
        print(f"Error: Item with ID '{item_id}' not found in category '{category_name}', project '{project_dir_name}', or category data load failed.")
        return False

    # update_data の内容で既存データを更新
    # data[item_id].update(update_data) # これは浅いコピーなのでネスト辞書に注意
    for key, value in update_data.items():
        if key not in ['id', 'category']: # idとcategoryは上書きさせない
            data[item_id][key] = value
        elif key == 'id' and value != item_id:
            print(f"Warning: Attempt to change item ID from '{item_id}' to '{value}' was ignored.")
        elif key == 'category' and value != category_name:
            print(f"Warning: Attempt to change item category from '{category_name}' to '{value}' was ignored.")

    # 念のため、IDとカテゴリが変更されていないことを保証
    data[item_id]['id'] = item_id
    data[item_id]['category'] = category_name

    if save_data_category(project_dir_name, category_name, data):
        print(f"Item '{data[item_id].get('name', item_id)}' updated in category '{category_name}', project '{project_dir_name}'.")
        return True
    else:
        print(f"Failed to save data after updating item '{data[item_id].get('name', item_id)}'.")
        return False

def delete_item(project_dir_name: str, category_name: str, item_id: str) -> bool:
    """指定されたプロジェクト、カテゴリ、IDのアイテムを削除します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 対象アイテムのカテゴリ名。
        item_id (str): 削除するアイテムのID。

    Returns:
        bool: 削除と保存が成功した場合は True、失敗した場合は False。
    """
    if not project_dir_name or not category_name or not item_id:
        print("Error: Project name, category name, and item ID are required for deletion.")
        return False

    data = load_data_category(project_dir_name, category_name)
    if data is None or item_id not in data:
        print(f"Error: Item with ID '{item_id}' not found in category '{category_name}', project '{project_dir_name}', for deletion or category data load failed.")
        return False # アイテムが存在しないか、カテゴリデータ読み込み失敗

    item_name_for_log = data[item_id].get('name', item_id) # ログ用の名前取得
    del data[item_id] # アイテムを辞書から削除

    if save_data_category(project_dir_name, category_name, data):
        print(f"Item '{item_name_for_log}' (ID: {item_id}) deleted from category '{category_name}', project '{project_dir_name}'.")
        return True
    else:
        # 削除自体は成功したが保存に失敗した場合、データはメモリ上では削除されている
        print(f"Failed to save data after deleting item '{item_name_for_log}'. Data integrity might be compromised.")
        return False

# --- 履歴とタグのヘルパー関数 ---

def add_history_entry(project_dir_name: str, category_name: str, item_id: str, entry_text: str) -> bool:
    """指定されたアイテムに新しい履歴エントリ（IDとタイムスタンプ付き）を追加します。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 対象アイテムのカテゴリ名。
        item_id (str): 履歴を追加するアイテムのID。
        entry_text (str): 追加する履歴の内容。

    Returns:
        bool: 履歴の追加と保存が成功した場合は True、失敗した場合は False。
    """
    item = get_item(project_dir_name, category_name, item_id)
    if not item:
        print(f"Cannot add history: Item ID '{item_id}' not found in category '{category_name}', project '{project_dir_name}'.")
        return False
    if not isinstance(entry_text, str):
        print("Error: History entry text must be a string.")
        return False

    history_id = str(uuid.uuid4()) # 各履歴エントリに一意のIDを付与
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = {"id": history_id, "timestamp": timestamp, "entry": entry_text.strip()} # strip()で前後の空白除去

    if 'history' not in item or not isinstance(item['history'], list):
        item['history'] = [] # 履歴フィールドがなければリストで初期化
    item['history'].append(new_entry)

    # アイテム全体を更新する形で履歴を保存
    # update_item は item_data の 'history' フィールド全体を上書きする
    return update_item(project_dir_name, category_name, item_id, {"history": item['history']})

def update_tags(project_dir_name: str, category_name: str, item_id: str, tags_list: list[str]) -> bool:
    """指定されたアイテムのタグリストを新しいリストで上書きします。

    Args:
        project_dir_name (str): 対象プロジェクトのディレクトリ名。
        category_name (str): 対象アイテムのカテゴリ名。
        item_id (str): タグを更新するアイテムのID。
        tags_list (list[str]): 新しいタグのリスト（文字列のリスト）。

    Returns:
        bool: タグの更新と保存が成功した場合は True、失敗した場合は False。
    """
    if not isinstance(tags_list, list) or not all(isinstance(tag, str) for tag in tags_list):
        print("Error: tags_list must be a list of strings.")
        return False
    # アイテムの存在確認は update_item 内で行われる
    return update_item(project_dir_name, category_name, item_id, {"tags": tags_list})


if __name__ == '__main__':
    """モジュールの基本的な動作をテストするためのコード。"""
    print("--- Data Manager テスト ---")
    test_project = "data_manager_test_suite" # テスト専用のプロジェクト名

    # --- セットアップ: テスト用プロジェクトディレクトリをクリーンにする ---
    # (注意: この部分は実際のプロジェクトデータを誤って削除しないよう注意)
    import shutil
    test_project_path = get_project_gamedata_path(test_project)
    if os.path.exists(os.path.dirname(test_project_path)): # gamedata の親 (プロジェクトディレクトリ)
        print(f"クリーンアップ: 既存のテストプロジェクトディレクトリ '{os.path.dirname(test_project_path)}' を削除します。")
        shutil.rmtree(os.path.dirname(test_project_path), ignore_errors=True)
    # --------------------------------------------------------------------

    # 1. カテゴリ作成テスト
    print("\n1. カテゴリ作成テスト:")
    cat_chars = "キャラクター"
    cat_items = "アイテム"
    assert create_category(test_project, cat_chars) is True, "キャラクターカテゴリ作成失敗"
    assert create_category(test_project, cat_items) is True, "アイテムカテゴリ作成失敗"
    assert create_category(test_project, cat_chars) is False, "既存カテゴリの再作成がTrueを返した"
    print(f"  カテゴリ '{cat_chars}', '{cat_items}' 作成テスト完了。")

    # 2. カテゴリ一覧テスト
    print("\n2. カテゴリ一覧テスト:")
    categories = list_categories(test_project)
    print(f"  取得されたカテゴリ: {categories}")
    assert cat_chars in categories and cat_items in categories, "作成したカテゴリが一覧に含まれていない"
    assert len(categories) == 2, "カテゴリ数が期待と異なる"

    # 3. アイテム追加テスト
    print("\n3. アイテム追加テスト:")
    char1_data = {"name": "アリス", "description": "勇敢な冒険者"}
    char1_id = add_item(test_project, cat_chars, char1_data)
    assert char1_id is not None, f"アリス追加失敗: {char1_id}"
    print(f"  キャラクター 'アリス' (ID: {char1_id}) 追加成功。")

    item1_data = {"name": "ポーション", "tags": ["回復", "消耗品"]}
    item1_id = add_item(test_project, cat_items, item1_data)
    assert item1_id is not None, f"ポーション追加失敗: {item1_id}"
    print(f"  アイテム 'ポーション' (ID: {item1_id}) 追加成功。")

    # 4. アイテム取得テスト
    print("\n4. アイテム取得テスト:")
    retrieved_char1 = get_item(test_project, cat_chars, char1_id)
    assert retrieved_char1 is not None and retrieved_char1.get("name") == "アリス", "アリス取得失敗または内容不一致"
    print(f"  キャラクター 'アリス' 取得成功: {retrieved_char1.get('description')}")
    assert get_item(test_project, cat_chars, "存在しないID") is None, "存在しないIDの取得がNoneを返さなかった"

    # 5. アイテム一覧テスト
    print("\n5. アイテム一覧テスト:")
    char_list = list_items(test_project, cat_chars)
    assert len(char_list) == 1 and char_list[0]["name"] == "アリス", "キャラクター一覧取得失敗"
    print(f"  キャラクターリスト: {[item['name'] for item in char_list]}")

    # 6. アイテム更新テスト
    print("\n6. アイテム更新テスト:")
    update_desc_char1 = {"description": "熟練の冒険者、多くの謎を解き明かす。"}
    assert update_item(test_project, cat_chars, char1_id, update_desc_char1) is True, "アリス更新失敗"
    updated_char1 = get_item(test_project, cat_chars, char1_id)
    assert updated_char1.get("description") == update_desc_char1["description"], "アリスの説明が更新されていない"
    print(f"  キャラクター 'アリス' 更新後の説明: {updated_char1.get('description')}")

    # 7. 履歴追加テスト
    print("\n7. 履歴追加テスト:")
    history_entry1 = "ドラゴンの洞窟を発見した。"
    assert add_history_entry(test_project, cat_chars, char1_id, history_entry1) is True, "アリスへの履歴追加失敗"
    char1_with_history = get_item(test_project, cat_chars, char1_id)
    assert len(char1_with_history.get("history", [])) == 1, "履歴エントリ数が期待と異なる"
    assert char1_with_history["history"][0]["entry"] == history_entry1, "履歴内容が不一致"
    print(f"  アリスの履歴: {char1_with_history['history'][0]['entry']}")

    # 8. タグ更新テスト
    print("\n8. タグ更新テスト:")
    new_tags_item1 = ["回復", "貴重品"]
    assert update_tags(test_project, cat_items, item1_id, new_tags_item1) is True, "ポーションのタグ更新失敗"
    item1_with_new_tags = get_item(test_project, cat_items, item1_id)
    assert sorted(item1_with_new_tags.get("tags", [])) == sorted(new_tags_item1), "タグが更新されていないか内容不一致"
    print(f"  ポーションの更新後タグ: {item1_with_new_tags.get('tags')}")

    # 9. アイテム削除テスト
    print("\n9. アイテム削除テスト:")
    assert delete_item(test_project, cat_chars, char1_id) is True, "アリス削除失敗"
    assert get_item(test_project, cat_chars, char1_id) is None, "アリス削除後も取得できてしまう"
    print(f"  キャラクター 'アリス' 削除成功。")
    assert len(list_items(test_project, cat_chars)) == 0, "キャラクター削除後も一覧に残っている"

    # 10. 存在しないプロジェクトでの操作テスト
    print("\n10. 存在しないプロジェクトでの操作テスト:")
    non_existent_project = "project_that_does_not_exist_xyz"
    assert list_categories(non_existent_project) == [], "存在しないプロジェクトのカテゴリ一覧が空でない"
    assert create_category(non_existent_project, "ダミー") is True, "存在しないプロジェクトへのカテゴリ作成に失敗（作成されるはず）"
    print(f"  存在しないプロジェクト '{non_existent_project}' でのカテゴリ作成・一覧テスト完了。")
    # 作成されたディレクトリをクリーンアップ
    if os.path.exists(os.path.dirname(get_project_gamedata_path(non_existent_project))):
        shutil.rmtree(os.path.dirname(get_project_gamedata_path(non_existent_project)), ignore_errors=True)


    # --- 最終クリーンアップ ---
    if os.path.exists(os.path.dirname(test_project_path)):
        print(f"最終クリーンアップ: テストプロジェクトディレクトリ '{os.path.dirname(test_project_path)}' を削除します。")
        shutil.rmtree(os.path.dirname(test_project_path), ignore_errors=True)

    print("\n--- 全テスト完了 ---")
