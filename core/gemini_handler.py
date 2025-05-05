# core/gemini_handler.py

import google.generativeai as genai
from google.api_core import exceptions # エラーハンドリング用

# APIクライアント設定を保持する変数（モジュールレベル）
# 本来はクラスで状態を持つ方が良いが、シンプルにするため一旦モジュール変数で管理
_is_configured = False
_configured_api_key = None

def configure_gemini_api(api_key):
    """Gemini APIクライアントを設定する"""
    global _is_configured, _configured_api_key
    if not api_key:
        print("Gemini Handler: APIキーが空です。設定されていません。")
        _is_configured = False
        _configured_api_key = None
        return False, "APIキーが空です。"

    # 同じキーで既に設定済みなら再設定しない（効率化）
    if _is_configured and _configured_api_key == api_key:
         print("Gemini Handler: 同じAPIキーで既に設定済みです。")
         return True, "設定済み"

    try:
        genai.configure(api_key=api_key)
        _is_configured = True
        _configured_api_key = api_key
        print("Gemini Handler: APIクライアントを設定しました。")
        return True, "設定成功"
    except Exception as e:
        print(f"Gemini Handler: APIクライアントの設定に失敗しました: {e}")
        _is_configured = False
        _configured_api_key = None
        # エラーの種類によってメッセージを変えることも可能
        return False, f"APIクライアント設定失敗: {e}"

def is_configured():
    """APIクライアントが設定済みか確認する"""
    return _is_configured

def generate_response(model_name, prompt_text):
    """指定されたモデルを使用してプロンプトに対する応答を生成する"""
    if not _is_configured:
        # raise Exception("Gemini APIが設定されていません。configure_gemini_apiを呼び出してください。")
        print("Gemini Handler Error: APIが設定されていません。")
        # エラーを示す値を返すか、例外を送出するかは設計次第
        return None, "API未設定" # 応答テキストとエラーメッセージを返す例

    if not model_name:
         print("Gemini Handler Error: モデル名が指定されていません。")
         return None, "モデル名未指定"

    try:
        print(f"Gemini Handler: モデル '{model_name}' を使用してリクエスト送信...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt_text)
        print("Gemini Handler: 応答を受信しました。")
        return response.text, None # 応答テキストとエラーなしを示すNoneを返す

    except exceptions.NotFound as e:
         print(f"Gemini Handler API Error (NotFound): {e}")
         return None, f"モデル '{model_name}' が見つからないか、サポートされていません。({e})"
    except exceptions.PermissionDenied as e:
        print(f"Gemini Handler API Error (PermissionDenied): {e}")
        return None, f"APIキーが無効か、権限がありません。({e})"
    except exceptions.ResourceExhausted as e:
         print(f"Gemini Handler API Error (ResourceExhausted): {e}")
         return None, f"APIの利用制限（クォータ）に達しました。({e})"
    except Exception as e:
        # その他の予期せぬエラー
        print(f"Gemini Handler API Error (Unknown): {e}")
        return None, f"予期せぬAPIエラーが発生しました: {e}"

# 必要であれば、モデルリスト取得などの関数もここに追加できる
# def list_available_models(): ...
