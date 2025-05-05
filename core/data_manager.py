# core/data_manager.py

import json
import os
import uuid # ユニークID生成用
from datetime import datetime # 履歴のタイムスタンプ用 (任意)

# --- データ保存ディレクトリ ---
# 'data/userdata' ディレクトリを想定
DATA_DIR = os.path.join("data", "userdata")

# --- ヘルパー関数: ファイルパス取得 ---
def _get_filepath(category):
    """カテゴリ名から対応するJSONファイルのパスを生成"""
    # カテゴリ名をファイル名として安全な形式にする処理が必要な場合もある
    # (例: スペースや特殊文字を置換するなど)
    # ここでは単純にカテゴリ名をファイル名とする
    filename = f"{category}.json"
    return os.path.join(DATA_DIR, filename)

# --- ヘルパー関数: データディレクトリ作成 ---
def ensure_data_dir():
    """データ保存用ディレクトリが存在しない場合に作成"""
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
            print(f"データディレクトリ '{DATA_DIR}' を作成しました。")
        except OSError as e:
            print(f"エラー: データディレクトリ '{DATA_DIR}' の作成に失敗しました: {e}")
            # ここで例外を再送出するかどうかは設計次第
            raise

# --- ヘルパー関数: ユニークID生成 ---
def generate_id(prefix="item"):
    """プレフィックス付きのユニークIDを生成"""
    return f"{prefix}-{uuid.uuid4()}"

# --- カテゴリデータの読み込み ---
def load_data_category(category):
    """
    指定されたカテゴリのデータをJSONファイルから読み込む。
    データはIDをキーとした辞書形式で保存されていることを想定。
    Returns:
        dict: {item_id: item_data, ...} 形式のデータ。ファイルがない/読めない場合は空辞書。
    """
    ensure_data_dir() # 念のためディレクトリ確認
    filepath = _get_filepath(category)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # データ形式が辞書であることを確認（任意だが推奨）
                if not isinstance(data, dict):
                     print(f"警告: カテゴリ '{category}' のデータ形式が辞書ではありません。空のデータとして扱います。")
                     return {}
                return data
        except json.JSONDecodeError as e:
            print(f"エラー: カテゴリ '{category}' のJSONデコードに失敗しました ({filepath}): {e}")
            return {} # エラー時は空辞書
        except Exception as e:
            print(f"エラー: カテゴリ '{category}' の読み込み中に予期せぬエラーが発生しました ({filepath}): {e}")
            return {} # エラー時は空辞書
    else:
        # print(f"カテゴリ '{category}' のファイル ({filepath}) は存在しません。") # ログ出力は任意
        return {} # ファイルが存在しない場合は空辞書

# --- カテゴリデータの保存 ---
def save_data_category(category, data):
    """
    指定されたカテゴリのデータ（IDをキーとした辞書）をJSONファイルに保存する。
    Args:
        category (str): カテゴリ名。
        data (dict): 保存するデータ ({item_id: item_data, ...})。
    Returns:
        bool: 保存に成功したかどうか。
    """
    ensure_data_dir() # ディレクトリ確認
    filepath = _get_filepath(category)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # print(f"カテゴリ '{category}' のデータを {filepath} に保存しました。") # ログは任意
        return True
    except Exception as e:
        print(f"エラー: カテゴリ '{category}' の保存中にエラーが発生しました ({filepath}): {e}")
        return False

# --- カテゴリ一覧の取得 ---
def list_categories():
    """
    データディレクトリ内のJSONファイル名からカテゴリのリストを取得する。
    Returns:
        list: カテゴリ名のリスト。
    """
    ensure_data_dir()
    categories = []
    try:
        for filename in os.listdir(DATA_DIR):
            if filename.lower().endswith('.json'):
                # 拡張子を除いた部分をカテゴリ名とする
                category_name = os.path.splitext(filename)[0]
                categories.append(category_name)
    except FileNotFoundError:
        print(f"データディレクトリ '{DATA_DIR}' が見つかりません。")
        return [] # ディレクトリがない場合は空
    except Exception as e:
        print(f"エラー: カテゴリ一覧の取得中にエラーが発生しました: {e}")
        return [] # その他のエラー
    return sorted(categories) # ソートして返す

# --- カテゴリ内のアイテム一覧取得 ---
def list_items(category):
    """
    指定されたカテゴリのデータから、アイテム名とIDのリストを取得する。
    Args:
        category (str): カテゴリ名。
    Returns:
        list: [{'id': str, 'name': str}, ...] 形式のリスト。
    """
    data = load_data_category(category)
    items = []
    for item_id, item_data in data.items():
        # 各アイテムデータに 'name' キーがあることを期待する
        item_name = item_data.get('name', f"名称未設定 ({item_id})") # nameがない場合のフォールバック
        items.append({'id': item_id, 'name': item_name})
    # 名前順でソートして返す
    return sorted(items, key=lambda x: x['name'])

# --- カテゴリの作成 ---
def create_category(category):
    """
    新しいカテゴリを作成する（空のJSONファイルを作成）。
    Args:
        category (str): 作成するカテゴリ名。
    Returns:
        bool: 作成に成功したかどうか。
    """
    ensure_data_dir()
    if not category or not isinstance(category, str):
        print("エラー: カテゴリ名が無効です。")
        return False
    # カテゴリ名がファイル名として安全かチェック・変換が必要な場合がある
    filepath = _get_filepath(category)
    if os.path.exists(filepath):
        print(f"情報: カテゴリ '{category}' は既に存在します。")
        return True # 既に存在する場合も成功とみなす
    try:
        # 空の辞書を書き込む
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        print(f"カテゴリ '{category}' を作成しました ({filepath})。")
        return True
    except Exception as e:
        print(f"エラー: カテゴリ '{category}' の作成に失敗しました: {e}")
        return False

# --- アイテム取得 ---
def get_item(category, item_id):
    """
    指定されたカテゴリとIDのアイテムデータを取得する。
    Args:
        category (str): カテゴリ名。
        item_id (str): アイテムID。
    Returns:
        dict or None: アイテムデータが見つかった場合はその辞書、見つからない場合はNone。
    """
    data = load_data_category(category)
    return data.get(item_id) # IDが存在すればデータを、しなければNoneを返す

# --- アイテム追加 ---
def add_item(category, item_data):
    """
    指定されたカテゴリに新しいアイテムを追加する。
    自動的にユニークIDが付与される。
    Args:
        category (str): カテゴリ名。
        item_data (dict): 追加するアイテムのデータ（'name' キー推奨）。
                          既存の 'id' キーは上書きされる。
                          'category' キーもここで設定される。
    Returns:
        str or None: 追加されたアイテムのID。失敗した場合はNone。
    """
    if not category or not isinstance(category, str):
        print("エラー: カテゴリ名が無効です。")
        return None
    if not isinstance(item_data, dict):
        print("エラー: アイテムデータが辞書形式ではありません。")
        return None

    data = load_data_category(category)

    # 新しいIDを生成
    new_id = generate_id(prefix=category[:4]) # カテゴリ名の先頭4文字をプレフィックスに

    # item_data をコピーしてIDとカテゴリを設定
    new_item = item_data.copy()
    new_item['id'] = new_id
    new_item['category'] = category # カテゴリ情報もデータ内に保持

    # 履歴リストやタグリストがなければ初期化する (任意)
    new_item.setdefault('history', [])
    new_item.setdefault('tags', [])
    # status などの構造化データも必要なら初期化
    new_item.setdefault('status', {})
    new_item.setdefault('description', "") # description も初期化
    new_item.setdefault('image_path', None) # image_path も初期化

    data[new_id] = new_item

    if save_data_category(category, data):
        print(f"アイテム '{new_item.get('name', 'N/A')}' (ID: {new_id}) をカテゴリ '{category}' に追加しました。")
        return new_id
    else:
        print(f"エラー: アイテムの追加に失敗しました（保存エラー）。")
        return None

# --- アイテム更新 ---
def update_item(category, item_id, updated_data):
    """
    指定されたカテゴリとIDのアイテムデータを更新する。
    Args:
        category (str): カテゴリ名。
        item_id (str): 更新するアイテムのID。
        updated_data (dict): 更新するキーと値を含む辞書。
                               'id' や 'category' の変更は想定しない。
    Returns:
        bool: 更新に成功したかどうか。
    """
    if not isinstance(updated_data, dict):
        print("エラー: 更新データが辞書形式ではありません。")
        return False

    data = load_data_category(category)

    if item_id not in data:
        print(f"エラー: 更新対象のアイテム (ID: {item_id}) がカテゴリ '{category}' に見つかりません。")
        return False

    # 元のデータを取得し、更新データで上書き (IDとカテゴリは保護)
    original_item = data[item_id]
    update_payload = updated_data.copy()
    update_payload.pop('id', None) # id が含まれていても無視
    update_payload.pop('category', None) # category が含まれていても無視

    original_item.update(update_payload) # updateメソッドで辞書をマージ

    data[item_id] = original_item # 更新したデータを再度セット

    if save_data_category(category, data):
        print(f"アイテム (ID: {item_id}) をカテゴリ '{category}' で更新しました。")
        return True
    else:
        print(f"エラー: アイテムの更新に失敗しました（保存エラー）。")
        return False

# --- アイテム削除 ---
def delete_item(category, item_id):
    """
    指定されたカテゴリとIDのアイテムデータを削除する。
    Args:
        category (str): カテゴリ名。
        item_id (str): 削除するアイテムのID。
    Returns:
        bool: 削除に成功したかどうか。
    """
    data = load_data_category(category)

    if item_id not in data:
        print(f"情報: 削除対象のアイテム (ID: {item_id}) はカテゴリ '{category}' に存在しません。")
        return True # 存在しない場合も（削除された状態なので）成功とみなす

    del data[item_id] # 辞書から削除

    if save_data_category(category, data):
        print(f"アイテム (ID: {item_id}) をカテゴリ '{category}' から削除しました。")
        return True
    else:
        print(f"エラー: アイテムの削除に失敗しました（保存エラー）。")
        return False

# --- 履歴追加のヘルパー関数 (例) ---
def add_history_entry(category, item_id, entry_text):
    """指定アイテムの履歴に新しいエントリを追加する"""
    item = get_item(category, item_id)
    if not item:
        return False
    
    # history がリストでなければ初期化
    if not isinstance(item.get('history'), list):
        item['history'] = []
        
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # 現在時刻
    item['history'].append({
        "timestamp": timestamp,
        "entry": entry_text
    })
    
    # 更新データとして history のみを渡す
    return update_item(category, item_id, {'history': item['history']})

# --- タグ更新のヘルパー関数 (例) ---
def update_tags(category, item_id, tags_list):
     """指定アイテムのタグリストを更新する"""
     if not isinstance(tags_list, list):
          print("エラー: タグはリスト形式で指定してください。")
          return False
     # 更新データとして tags のみを渡す
     return update_item(category, item_id, {'tags': tags_list})

# --- デバッグ用 ---
if __name__ == '__main__':
    # このファイル単体で実行したときのテストコード
    print("Data Manager - 単体テスト")
    ensure_data_dir()

    # カテゴリ作成
    create_category("キャラクター")
    create_category("アイテム")

    # カテゴリ一覧
    print("カテゴリ:", list_categories())

    # アイテム追加
    char_id1 = add_item("キャラクター", {"name": "アルド", "description": "勇敢な戦士", "status": {"HP": 30, "maxHP": 30}})
    char_id2 = add_item("キャラクター", {"name": "リナ", "description": "好奇心旺盛な魔法使い", "status": {"MP": 40, "maxMP": 40}})
    item_id1 = add_item("アイテム", {"name": "回復薬", "description": "HPを少し回復する"})

    # アイテム一覧
    print("キャラクター一覧:", list_items("キャラクター"))
    print("アイテム一覧:", list_items("アイテム"))

    # アイテム取得
    print("アルドの情報:", get_item("キャラクター", char_id1))

    # アイテム更新
    update_item("キャラクター", char_id1, {"description": "勇敢な戦士。レベル5になった。", "status": {"HP": 35, "maxHP": 35}})
    print("アルドの情報(更新後):", get_item("キャラクター", char_id1))

    # 履歴追加
    add_history_entry("キャラクター", char_id1, "ゴブリンキングを倒した！")
    add_history_entry("キャラクター", char_id1, "新しい剣を手に入れた。")
    print("アルドの情報(履歴追加後):", get_item("キャラクター", char_id1))

    # タグ更新
    update_tags("キャラクター", char_id1, ["主人公", "戦士", "レベル5"])
    print("アルドの情報(タグ更新後):", get_item("キャラクター", char_id1))

    # アイテム削除
    # delete_item("アイテム", item_id1)
    # print("アイテム一覧(削除後):", list_items("アイテム"))

    # 存在しないカテゴリ
    print("存在しないカテゴリのアイテム:", list_items("武器"))

