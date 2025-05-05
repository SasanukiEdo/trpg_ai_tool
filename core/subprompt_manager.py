# core/subprompt_manager.py の内容

import json
import os
from PyQt5.QtWidgets import QMessageBox

# --- サブプロンプトファイルのパス ---
SUBPROMPTS_FILE = "data/subprompts_v2.json"

# --- デフォルトサブプロンプト ---
DEFAULT_SUBPROMPTS = {
    "一般": {
        "情景描写": {"content": "現在の場所、時間、天気、雰囲気などを詳細に描写してください。", "model": None, "api_key": None},
        "NPC会話": {"content": "プレイヤーが話しかけたNPCとして自然に応答してください。", "model": None, "api_key": None}
    },
    "戦闘": {
        "敵の行動宣言": {"content": "敵キャラクターの次の行動を宣言し、その理由や狙いを描写してください。", "model": None, "api_key": None},
        "ダメージ描写": {"content": "攻撃がヒットした場合のダメージ量と、その様子を具体的に描写してください。", "model": None, "api_key": None}
    }
}

# --- サブプロンプトの読み込み ---
def load_subprompts():
    if os.path.exists(SUBPROMPTS_FILE):
        try:
            with open(SUBPROMPTS_FILE, 'r', encoding='utf-8') as f:
                # TODO: 読み込んだデータ構造の検証を追加するとより堅牢になる
                return json.load(f)
        except Exception as e:
            print(f"サブプロンプトファイルの読み込みに失敗しました ({SUBPROMPTS_FILE}): {e}")
            # QMessageBox.critical(None, "サブプロンプト読込エラー", f"サブプロンプトファイル({SUBPROMPTS_FILE})の読み込みに失敗しました:\n{e}\nデフォルトデータを使用します。")
            return DEFAULT_SUBPROMPTS.copy()
    return DEFAULT_SUBPROMPTS.copy()

# --- サブプロンプトの保存 ---
def save_subprompts(subprompts_data):
    try:
        # data/ ディレクトリがない場合は作成する (オプション)
        data_dir = os.path.dirname(SUBPROMPTS_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

        with open(SUBPROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(subprompts_data, f, ensure_ascii=False, indent=4)
        print(f"サブプロンプトを {SUBPROMPTS_FILE} に保存しました。")
        return True
    except Exception as e:
        print(f"サブプロンプトファイルの保存に失敗しました ({SUBPROMPTS_FILE}): {e}")
        QMessageBox.warning(None, "保存エラー", f"サブプロンプトファイル({SUBPROMPTS_FILE})の保存に失敗しました:\n{e}")
        return False

# --- (オプション) サブプロンプト操作関数 ---
# 必要であれば、add, edit, delete のロジックもここに移動させることを検討
# def add_subprompt_data(subprompts, category, name, data): ...
# def edit_subprompt_data(subprompts, old_category, old_name, new_category, new_name, new_data): ...
# def delete_subprompt_data(subprompts, category, names_to_delete): ...
# これらの関数を MainWindow から呼び出す形にする

