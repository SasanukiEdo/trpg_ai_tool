# core/gemini_handler.py

import google.generativeai as genai
import os

# --- ★★★ モジュールレベルでAPIクライアントと設定済みフラグを保持 ★★★ ---
_API_KEY_CONFIGURED = None
_SAFETY_SETTINGS = [ # 安全性設定 (必要に応じて調整)
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
# --------------------------------------------------------------------

def configure_gemini_api(api_key):
    """
    指定されたAPIキーでGemini APIクライアントを設定する。
    成功した場合は (True, "成功メッセージ") を、失敗した場合は (False, "エラーメッセージ") を返す。
    """
    global _API_KEY_CONFIGURED
    if not api_key:
        _API_KEY_CONFIGURED = None
        # genai.configure(api_key=None) # APIキーをNoneに設定することはできない場合がある
        return False, "APIキーが提供されていません。"
    try:
        genai.configure(api_key=api_key)
        _API_KEY_CONFIGURED = api_key # 設定成功フラグとしてキー自体を保持（is_configuredで利用）
        print(f"Gemini Handler: APIクライアントを設定しました。")
        return True, "Gemini APIクライアントが正常に設定されました。"
    except Exception as e:
        _API_KEY_CONFIGURED = None
        print(f"Gemini Handler Error: APIクライアントの設定に失敗しました - {e}")
        return False, f"APIクライアントの設定に失敗しました: {e}"

def is_configured():
    """APIクライアントが設定済みかどうかを返す"""
    return _API_KEY_CONFIGURED is not None

def generate_response(model_name, prompt_text):
    """
    指定されたモデルとプロンプトを使用してAIからの応答を生成する。
    成功した場合は (応答テキスト, None) を、失敗した場合は (None, エラーメッセージ) を返す。
    """
    if not is_configured():
        return None, "APIキーが設定されていません。先にAPIを設定してください。"
    if not model_name:
        return None, "使用するモデル名が指定されていません。"
    if not prompt_text:
        return None, "プロンプトが空です。"

    try:
        print(f"Gemini Handler: Generating response with model '{model_name}'...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt_text,
            safety_settings=_SAFETY_SETTINGS # 安全性設定を適用
        )
        # print(f"Gemini Handler: Raw response object: {response}") # デバッグ用
        # response.text でテキスト部分のみを取得
        if hasattr(response, 'text') and response.text:
            return response.text, None
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
             # ブロックされた場合の理由を取得
             block_reason = response.prompt_feedback.block_reason
             block_reason_message = response.prompt_feedback.block_reason_message if hasattr(response.prompt_feedback, 'block_reason_message') else "詳細不明"
             # safety_ratings も参照可能
             # ratings_info = "Safety Ratings: " + ", ".join([f"{rating.category.name}: {rating.probability.name}" for rating in response.prompt_feedback.safety_ratings])

             error_msg = f"応答がブロックされました。理由: {block_reason} ({block_reason_message})"
             print(f"Gemini Handler Error: {error_msg}")
             return None, error_msg
        else:
             # 予期しない応答形式
             print(f"Gemini Handler Error: 予期しない応答形式です。応答オブジェクト: {response}")
             return None, "AIから予期しない形式の応答がありました。"

    except Exception as e:
        print(f"Gemini Handler Error: AI応答の生成中にエラーが発生しました - {e}")
        import traceback
        traceback.print_exc() # スタックトレースをコンソールに出力
        return None, f"AI応答の生成中にエラーが発生しました: {e}"

# 必要であれば、モデルリスト取得などの関数もここに追加できる
# def list_available_models(): ...
