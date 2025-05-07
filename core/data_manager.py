# core/data_manager.py

import json
import os
import uuid
import datetime

# --- 定数 ---
PROJECTS_BASE_DIR = "data"  # config_manager や subprompt_manager と同じ
GAMEDATA_SUBDIR_NAME = "gamedata" # プロジェクト内のゲームデータ用サブディレクトリ名

# --- ★★★ 変更: DATA_DIR を関数内で動的に取得するように変更 ★★★ ---
# DATA_DIR = os.path.join("data", "userdata") # 削除

def get_project_gamedata_path(project_dir_name):
    """指定されたプロジェクトのゲームデータディレクトリパスを返す"""
    return os.path.join(PROJECTS_BASE_DIR, project_dir_name, GAMEDATA_SUBDIR_NAME)

def get_category_filepath(project_dir_name, category_name):
    """指定されたプロジェクトとカテゴリ名に対するJSONファイルのフルパスを返す"""
    gamedata_dir = get_project_gamedata_path(project_dir_name)
    # カテゴリ名をファイル名として使用 (必要ならサニタイズ)
    # Windowsでは使えない文字などがあるため、より安全なファイル名生成方法も検討可
    filename = f"{category_name}.json"
    return os.path.join(gamedata_dir, filename)

# --- カテゴリ管理 ---
def list_categories(project_dir_name):
    """指定されたプロジェクトのgamedataディレクトリ内のカテゴリリスト（JSONファイル名から拡張子を除いたもの）を返す"""
    gamedata_dir = get_project_gamedata_path(project_dir_name)
    if not os.path.exists(gamedata_dir):
        return []
    try:
        categories = [
            os.path.splitext(f)[0]
            for f in os.listdir(gamedata_dir)
            if os.path.isfile(os.path.join(gamedata_dir, f)) and f.endswith(".json")
        ]
        return sorted(categories)
    except Exception as e:
        print(f"Error listing categories for project '{project_dir_name}': {e}")
        return []

def create_category(project_dir_name, category_name):
    """
    指定されたプロジェクトに新しいカテゴリ（空のJSONファイル）を作成する。
    gamedataディレクトリがなければ作成する。
    """
    if not category_name or not project_dir_name:
        print("Error: Project name and category name cannot be empty for creation.")
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
            print(f"Category '{category_name}' created successfully for project '{project_dir_name}' at {filepath}")
            return True
        else:
            print(f"Category '{category_name}' already exists for project '{project_dir_name}'.")
            return False # 既に存在する場合は False (作成はしていない)
    except Exception as e:
        print(f"Error creating category '{category_name}' for project '{project_dir_name}': {e}")
        return False

# --- データ読み込み/保存 (カテゴリ単位) ---
def load_data_category(project_dir_name, category_name):
    """指定されたプロジェクトとカテゴリのデータをファイルから読み込む"""
    filepath = get_category_filepath(project_dir_name, category_name)
    if not os.path.exists(filepath):
        # ファイルが存在しない場合、カテゴリ作成を試みる (空のデータで)
        print(f"Data file for category '{category_name}' in project '{project_dir_name}' not found. Attempting to create.")
        if create_category(project_dir_name, category_name):
            return {} # 新規作成成功時は空の辞書
        else:
            print(f"  Failed to create category '{category_name}', returning None.")
            return None # 作成失敗時は None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: JSON format is incorrect in file {filepath}. Returning empty data.")
        return {} # JSON形式エラー時は空のデータを返す (データ損失を防ぐため)
    except Exception as e:
        print(f"Error loading data for category '{category_name}' in project '{project_dir_name}': {e}")
        return None # その他のエラー

def save_data_category(project_dir_name, category_name, data):
    """指定されたプロジェクトとカテゴリのデータをファイルに保存する"""
    filepath = get_category_filepath(project_dir_name, category_name)
    gamedata_dir = os.path.dirname(filepath)
    try:
        os.makedirs(gamedata_dir, exist_ok=True) # 保存先のディレクトリがなければ作成
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Data for category '{category_name}' saved successfully for project '{project_dir_name}' at {filepath}")
        return True
    except Exception as e:
        print(f"Error saving data for category '{category_name}' in project '{project_dir_name}': {e}")
        return False

# --- アイテム操作 ---
def list_items(project_dir_name, category_name):
    """指定されたプロジェクトとカテゴリの全アイテムのリストを返す (idとnameを含む辞書のリスト)"""
    data = load_data_category(project_dir_name, category_name)
    if data is None: # load_data_category が None を返す場合 (読み込み/作成失敗)
        return []
    # 各アイテム辞書から 'id' と 'name' を抽出
    items_list = []
    for item_id, item_details in data.items():
        item_summary = {
            'id': item_details.get('id', item_id), # データ内にidがあればそれを優先
            'name': item_details.get('name', 'N/A')
        }
        items_list.append(item_summary)
    return sorted(items_list, key=lambda x: x.get('name', '')) # 名前でソート

def get_item(project_dir_name, category_name, item_id):
    """指定されたプロジェクト、カテゴリ、IDのアイテムデータを取得する"""
    data = load_data_category(project_dir_name, category_name)
    if data is None:
        return None
    return data.get(item_id)

def add_item(project_dir_name, category_name, item_data):
    """
    指定されたプロジェクトとカテゴリに新しいアイテムを追加する。
    item_data に 'name' は必須。'id' がなければ自動生成。
    成功すれば新しいアイテムのIDを、失敗すればNoneを返す。
    """
    if not project_dir_name or not category_name:
        print("Error: Project name and category name must be provided to add an item.")
        return None
    if not isinstance(item_data, dict) or 'name' not in item_data:
        print("Error: item_data must be a dictionary and contain a 'name'.")
        return None

    data = load_data_category(project_dir_name, category_name)
    if data is None: # カテゴリファイルの読み込み/作成に失敗した場合
        print(f"Failed to load or create category '{category_name}' for project '{project_dir_name}'. Cannot add item.")
        return None

    item_id = item_data.get('id')
    if not item_id:
        item_id = f"{category_name[:4].lower()}-{uuid.uuid4()}" # カテゴリ名の最初の数文字とUUID
    item_data['id'] = item_id
    item_data['category'] = category_name # カテゴリ情報をアイテムデータ内にも保持

    # 履歴やタグがなければ空リストで初期化 (任意)
    if 'history' not in item_data: item_data['history'] = []
    if 'tags' not in item_data: item_data['tags'] = []

    data[item_id] = item_data
    if save_data_category(project_dir_name, category_name, data):
        return item_id
    else:
        return None

def update_item(project_dir_name, category_name, item_id, update_data):
    """指定されたプロジェクト、カテゴリ、IDのアイテムデータを更新する"""
    data = load_data_category(project_dir_name, category_name)
    if data is None or item_id not in data:
        return False
    # update_data の内容で既存データを更新
    # data[item_id].update(update_data)
    # ★★★ 修正: update_data のキーのみを更新するのではなく、ネストされた構造も考慮して上書き
    for key, value in update_data.items():
        data[item_id][key] = value
    # IDやカテゴリが変更されないように保護 (任意)
    data[item_id]['id'] = item_id
    data[item_id]['category'] = category_name
    return save_data_category(project_dir_name, category_name, data)

def delete_item(project_dir_name, category_name, item_id):
    """指定されたプロジェクト、カテゴリ、IDのアイテムを削除する"""
    data = load_data_category(project_dir_name, category_name)
    if data is None or item_id not in data:
        return False
    del data[item_id]
    return save_data_category(project_dir_name, category_name, data)

# --- 履歴とタグのヘルパー関数 (変更なし、ただし project_dir_name と category_name を受け取る) ---
def add_history_entry(project_dir_name, category_name, item_id, entry_text):
    """アイテムに履歴エントリを追加する"""
    item = get_item(project_dir_name, category_name, item_id)
    if not item: return False
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = {"timestamp": timestamp, "entry": entry_text}
    if 'history' not in item or not isinstance(item['history'], list):
        item['history'] = []
    item['history'].append(new_entry)
    return update_item(project_dir_name, category_name, item_id, {"history": item['history']})

def update_tags(project_dir_name, category_name, item_id, tags_list):
    """アイテムのタグリストを更新する"""
    if not isinstance(tags_list, list): return False
    return update_item(project_dir_name, category_name, item_id, {"tags": tags_list})


if __name__ == '__main__':
    # --- テストコード ---
    test_project_dm = "dm_test_project" # データマネージャテスト用プロジェクト

    # 1. カテゴリ作成テスト
    print(f"\n--- カテゴリ作成テスト ({test_project_dm}) ---")
    cat_created1 = create_category(test_project_dm, "キャラクター")
    print(f"'キャラクター' 作成結果: {cat_created1}")
    cat_created2 = create_category(test_project_dm, "アイテム")
    print(f"'アイテム' 作成結果: {cat_created2}")
    cat_created_again = create_category(test_project_dm, "キャラクター") # 再度作成
    print(f"'キャラクター' 再作成結果 (Falseのはず): {cat_created_again}")


    # 2. カテゴリ一覧テスト
    print(f"\n--- カテゴリ一覧テスト ({test_project_dm}) ---")
    categories = list_categories(test_project_dm)
    print(f"現在のカテゴリ: {categories}")
    if "キャラクター" in categories and "アイテム" in categories:
        print("カテゴリ一覧取得成功。")

    # 3. アイテム追加テスト
    print(f"\n--- アイテム追加テスト ({test_project_dm}, キャラクター) ---")
    char1_id = add_item(test_project_dm, "キャラクター", {"name": "ユノ・アステル", "description": "親切なAIアシスタント"})
    print(f"追加されたキャラクター1のID: {char1_id}")
    char2_id = add_item(test_project_dm, "キャラクター", {"name": "マスター", "description": "TRPGツールの開発者"})
    print(f"追加されたキャラクター2のID: {char2_id}")

    item1_id = add_item(test_project_dm, "アイテム", {"name": "回復薬", "tags": ["消耗品", "回復"]})
    print(f"追加されたアイテム1のID: {item1_id}")

    # 4. アイテム一覧テスト
    print(f"\n--- アイテム一覧テスト ({test_project_dm}, キャラクター) ---")
    char_list = list_items(test_project_dm, "キャラクター")
    print(f"キャラクターリスト: {char_list}")
    if len(char_list) == 2: print("キャラクター一覧取得成功。")

    # 5. アイテム取得テスト
    print(f"\n--- アイテム取得テスト ({test_project_dm}) ---")
    if char1_id:
        retrieved_char1 = get_item(test_project_dm, "キャラクター", char1_id)
        print(f"取得したキャラクター1: {retrieved_char1}")
        if retrieved_char1 and retrieved_char1['name'] == "ユノ・アステル":
            print("キャラクター取得成功。")

    # 6. アイテム更新テスト
    print(f"\n--- アイテム更新テスト ({test_project_dm}) ---")
    if char1_id:
        update_success = update_item(test_project_dm, "キャラクター", char1_id, {"description": "非常に親切なAIアシスタント。開発を手伝う。"})
        print(f"キャラクター1更新結果: {update_success}")
        updated_char1 = get_item(test_project_dm, "キャラクター", char1_id)
        print(f"更新後のキャラクター1: {updated_char1}")
        if updated_char1 and "開発を手伝う" in updated_char1['description']:
            print("キャラクター更新成功。")

    # 7. 履歴追加テスト
    if char1_id:
        print(f"\n--- 履歴追加テスト ({test_project_dm}) ---")
        history_added = add_history_entry(test_project_dm, "キャラクター", char1_id, "プロジェクト機能の実装を支援した。")
        print(f"履歴追加結果: {history_added}")
        char_with_history = get_item(test_project_dm, "キャラクター", char1_id)
        print(f"履歴追加後のキャラ: {char_with_history.get('history')}")


    # 8. アイテム削除テスト
    print(f"\n--- アイテム削除テスト ({test_project_dm}) ---")
    if char2_id:
        delete_success = delete_item(test_project_dm, "キャラクター", char2_id)
        print(f"キャラクター2削除結果: {delete_success}")
        deleted_char2 = get_item(test_project_dm, "キャラクター", char2_id)
        print(f"削除後のキャラクター2取得試行: {deleted_char2}")
        if delete_success and deleted_char2 is None:
            print("キャラクター削除成功。")
        char_list_after_delete = list_items(test_project_dm, "キャラクター")
        print(f"削除後のキャラクターリスト: {char_list_after_delete}")

    # 9. 存在しないプロジェクトのテスト
    print(f"\n--- 存在しないプロジェクトのカテゴリ一覧テスト ---")
    non_existent_cats = list_categories("no_such_project_exists_here")
    print(f"存在しないプロジェクトのカテゴリ: {non_existent_cats}")
    if not non_existent_cats: print("期待通り空リスト。")

    print(f"\n--- 存在しないプロジェクトへのアイテム追加テスト ---")
    failed_add = add_item("no_such_project_exists_here", "ダミーカテゴリ", {"name": "ダミーアイテム"})
    print(f"存在しないプロジェクトへのアイテム追加結果 (Noneのはず): {failed_add}")


