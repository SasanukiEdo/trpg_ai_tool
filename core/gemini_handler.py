# core/gemini_handler.py

"""Google Gemini APIとの通信を処理するモジュール。

APIクライアントの設定、プロンプトの送信、応答の取得、
および基本的なエラーハンドリング機能を提供します。

主な機能:
    - configure_gemini_api: APIキーを使用してGemini APIクライアントを設定する。
    - is_configured: APIクライアントが設定済みか確認する。
    - generate_response: 指定されたモデルとプロンプトでAIからの応答を生成する。
"""

import google.generativeai as genai
import os # osモジュールは現在直接使用されていませんが、将来的な拡張のために残すことも可能です。
import traceback # エラー発生時のスタックトレース表示用

_API_KEY_CONFIGURED = None
"""str | None: 設定されたAPIキーを保持します。未設定の場合はNone。
モジュールレベルでAPIクライアントが設定済みかどうかのフラグとしても機能します。
"""

_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
"""list[dict]: Gemini APIに渡す安全性設定のリスト。
各カテゴリに対してブロック閾値を設定します。現在は全て 'BLOCK_NONE'（ブロックしない）。
"""

def configure_gemini_api(api_key: str) -> tuple[bool, str]:
    """指定されたAPIキーでGemini APIクライアントを設定します。

    この関数はアプリケーション起動時やAPIキーが変更された際に呼び出されることを想定しています。

    Args:
        api_key (str): 設定するGemini APIキー。

    Returns:
        tuple[bool, str]: 設定の成功を示すブール値と、ユーザー向けのメッセージ文字列のタプル。
                          (True, "成功メッセージ") または (False, "エラーメッセージ")
    """
    global _API_KEY_CONFIGURED
    if not api_key:
        _API_KEY_CONFIGURED = None
        msg = "APIキーが提供されていません。設定できませんでした。"
        print(f"Gemini Handler Warning: {msg}")
        return False, msg
    try:
        genai.configure(api_key=api_key)
        _API_KEY_CONFIGURED = api_key # 設定成功の証としてキーを保持
        msg = "Gemini APIクライアントが正常に設定されました。"
        print(f"Gemini Handler: {msg}")
        return True, msg
    except Exception as e:
        _API_KEY_CONFIGURED = None
        error_detail = f"APIクライアントの設定に失敗しました: {e}"
        print(f"Gemini Handler Error: {error_detail}")
        return False, error_detail

def is_configured() -> bool:
    """Gemini APIクライアントが現在設定済みであるかどうかを返します。

    Returns:
        bool: APIキーが設定されていれば True、そうでなければ False。
    """
    return _API_KEY_CONFIGURED is not None

def generate_response(model_name: str, prompt_text: str) -> tuple[str | None, str | None]:
    """指定されたモデルとプロンプトを使用してAIからの応答を生成します。

    APIが未設定の場合、モデル名やプロンプトが不正な場合はエラーメッセージを返します。
    AIからの応答がブロックされた場合や、予期せぬエラーが発生した場合もエラーメッセージを返します。

    Args:
        model_name (str): 使用するAIモデルの名前 (例: "gemini-1.5-pro-latest")。
        prompt_text (str): AIに送信するプロンプトの全文。

    Returns:
        tuple[str | None, str | None]:
            成功した場合: (AIからの応答テキスト, None)
            失敗した場合: (None, エラーメッセージ文字列)
    """
    if not is_configured():
        msg = "APIキーが設定されていません。先にAPIを設定してください。"
        print(f"Gemini Handler Error: {msg}")
        return None, msg
    if not model_name:
        msg = "使用するモデル名が指定されていません。"
        print(f"Gemini Handler Error: {msg}")
        return None, msg
    if not prompt_text: # 空のプロンプトもエラーとする
        msg = "プロンプトが空です。"
        print(f"Gemini Handler Error: {msg}")
        return None, msg

    try:
        print(f"Gemini Handler: モデル '{model_name}' を使用して応答を生成中...")
        # print(f"  送信プロンプト (最初の200文字): {prompt_text[:200]}...") # デバッグ用にプロンプト一部表示
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt_text,
            safety_settings=_SAFETY_SETTINGS
        )

        # print(f"Gemini Handler: Raw response object: {response}") # 完全なレスポンスオブジェクトのデバッグ出力

        # 応答テキストの抽出とエラーハンドリング
        if hasattr(response, 'text') and response.text:
            # print(f"Gemini Handler: 応答テキスト取得成功。")
            return response.text, None
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            block_reason_message = getattr(response.prompt_feedback, 'block_reason_message', "詳細不明")
            # 安全性評価の詳細もログに出力 (任意)
            # safety_ratings_info = "Safety Ratings: " + ", ".join([f"{rating.category.name}: {rating.probability.name}" for rating in response.prompt_feedback.safety_ratings])
            # print(f"Gemini Handler Info: {safety_ratings_info}")
            error_msg = f"応答がブロックされました。理由: {block_reason} ({block_reason_message})"
            print(f"Gemini Handler Error: {error_msg}")
            return None, error_msg
        elif not response.parts: # テキストもブロック理由もないが、partsも空の場合 (例: 不適切なコンテンツでparts自体が空になるケース)
            error_msg = "AIからの応答が空でした。コンテンツが不適切と判断された可能性があります。"
            print(f"Gemini Handler Error: {error_msg} (Prompt Feedback: {response.prompt_feedback})")
            return None, error_msg
        else:
            # その他の予期しない応答形式 (通常は上記でカバーされるはず)
            print(f"Gemini Handler Error: 予期しない応答形式です。応答オブジェクト: {response}")
            return None, "AIから予期しない形式の応答がありました。"

    except Exception as e:
        error_detail = f"AI応答の生成中に予期せぬエラーが発生しました ({model_name}): {e}"
        print(f"Gemini Handler Error: {error_detail}")
        traceback.print_exc() # 詳細なスタックトレースをコンソールに出力
        return None, error_detail

if __name__ == '__main__':
    """モジュールの基本的な動作をテストするためのコード。

    このテストを実行する前に、環境変数 GOOGLE_API_KEY に有効なAPIキーを
    設定するか、以下の `configure_gemini_api` に直接キーを渡してください。
    """
    print("--- Gemini Handler テスト ---")

    # APIキーの設定 (環境変数から取得するか、直接文字列を指定)
    # api_key_for_test = os.getenv("GOOGLE_API_KEY")
    api_key_for_test = "YOUR_API_KEY_HERE" # ここにテスト用のAPIキーを直接入力

    if api_key_for_test == "YOUR_API_KEY_HERE" or not api_key_for_test:
        print("警告: テスト用のAPIキーが設定されていません。`api_key_for_test` 変数を編集してください。")
        print("テストをスキップします。")
    else:
        config_success, config_msg = configure_gemini_api(api_key_for_test)
        print(f"API設定結果: {config_success}, メッセージ: {config_msg}")

        if config_success:
            # 1. 正常な応答テスト
            print("\n1. 正常な応答テスト (gemini-1.5-flash-latest):")
            test_prompt_1 = "こんにちは！今日の天気は？"
            response_1, error_1 = generate_response("gemini-1.5-flash-latest", test_prompt_1)
            if error_1:
                print(f"   エラー: {error_1}")
            else:
                print(f"   AIの応答: {response_1[:100]}...") # 最初の100文字だけ表示

            # 2. モデル名が不正な場合
            print("\n2. 不正なモデル名テスト:")
            response_2, error_2 = generate_response("invalid-model-name", "テストプロンプト")
            if error_2:
                print(f"   エラー (期待通り): {error_2}")
            else:
                print(f"   AIの応答 (予期せず): {response_2}")

            # 3. プロンプトが空の場合
            print("\n3. 空のプロンプトテスト:")
            response_3, error_3 = generate_response("gemini-1.5-flash-latest", "")
            if error_3:
                print(f"   エラー (期待通り): {error_3}")
            else:
                print(f"   AIの応答 (予期せず): {response_3}")

            # 4. APIが未設定の状態で呼び出し (テストのために一度Noneにするのは難しいのでコメントアウト)
            # print("\n4. API未設定テスト:")
            # global _API_KEY_CONFIGURED
            # _API_KEY_CONFIGURED = None # 強制的に未設定状態に
            # response_4, error_4 = generate_response("gemini-1.5-flash-latest", "テスト")
            # if error_4 and "APIキーが設定されていません" in error_4:
            #     print(f"   エラー (期待通り): {error_4}")
            # else:
            #     print(f"   テスト失敗: {response_4}, {error_4}")
            # configure_gemini_api(api_key_for_test) # 元に戻す

        else:
            print("APIキーの設定に失敗したため、応答生成テストはスキップします。")

    print("\n--- テスト完了 ---")

