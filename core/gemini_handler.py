# core/gemini_handler.py
"""
Gemini APIとのチャット形式の対話を処理するモジュール。

このモジュールは GeminiChatHandler クラスを提供し、システム指示、
会話履歴の管理、一時的なコンテキスト情報とユーザー入力を組み合わせた
メッセージ送信、およびAIからの応答取得を扱います。
"""

import google.generativeai as genai
from typing import List, Dict, Tuple, Optional, Union # 型ヒントのために追加

# --- グローバル変数 (APIキーと設定済みフラグ) ---
_API_KEY: Optional[str] = None
_IS_CONFIGURED: bool = False

def configure_gemini_api(api_key: str) -> Tuple[bool, str]:
    """Gemini APIクライアントを設定します。

    Args:
        api_key (str): Google AI Studioから取得したAPIキー。

    Returns:
        Tuple[bool, str]: 設定成功の場合は (True, "成功メッセージ")、
                          失敗の場合は (False, "エラーメッセージ")。
    """
    global _API_KEY, _IS_CONFIGURED
    if not api_key:
        _IS_CONFIGURED = False
        return False, "APIキーが空です。"
    try:
        genai.configure(api_key=api_key)
        _API_KEY = api_key
        _IS_CONFIGURED = True
        print("Gemini API client configured successfully.")
        return True, "Gemini APIクライアントが正常に設定されました。"
    except Exception as e:
        _IS_CONFIGURED = False
        print(f"Error configuring Gemini API: {e}")
        return False, f"Gemini APIクライアントの設定に失敗しました: {e}"

def is_configured() -> bool:
    """Gemini APIが設定済みかどうかを返します。

    Returns:
        bool: 設定されていれば True、そうでなければ False。
    """
    return _IS_CONFIGURED

class GeminiChatHandler:
    """Gemini APIとのチャットセッションを管理し、会話履歴を保持するクラス。

    Attributes:
        model_name (str): 使用するGeminiモデルの名前 (例: 'gemini-1.5-flash')。
        _model (genai.GenerativeModel | None): Geminiモデルのインスタンス。
        _chat_session (genai.ChatSession | None): 現在のチャットセッション。
        _pure_chat_history (List[Dict[str, Union[str, List[Dict[str, str]]]]]):
            アプリケーション側で管理する「純粋な」会話履歴。
            各要素は {'role': 'user'/'model', 'parts': [{'text': ...}]} の形式。
        _system_instruction_text (str | None): 現在のチャットセッションのシステム指示。
    """

    def __init__(self, model_name: str):
        """GeminiChatHandlerのコンストラクタ。

        Args:
            model_name (str): 使用するGeminiモデルの名前。
        """
        self.model_name: str = model_name
        self._model: Optional[genai.GenerativeModel] = None
        self._chat_session: Optional[genai.ChatSession] = None
        self._pure_chat_history: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []
        self._system_instruction_text: Optional[str] = None
        self._initialize_model()

    def _initialize_model(self, system_instruction_text: Optional[str] = None):
        """Geminiモデルを初期化（または再初期化）します。
        指定されたシステム指示でモデルを設定します。

        Args:
            system_instruction_text (str, optional): モデルに与えるシステム指示。
                                                     Noneの場合は現在の指示を維持。
        """
        if not is_configured():
            print("Error: Gemini API is not configured. Cannot initialize model.")
            self._model = None
            return

        if system_instruction_text is not None:
            self._system_instruction_text = system_instruction_text
        
        try:
            print(f"Initializing Gemini model: {self.model_name} with system instruction (length: {len(self._system_instruction_text or '')})")
            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self._system_instruction_text # ここでシステム指示を設定
            )
            # モデル初期化時にチャットセッションもリセット（履歴は保持）
            self.start_new_chat_session(keep_history=True)
        except Exception as e:
            print(f"Error initializing Gemini model '{self.model_name}': {e}")
            self._model = None
            self._chat_session = None


    def start_new_chat_session(self, keep_history: bool = False, system_instruction_text: Optional[str] = None):
        """新しいチャットセッションを開始します。
        既存の純粋な会話履歴を引き継ぐか、クリアするかを選択できます。
        システム指示も更新可能です。

        Args:
            keep_history (bool): Trueの場合、既存の純粋な会話履歴を維持します。
                                 Falseの場合、純粋な会話履歴をクリアします。
            system_instruction_text (str, optional): 新しいシステム指示。
                                                     Noneの場合は現在の指示を維持。
        """
        if system_instruction_text is not None or self._model is None or \
           (self._system_instruction_text != system_instruction_text and system_instruction_text is not None) :
            # モデルの再初期化が必要な場合 (システム指示が変わったか、モデルが未初期化)
            self._initialize_model(system_instruction_text)
        
        if not self._model:
            print("Cannot start chat session: Model not initialized.")
            return

        if not keep_history:
            self._pure_chat_history = []
            print("Chat history cleared.")

        try:
            # アプリケーション管理の純粋な会話履歴でチャットセッションを初期化
            print(f"Starting new chat session with history (length: {len(self._pure_chat_history)})")
            self._chat_session = self._model.start_chat(history=self._pure_chat_history)
        except Exception as e:
            print(f"Error starting chat session: {e}")
            self._chat_session = None

    def send_message_with_context(self, transient_context: str, user_input: str) -> Tuple[Optional[str], Optional[str]]:
        """一時的なコンテキストとユーザー入力を組み合わせてメッセージを送信し、AIの応答を取得します。
        純粋な会話履歴は内部で更新されます。

        Args:
            transient_context (str): そのターン限りのコンテキスト情報（サブプロンプト、アイテムデータなど）。
            user_input (str): ユーザーが実際に入力したメッセージ（純粋な入力）。

        Returns:
            Tuple[Optional[str], Optional[str]]: (AIの応答テキスト, エラーメッセージ)
                                                 成功時は (応答テキスト, None)、失敗時は (None, エラーメッセージ)。
        """
        if not self._chat_session:
            if not self._model:
                return None, "チャットセッションを開始できません: モデルが初期化されていません。APIキーを確認してください。"
            # チャットセッションがなければ（初回など）、ここで開始を試みる
            self.start_new_chat_session(keep_history=True) # 現在の履歴とシステム指示で
            if not self._chat_session:
                 return None, "チャットセッションの開始に失敗しました。"


        full_message_to_send = ""
        if transient_context and transient_context.strip(): # 一時コンテキストがあれば追加
            full_message_to_send += f"{transient_context.strip()}\n\n"
        full_message_to_send += f"## ユーザーの入力:\n{user_input.strip()}" # 純粋なユーザー入力

        print(f"Sending message to Gemini (total length approx {len(full_message_to_send)} chars).")
        # print(f"  Full message content:\n---\n{full_message_to_send}\n---") # デバッグ用

        try:
            # --- SDKのチャットセッションにメッセージ送信 ---
            # sendMessageは、送信メッセージと応答を自動で自身の履歴に追加するが、
            # 我々は _pure_chat_history を別途管理している。
            # SDKの履歴は、このsendMessage呼び出しのコンテキストとしてのみ使われ、
            # 次回 start_new_chat_session で _pure_chat_history から再構築される。
            response = self._chat_session.send_message(full_message_to_send)
            ai_response_text = response.text

            # --- 純粋な会話履歴を更新 ---
            self._pure_chat_history.append({'role': 'user', 'parts': [{'text': user_input.strip()}]})
            self._pure_chat_history.append({'role': 'model', 'parts': [{'text': ai_response_text.strip()}]})
            print(f"  AI Response received. Pure history length: {len(self._pure_chat_history)}")
            
            return ai_response_text, None
        except Exception as e:
            print(f"Error sending message or receiving response from Gemini: {e}")
            # エラーによっては、チャットセッションをリセットした方が良い場合もある
            # self.start_new_chat_session(keep_history=True) # 例えば接続エラー後など
            return None, str(e)

    def get_pure_chat_history(self) -> List[Dict[str, Union[str, List[Dict[str, str]]]]]:
        """現在の純粋な会話履歴を取得します。

        Returns:
            List[Dict[str, Union[str, List[Dict[str, str]]]]]: 会話履歴のリスト。
        """
        return self._pure_chat_history.copy() # コピーを返す

    def clear_pure_chat_history(self):
        """純粋な会話履歴をクリアします。
        チャットセッションも新しい履歴（空）で再開始します。
        """
        self._pure_chat_history = []
        print("Pure chat history cleared.")
        if self._model: # モデルが初期化されていれば、チャットセッションもリセット
            self.start_new_chat_session(keep_history=False) # 履歴はクリア済みで開始

    def update_settings_and_restart_chat(self, new_model_name: Optional[str] = None, new_system_instruction: Optional[str] = None):
        """モデル名またはシステム指示を更新し、現在の純粋な会話履歴を維持したまま
        チャットセッションを再開（再初期化）します。

        Args:
            new_model_name (str, optional): 新しいモデル名。Noneの場合は現在のモデル名を維持。
            new_system_instruction (str, optional): 新しいシステム指示。Noneの場合は現在の指示を維持。
        """
        if not is_configured():
            print("Warning: Gemini API not configured. Cannot update settings.")
            return

        model_changed = False
        if new_model_name and self.model_name != new_model_name:
            self.model_name = new_model_name
            model_changed = True
            print(f"Chat handler: Model name updated to '{self.model_name}'.")

        system_instruction_changed = False
        if new_system_instruction is not None and self._system_instruction_text != new_system_instruction:
            # Noneを渡された場合はシステム指示をクリアする意図かもしれないが、
            # ここではNoneなら「変更なし」として扱う。明示的に空文字列""を渡せばクリアできる。
            self._system_instruction_text = new_system_instruction
            system_instruction_changed = True
            print(f"Chat handler: System instruction updated (length: {len(self._system_instruction_text or '')}).")

        if model_changed or system_instruction_changed:
            # モデル自体かシステム指示が変わった場合は、モデルを再初期化する必要がある
            try:
                print(f"Re-initializing Gemini model: {self.model_name} (due to settings change).")
                self._model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=self._system_instruction_text
                )
            except Exception as e:
                print(f"Error re-initializing Gemini model '{self.model_name}': {e}")
                self._model = None
                self._chat_session = None
                return # モデル初期化失敗ならチャット再開も不可
        
        # モデルが（再）初期化されていれば、現在の純粋な履歴でチャットセッションを開始
        if self._model:
            try:
                print(f"Restarting chat session with updated settings and existing history (length: {len(self._pure_chat_history)}).")
                self._chat_session = self._model.start_chat(history=self._pure_chat_history)
            except Exception as e:
                print(f"Error restarting chat session with updated settings: {e}")
                self._chat_session = None
        else:
            print("Cannot restart chat session: Model not properly initialized after settings update.")

    # --- 以前の generate_response 関数は、このクラスのメソッドに置き換えられるか、
    #     あるいは単発プロンプト用として残す場合は名前を変更するなどする ---
    # def generate_response(model_name: str, prompt: str) -> Tuple[Optional[str], Optional[str]]:
    # (この関数は削除またはコメントアウトし、新しいチャットハンドラを使用するように移行)