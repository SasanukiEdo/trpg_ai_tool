# core/config_manager.py

import json
import os
# QMessageBox を critical でも使うのでインポートを確認
from PyQt5.QtWidgets import QMessageBox

# --- メインプロンプトファイルのパス ---
CONFIG_FILE = "data/config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "gemini-1.5-pro-latest",
    "main_system_prompt": "あなたは経験豊富なテーブルトークRPGのゲームマスターです。プレイヤーの発言や行動に対して、状況を描写し、ゲームを進行させてください。"
}
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key, value in DEFAULT_CONFIG.items():
                    config.setdefault(key, value)
                return config
        except Exception as e:
            print(f"設定ファイルの読み込みに失敗しました ({CONFIG_FILE}): {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

# --- 設定の保存関数を修正 ---
def save_config(config_data):
    """設定データをJSONファイルに保存する。デバッグとエラーハンドリング強化版。"""
    
    try:
        # --- デバッグ用: 保存するデータの内容と型をコンソールに出力 ---
        print("--- Attempting to save config data ---")
        problematic_keys = []
        for key, value in config_data.items():
            print(f"Key: '{key}', Type: {type(value)}, Value: {repr(value)}")
            # JSONで保存できない可能性のある型をチェック (より厳密なチェックも可能)
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                 problematic_keys.append(key)
        print("------------------------------------")

        if problematic_keys:
             print(f"警告: 以下のキーの値はJSONで直接保存できない型かもしれません: {problematic_keys}")
             # ここでエラーにするか、警告に留めるか選択できる
             # raise TypeError(f"設定データにJSON非互換の型が含まれています: {problematic_keys}")
        # --- ここまでデバッグ用 ---

        # data/ ディレクトリの作成処理 (オプション、必要ならコメント解除)
        data_dir = os.path.dirname(CONFIG_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            # ensure_ascii=False で日本語をそのまま保存
            # indent=4 で見やすく整形
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        print(f"設定を {CONFIG_FILE} に保存しました。")
        return True # 成功

    except TypeError as e: # JSONシリアライズエラーを捕捉
        print(f"設定ファイルの保存中にJSONシリアライズエラーが発生しました ({CONFIG_FILE}): {e}")
        # ユーザーに分かりやすいエラーメッセージを表示
        QMessageBox.critical(None, "保存エラー",
                           f"設定の保存中に内部エラーが発生しました。\n"
                           f"プログラムで扱えないデータ形式が含まれている可能性があります。\n"
                           f"(エラー詳細: {e})\n"
                           f"コンソール出力を確認してください。")
        return False # 失敗
    except Exception as e: # その他のファイル書き込みエラーなど
        print(f"設定ファイルの保存に失敗しました ({CONFIG_FILE}): {e}")
        QMessageBox.warning(None, "保存エラー", f"設定ファイル({CONFIG_FILE})の保存に失敗しました:\n{e}")
        return False # 失敗

