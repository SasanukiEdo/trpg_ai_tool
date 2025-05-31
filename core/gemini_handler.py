# core/gemini_handler.py
"""
Gemini APIとのチャット形式の対話を処理するモジュール。

このモジュールは GeminiChatHandler クラスを提供し、システム指示、
会話履歴の管理、一時的なコンテキスト情報とユーザー入力を組み合わせた
メッセージ送信、およびAIからの応答取得を扱います。
会話履歴のプロジェクトごとの保存・読み込み機能を含む。
"""

import google.generativeai as genai
from google.generativeai import types as gtypes # これはそのまま使用
# from google.generativeai.types import Content, Part # ★ 削除

from typing import List, Dict, Tuple, Optional, Union
import os
import json

from core.config_manager import load_global_config, PROJECTS_BASE_DIR # 追加

# --- グローバル変数 (APIキーと設定済みフラグ) ---
_API_KEY: Optional[str] = None
_IS_CONFIGURED: bool = False
HISTORY_FILENAME = "chat_history.json" # 履歴ファイル名
# PROJECTS_BASE_DIRはconfig_managerからインポート

# --- ★★★ 安全設定の固定値 (参照されるが、API送信時には含めない方針へ) ★★★ ---
FIXED_SAFETY_SETTINGS: List[gtypes.SafetySettingDict] = [ # type: ignore
    {"category": gtypes.HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": gtypes.HarmBlockThreshold.BLOCK_NONE},
    {"category": gtypes.HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": gtypes.HarmBlockThreshold.BLOCK_NONE},
    {"category": gtypes.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": gtypes.HarmBlockThreshold.BLOCK_NONE},
    {"category": gtypes.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": gtypes.HarmBlockThreshold.BLOCK_NONE},
]
# --- ★★★ ------------------------------------------------------------- ★★★ ---

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
        # print("Gemini API client configured successfully.")
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
        project_dir_name (str | None): 現在のチャットハンドラが対象とするプロジェクトのディレクトリ名。
        model_name (str): 使用するGeminiモデルの名前。
        generation_config (gtypes.GenerationConfigDict | None): 生成制御パラメータ。
        safety_settings (List[gtypes.SafetySettingDict] | None): 安全性設定。
        _model (genai.GenerativeModel | None): Geminiモデルのインスタンス。
        _chat_session (genai.ChatSession | None): 現在のチャットセッション。
        _pure_chat_history (List[Dict[str, Union[str, List[Dict[str, str]]]]]):
            アプリケーション側で管理する「純粋な」会話履歴。
            各要素は {'role': 'user'/'model', 'parts': [{'text': ...}]} の形式。
        _system_instruction_text (str | None): 現在のチャットセッションのシステム指示。
    """

    def __init__(self, 
                 model_name: str, 
                 project_dir_name: Optional[str] = None,
                 generation_config: Optional[gtypes.GenerationConfigDict] = None,
                 safety_settings: Optional[List[gtypes.SafetySettingDict]] = None # この引数は無視される
                 ):
        """GeminiChatHandlerのコンストラクタ。

        Args:
            model_name (str): 使用するGeminiモデルの名前。
            project_dir_name (str, optional): 対象プロジェクトのディレクトリ名。
                                            Noneの場合、履歴の保存・読み込みは行われない。
            generation_config (gtypes.GenerationConfigDict, optional): 生成制御パラメータ。
            safety_settings (List[gtypes.SafetySettingDict], optional): この引数は無視され、常にBLOCK_NONEが設定されます。
        """
        self.project_dir_name: Optional[str] = project_dir_name
        self.model_name: str = model_name
        
        # generation_config の初期化 (グローバル設定から読み込む)
        if generation_config is None:
            g_config = load_global_config()
            self.generation_config: Optional[gtypes.GenerationConfigDict] = { # type: ignore
                "temperature": g_config.get("generation_temperature", 0.7),
                "top_p": g_config.get("generation_top_p", 0.95),
                "top_k": g_config.get("generation_top_k", 40),
                "max_output_tokens": g_config.get("generation_max_output_tokens", 2048),
            }
        else:
            self.generation_config = generation_config

        # safety_settings は常に固定値を設定
        self.safety_settings: Optional[List[gtypes.SafetySettingDict]] = FIXED_SAFETY_SETTINGS # type: ignore
        # print(f"GeminiChatHandler: Safety settings are fixed to BLOCK_NONE for all categories.")

        self._model: Optional[genai.GenerativeModel] = None
        self._chat_session: Optional[genai.ChatSession] = None
        self._pure_chat_history: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []
        self._system_instruction_text: Optional[str] = None
        
        if self.project_dir_name:
            self._load_history_from_file()
            
        self._initialize_model()

    # --- ★★★ プライベートヘルパー: 履歴ファイルパス取得 ★★★ ---
    def _get_history_file_path(self) -> Optional[str]:
        """現在のプロジェクトの履歴ファイルへのフルパスを返します。
        プロジェクト名が設定されていなければ None を返します。
        """
        if not self.project_dir_name:
            return None
        project_path = os.path.join(PROJECTS_BASE_DIR, self.project_dir_name)
        if not os.path.isdir(project_path):
            try:
                os.makedirs(project_path, exist_ok=True)
                # print(f"GeminiChatHandler: Created project directory for history: {project_path}")
            except Exception as e:
                print(f"GeminiChatHandler: Error creating project directory {project_path}: {e}")
                return None
        return os.path.join(project_path, HISTORY_FILENAME)
    # --- ★★★ ----------------------------------------- ★★★ ---

    # --- ★★★ プライベートヘルパー: 履歴ファイル読み込み ★★★ ---
    def _load_history_from_file(self):
        """現在のプロジェクトの履歴ファイルから純粋な会話履歴を読み込みます。
        ファイルが存在しない、または読み込みに失敗した場合は、履歴は空のままです。
        """
        history_file_path = self._get_history_file_path()
        if not history_file_path:
            self._pure_chat_history = []
            return

        if os.path.exists(history_file_path):
            try:
                with open(history_file_path, 'r', encoding='utf-8') as f:
                    loaded_history = json.load(f)
                if isinstance(loaded_history, list):
                    self._pure_chat_history = loaded_history
                    # print(f"Chat history loaded from '{history_file_path}' ({len(self._pure_chat_history)} entries).")
                else:
                    print(f"Warning: Invalid history format in '{history_file_path}'. Starting with empty history.")
                    self._pure_chat_history = []
            except Exception as e:
                print(f"Error loading chat history from '{history_file_path}': {e}. Starting with empty history.")
                self._pure_chat_history = []
        else:
            print(f"No chat history file found at '{history_file_path}'. Starting with empty history.")
            self._pure_chat_history = []
    # --- ★★★ -------------------------------------------- ★★★ ---

    # --- ★★★ プライベートヘルパー: 履歴ファイル保存 ★★★ ---
    def _save_history_to_file(self):
        """現在の純粋な会話履歴をプロジェクトの履歴ファイルに保存します。
        プロジェクト名が設定されていなければ何もしません。
        """
        history_file_path = self._get_history_file_path()
        if not history_file_path:
            return

        try:
            os.makedirs(os.path.dirname(history_file_path), exist_ok=True)
            with open(history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._pure_chat_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving chat history to '{history_file_path}': {e}")
    # --- ★★★ ----------------------------------------- ★★★ ---


    def _initialize_model(self, system_instruction_text: Optional[str] = None):
        """Geminiモデルを初期化（または再初期化）します。
        指定されたシステム指示、generation_configでモデルを設定します。
        safety_settings はAPIに送信しません。
        """
        if not is_configured():
            print("Error: Gemini API is not configured. Cannot initialize model.")
            self._model = None
            return

        if system_instruction_text is not None:
            # 新しい指示があれば更新。空文字列の場合は None にして指示なしとして扱う
            self._system_instruction_text = system_instruction_text.strip() if system_instruction_text and system_instruction_text.strip() else None
        
        try:
            model_args = {"model_name": self.model_name}
            if self._system_instruction_text: # self._system_instruction_text を参照
                model_args["system_instruction"] = self._system_instruction_text
            if self.generation_config:
                model_args["generation_config"] = self.generation_config
            
            # print(f"Initializing Gemini model: {self.model_name} with system instruction: {'provided' if self._system_instruction_text else 'omitted'}, generation_config: {'provided' if self.generation_config else 'omitted'}, safety_settings: NOT SENT TO API")
            self._model = genai.GenerativeModel(**model_args) # type: ignore
            if self._model:
                # print(f"  Gemini model '{self.model_name}' initialized successfully.")
                pass
        except Exception as e:
            print(f"Error initializing Gemini model '{self.model_name}': {e}")
            self._model = None


    def start_new_chat_session(self, 
                               keep_history: bool = False, 
                               system_instruction_text: Optional[str] = None, 
                               load_from_file_if_empty: bool = True,
                               max_history_pairs: Optional[int] = None):
        """新しいチャットセッションを開始、または既存のセッションをシステム指示や履歴設定を更新して再開します。
        モデルの再初期化もここで行う。
        システム指示はモデルに直接設定され、履歴には含めません。
        """
        if not keep_history:
            self._pure_chat_history = [] 
            if load_from_file_if_empty and self.project_dir_name:
                self._load_history_from_file() 
            elif not load_from_file_if_empty:
                 # print("Chat history cleared (not keeping existing, not loading from file).")
                 pass

        # モデルの再初期化 (システム指示が変わった場合など)
        needs_reinitialization = False
        if system_instruction_text is not None:
            current_effective_instruction = self._system_instruction_text.strip() if self._system_instruction_text else ""
            new_effective_instruction = system_instruction_text.strip() if system_instruction_text else ""
            if current_effective_instruction != new_effective_instruction:
                needs_reinitialization = True
        
        if needs_reinitialization:
            # print("System instruction will be updated. Re-initializing model.")
            self._initialize_model(system_instruction_text=system_instruction_text) 
        elif not self._model: 
            # print("Model not yet initialized. Initializing now.")
            self._initialize_model(system_instruction_text=self._system_instruction_text) # 現在の指示で初期化

        if not is_configured() or not self._model:
            print("Chat session cannot be started: Model is not configured or initialized.")
            self._chat_session = None # ChatSession は引き続き使用する想定
            return

        # --- ChatSession に渡す履歴の準備 ---
        history_for_session_start: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []
        source_history_to_use = list(self._pure_chat_history) # コピーを使用

        if max_history_pairs is not None and max_history_pairs >= 0:
            num_messages_to_keep = max_history_pairs * 2
            if len(source_history_to_use) > num_messages_to_keep:
                source_history_to_use = source_history_to_use[-num_messages_to_keep:]
                # print(f"Using last {max_history_pairs} pairs ({num_messages_to_keep} messages) from history for new session.")
        
        # クリーニング処理: _pure_chat_history は常に正しい辞書形式であることを期待
        # ここでは、ChatSessionが期待する形式に変換する処理は不要（辞書のリストでOK）
        cleaned_history_to_send = []
        for item in source_history_to_use:
            if isinstance(item, dict) and "usage" in item:
                cleaned_item = {k: v for k, v in item.items() if k != "usage"}
                cleaned_history_to_send.append(cleaned_item)
            else:
                cleaned_history_to_send.append(item)
        
        history_for_session_start = cleaned_history_to_send
        # --- 履歴クリーニング処理ここまで ---

        try:
            if self._model:
                # print(f"Attempting to start chat session with {len(history_for_session_start)} messages (max_history_pairs: {max_history_pairs}). System instruction is set in the model directly.")
                # ChatSession の history には、純粋な user/model のやり取りのみを渡す
                self._chat_session = self._model.start_chat(history=history_for_session_start) # type: ignore
            else:
                print("Error: Model is None, cannot start chat session.")
                self._chat_session = None
        except Exception as e:
            print(f"Error starting new chat session with Gemini API: {e}")
            self._chat_session = None

        if self._chat_session:
            # print(f"Chat session started/restarted successfully (Session object: {self._chat_session}).")
            pass
        else:
            print("Failed to start/restart chat session.")


    def send_message_with_context(self,
                                  transient_context: str,
                                  user_input: str,
                                  max_history_pairs_for_this_turn: Optional[int] = None
                                  ) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, int]]]:
        if not self._model:
            error_msg = "モデルが初期化されていません。"
            print(f"Error in send_message_with_context: {error_msg}")
            return None, error_msg, None
        
        try:
            messages_for_api = []

            # 1. 実際の会話履歴 (_pure_chat_history を利用)
            #    max_history_pairs_for_this_turn に基づいて、直近の会話ペアを選択
            history_to_send = []
            if self._pure_chat_history:
                if max_history_pairs_for_this_turn is not None and max_history_pairs_for_this_turn >= 0:
                    num_pairs_to_take = max_history_pairs_for_this_turn
                    # 履歴は [user, model, user, model, ...] の順なので、ペア数は *2 する
                    num_entries_to_take = num_pairs_to_take * 2
                    history_to_send = self._pure_chat_history[-num_entries_to_take:]
                    # print(f"  Sending last {len(history_to_send)} entries ({num_pairs_to_take} pairs) from chat history.")
                else: # None または負の場合は全履歴
                    history_to_send = self._pure_chat_history
                    # print(f"  Sending all {len(history_to_send)} entries from chat history.")
            
            # API送信前に、history_to_send の各アイテムから "usage" キーを除外
            cleaned_history_to_send = []
            for item in history_to_send:
                if isinstance(item, dict) and "usage" in item:
                    cleaned_item = {k: v for k, v in item.items() if k != "usage"}
                    cleaned_history_to_send.append(cleaned_item)
                else:
                    cleaned_history_to_send.append(item)
            
            messages_for_api.extend(cleaned_history_to_send) # クリーンアップされた履歴を追加

            # 2. 一時的コンテキスト、空のmodel応答、ユーザー入力 の順で追加
            if transient_context and transient_context.strip():
                messages_for_api.append({"role": "user", "parts": [{"text": transient_context.strip()}]})
                # 一時的コンテキストの後に、空のモデル応答を挟む
                # messages_for_api.append({"role": "model", "parts": [{"text": ""}]}) 

            if user_input and user_input.strip(): # ユーザー入力が空でない場合のみ追加
                messages_for_api.append({"role": "user", "parts": [{"text": user_input.strip()}]})
            else:
                # ユーザー入力が空の場合、最後が空のmodelメッセージで終わってしまうため、
                # それを削除するか、あるいはエラーとするか検討が必要。
                # 現状では、ユーザー入力がない場合はエラーとして扱う（下部のチェックで捕捉）。
                print("Warning: User input is empty. If transient_context was also empty, this might lead to an error or unexpected behavior.")

            if not messages_for_api or not any(msg.get("role") == "user" and msg.get("parts") and msg["parts"][0].get("text", "").strip() for msg in messages_for_api):
                print("Error: No messages to send to the API (history, context, and input are all empty or invalid).")
                return None, "APIに送信するメッセージがありません。", None
            
            # print(f"  Total messages being sent to API (including history): {len(messages_for_api)}")
            # --- ★★★ デバッグ用に送信内容全体を表示 (本番ではコメントアウトまたは削除推奨) ★★★ ---
            # print("  Full messages_for_api content:")
            # for i, msg in enumerate(messages_for_api):
            #     role = msg.get('role', 'N/A')
            #     parts_content = ""
            #     if 'parts' in msg and isinstance(msg['parts'], list) and msg['parts']:
            #         if isinstance(msg['parts'][0], dict) and 'text' in msg['parts'][0]:
            #             parts_content = msg['parts'][0]['text'][:100] + ('...' if len(msg['parts'][0]['text']) > 100 else '')
            #         elif isinstance(msg['parts'][0], str): # 古い形式の履歴も考慮
            #             parts_content = msg['parts'][0][:100] + ('...' if len(msg['parts'][0]) > 100 else '')
            #     print(f"    [{i}] Role: {role}, Parts Preview: '{parts_content}'")
            # --- ★★★ -------------------------------------------------------------- ★★★ ---

            # print(f"送信コンテキスト: {messages_for_api}")

            # 3. API呼び出し (常に固定の safety_settings を使用)
            response = self._model.generate_content(
                contents=messages_for_api, # type: ignore
                # safety_settings はモデル初期化時に設定済みのため、ここでは渡さない
                # generation_config もモデル初期化時に設定済み
                stream=False 
            )

            ai_response_text = ""
            usage_metadata_dict: Optional[Dict[str, int]] = None

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_metadata_dict = {
                    "input_tokens": response.usage_metadata.prompt_token_count,
                    "output_tokens": response.usage_metadata.candidates_token_count,
                    "total_token_count": response.usage_metadata.total_token_count
                }
                # print(f"Usage metadata: {usage_metadata_dict}")

            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                ai_response_text = response.candidates[0].content.parts[0].text
            elif response.prompt_feedback:
                error_msg = f"プロンプトがブロックされました。Feedback: {response.prompt_feedback}"
                if hasattr(response.prompt_feedback, 'block_reason'):
                    error_msg += f" Reason: {response.prompt_feedback.block_reason}"
                if hasattr(response.prompt_feedback, 'safety_ratings'):
                     error_msg += f" SafetyRatings: {response.prompt_feedback.safety_ratings}"
                print(f"Error in send_message_with_context: {error_msg}")
                return None, error_msg, usage_metadata_dict
            else:
                # 応答が空、または finish_reason が OTHER で parts がない場合など
                finish_reason = "Unknown"
                if response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                    finish_reason = str(response.candidates[0].finish_reason)
                error_msg = f"AIからの応答が期待する形式ではありません (Finish reason: {finish_reason})。Response: {response}"
                print(f"Error in send_message_with_context: {error_msg}")
                return None, error_msg, usage_metadata_dict

            self._pure_chat_history.append({"role": "user", "parts": [{"text": user_input.strip()}]})
            model_entry = {"role": "model", "parts": [{"text": ai_response_text}]}
            if usage_metadata_dict: # usage_metadata_dict があれば追加
                model_entry["usage"] = usage_metadata_dict
            self._pure_chat_history.append(model_entry)
            
            if self.project_dir_name:
                self._save_history_to_file()
            return ai_response_text, None, usage_metadata_dict

        except Exception as e:
            error_msg = f"メッセージ送信中にエラーが発生しました: {e}"
            print(f"Error in send_message_with_context: {error_msg}")
            import traceback
            traceback.print_exc()
            return None, error_msg, None


    def get_pure_chat_history(self) -> List[Dict[str, Union[str, List[Dict[str, str]]]]]:
        """現在の純粋な会話履歴を返します。
        外部（例：UI）で履歴を表示するために使用します。
        """
        return list(self._pure_chat_history) # 変更不可能なコピーを返す


    def clear_pure_chat_history(self): # ★ ファイルもクリアする
        """純粋な会話履歴（メモリ上およびファイル）をクリアします。
        チャットセッションも新しい空の履歴で再開します。
        """
        self._pure_chat_history = []
        self._save_history_to_file() # 空の履歴をファイルに保存してクリア
        # print("Pure chat history (memory and file) cleared.")
        # チャットセッションもリセット（履歴なしで開始）
        if self._model: # モデルが初期化されていれば
            self.start_new_chat_session(keep_history=False, system_instruction_text=self._system_instruction_text, load_from_file_if_empty=False)
            # print("Chat session restarted with empty history after clearing.")
        else:
            print("Model not initialized, chat session not restarted after clearing history.")


    def update_settings_and_restart_chat(self, 
                                         new_model_name: Optional[str] = None, 
                                         new_system_instruction: Optional[str] = None, 
                                         new_project_dir_name: Optional[str] = None,
                                         max_history_pairs_for_restart: Optional[int] = None,
                                         new_generation_config: Optional[gtypes.GenerationConfigDict] = None,
                                         new_safety_settings: Optional[List[gtypes.SafetySettingDict]] = None # この引数は無視される
                                         ):
        """モデル名、システム指示、プロジェクト、生成設定などを更新し、チャットセッションを再開します。
        変更がない場合は現在の設定を維持します。
        safety_settings は常に固定値が使用され、この引数からの変更は無視されます。
        generation_config がNoneで渡された場合は、グローバル設定から再読み込みします。
        """
        # print("GeminiChatHandler: Updating settings and restarting chat...")
        
        if new_model_name:
            self.model_name = new_model_name
            # print(f"  Model name updated to: {self.model_name}")

        if new_generation_config is not None:
            self.generation_config = new_generation_config
            # print(f"  Generation config explicitly updated.")
        else: # new_generation_configがNoneの場合、グローバル設定から再読み込み
            g_config = load_global_config()
            self.generation_config = { # type: ignore
                "temperature": g_config.get("generation_temperature", 0.7),
                "top_p": g_config.get("generation_top_p", 0.95),
                "top_k": g_config.get("generation_top_k", 40),
                "max_output_tokens": g_config.get("generation_max_output_tokens", 2048),
            }
            # print(f"  Generation config reloaded from global settings.")

        # safety_settings は常に固定 (引数は無視)
        self.safety_settings = FIXED_SAFETY_SETTINGS # type: ignore
        # print(f"  Safety settings remain fixed to BLOCK_NONE.")

        if new_project_dir_name is not None and self.project_dir_name != new_project_dir_name:
            if self.project_dir_name is not None: # 既存のプロジェクトがあれば履歴を保存
                self._save_history_to_file()
            self.project_dir_name = new_project_dir_name
            self._pure_chat_history = [] # プロジェクト変更時は履歴をクリア
            self._load_history_from_file() # 新しいプロジェクトから履歴を読み込む
            # print(f"  Project directory changed to: {self.project_dir_name}")

        if new_system_instruction is not None:
            self._system_instruction_text = new_system_instruction.strip() if new_system_instruction and new_system_instruction.strip() else None
        
        # 新しいシステム指示があれば、それを使ってチャットを再開
        # モデルの再初期化は start_new_chat_session 内でシステム指示の変更を検知して行われる
        self.start_new_chat_session(
            keep_history=True, 
            system_instruction_text=new_system_instruction, 
            load_from_file_if_empty=False, # プロジェクト変更がなければ現在の履歴を引き継ぐ
            max_history_pairs=max_history_pairs_for_restart
        )
        # print("GeminiChatHandler: Settings updated and chat session restarted.")

    # --- ★★★ ゲッターメソッド ★★★ ---
    def get_generation_config(self) -> Optional[gtypes.GenerationConfigDict]:
        """現在の生成制御パラメータを返します。"""
        return self.generation_config

    def get_safety_settings(self) -> Optional[List[gtypes.SafetySettingDict]]:
        """現在の安全性設定を返します。"""
        return self.safety_settings
    # --- ★★★ ------------------ ★★★ ---

    def save_current_history_on_exit(self):
        """現在の純粋な会話履歴をファイルに保存します。
        終了時やプロジェクト切り替え時に呼び出されることを想定。
        """
        if self.project_dir_name: # プロジェクト名がある場合のみ保存
            self._save_history_to_file()
            # print(f"Chat history saved to file for project \'{self.project_dir_name}\'.")
        else:
            print("No project selected, chat history not saved to file.")

    def delete_last_exchange_and_get_user_message(self) -> Optional[str]:
        """直前のAIの応答とそれに対応するユーザーのメッセージを会話履歴から削除し、
        そのユーザーメッセージのテキストを返します。

        Returns:
            Optional[str]: 削除されたユーザーメッセージのテキスト。
                           該当するやり取りが見つからない場合は None。
        """
        if len(self._pure_chat_history) < 2:
            return None

        last_message = self._pure_chat_history[-1]
        second_last_message = self._pure_chat_history[-2]

        if last_message.get('role') == 'model' and second_last_message.get('role') == 'user':
            # ユーザーメッセージのpartsからテキストを取得
            user_parts = second_last_message.get('parts')
            user_message_text = None
            if isinstance(user_parts, list) and len(user_parts) > 0 and 'text' in user_parts[0]:
                user_message_text = user_parts[0]['text']
            
            self._pure_chat_history.pop()  # AIの応答を削除
            self._pure_chat_history.pop()  # ユーザーのメッセージを削除
            self._save_history_to_file() # 変更をファイルに保存
            # print(f"Last exchange (user and model) deleted from history. User message: '{user_message_text[:50]}...'")
            return user_message_text
        return None

    def generate_response_with_history_and_context(
        self,
        user_instruction: str,
        item_context: Optional[str] = None,
        chat_history_to_include: Optional[List[Dict[str, Union[str, List[Dict[str, str]]]]]] = None,
        max_history_pairs: Optional[int] = None,
        override_model_name: Optional[str] = None,
        stream: bool = False
    ) -> Union[Tuple[Optional[str], Optional[str], Optional[Dict[str, int]]], genai.types.GenerateContentResponse]:
        """
        指定された会話履歴とアイテムコンテキストを考慮して、応答を生成します。
        このメソッドは永続的なチャット履歴 (_pure_chat_history) を更新しません。

        override_model_name が指定されない場合は、ハンドラに設定されている現在のモデル、
        システム指示、生成設定、安全設定を使用します。
        override_model_name が指定された場合は、そのモデルを使用し、システム指示と生成設定は
        現在のハンドラの設定が適用されます。

        stream=True の場合、応答チャンクを yield するジェネレータとして動作します。
        stream=False の場合、(応答テキスト, エラーメッセージ, 使用状況メタデータ) のタプルを返します。

        Args:
            user_instruction (str): ユーザーからの主要な指示。
            item_context (str, optional): アイテムに関する追加コンテキスト。
            chat_history_to_include (List[Dict], optional): このターンに含める会話履歴。
                                                            None の場合は _pure_chat_history が使用される。
            max_history_pairs (int, optional): 含める会話履歴の最大ペア数。None なら全て。
            override_model_name (str, optional): この呼び出しでのみ使用するモデル名。
            stream (bool, optional): Trueの場合、ストリーミング応答を有効にする。デフォルトはFalse。

        Returns:
            Union[Tuple[Optional[str], Optional[str], Optional[Dict[str, int]]], Iterable[str]]:
                stream=False の場合: (応答テキスト, エラーメッセージ, 使用状況メタデータ)
                stream=True の場合: 応答テキストチャンクをyieldするジェネレータ (実際には genai.types.GenerateContentResponse)
        """
        if not is_configured():
            error_msg = "Gemini API is not configured."
            # print(f"DEBUG: GeminiChatHandler.generate_response_with_history_and_context: {error_msg}") # DEBUG LOG
            if stream:
                # ストリームの場合、エラーメッセージをyieldするシンプルなジェネレータを返す
                def error_generator():
                    yield f"Error: {error_msg}"
                return error_generator() # DEBUG: ここでジェネレータを返すように変更
            return None, error_msg, None

        active_model_name = override_model_name if override_model_name else self.model_name
        
        # モデルインスタンスの準備 (必要ならオーバーライドモデルで再初期化)
        target_model = self._model
        temp_model_for_override = None

        # --- DEBUG LOG: モデル初期化前の状態 ---
        # print(f"DEBUG: GeminiChatHandler: active_model_name='{active_model_name}'")
        if self._model:
            # print(f"DEBUG:   Current handler model: name='{self._model.model_name}', system_instruction is {'set' if self._system_instruction_text else 'not set'}")
            # print(f"DEBUG:     System Instruction: {self._system_instruction_text if self._system_instruction_text else 'None'}")
            # print(f"DEBUG:     Generation Config: {self._model.generation_config}")
            pass
        else:
            # print("DEBUG:   Current handler model is None.")
            pass
        # --- END DEBUG LOG ---

        if override_model_name and override_model_name != self.model_name:
            # print(f"DEBUG: GeminiChatHandler: Using override model for this turn: {override_model_name}")
            # 現在のハンドラ設定（システム指示、生成設定）を流用して一時モデルを作成
            # safety_settings は API に直接渡さないのでここでは考慮不要
            model_args_override = {"model_name": override_model_name}
            if self._system_instruction_text:
                model_args_override["system_instruction"] = self._system_instruction_text
            if self.generation_config:
                model_args_override["generation_config"] = self.generation_config
            
            try:
                temp_model_for_override = genai.GenerativeModel(**model_args_override) # type: ignore
                target_model = temp_model_for_override
                # print(f"DEBUG:   Temporary model '{override_model_name}' initialized for override.")
            except Exception as e:
                error_msg = f"Error initializing override model '{override_model_name}': {e}"
                # print(f"DEBUG: GeminiChatHandler: {error_msg}") # DEBUG LOG
                if stream:
                    def error_generator_override(): # DEBUG: ジェネレータを返す
                        yield f"Error: {error_msg}"
                    return error_generator_override()
                return None, error_msg, None
        
        if not target_model:
            error_msg = f"Model ('{active_model_name}') is not initialized."
            # print(f"DEBUG: GeminiChatHandler: {error_msg}") # DEBUG LOG
            if stream:
                def error_generator_no_model(): # DEBUG: ジェネレータを返す
                    yield f"Error: {error_msg}"
                return error_generator_no_model()
            return None, error_msg, None

        # プロンプトと履歴の構築
        full_prompt_parts = []
        history_for_api = []

        # 1. システム指示 (target_model に設定済みなのでここでは不要)

        # 2. チャット履歴の準備
        source_history = chat_history_to_include if chat_history_to_include is not None else self._pure_chat_history
        
        if max_history_pairs is not None and max_history_pairs >= 0:
            # ユーザー/モデルのペアでカウントするため、要素数としては max_history_pairs * 2
            num_history_entries_to_take = max_history_pairs * 2
            effective_history = source_history[-num_history_entries_to_take:]
        else:
            effective_history = source_history # 全て

        # APIが期待する形式に変換
        for entry in effective_history:
            role = entry.get('role')
            parts_data = entry.get('parts')
            if role and isinstance(parts_data, list) and parts_data:
                 # APIに渡す履歴はContentオブジェクトのリスト
                try:
                    # parts_data は [{'text': "..."}] の形式を想定
                    history_for_api.append({'role': role, 'parts': [p['text'] for p in parts_data if 'text' in p]})
                except Exception as e:
                    print(f"Warning: Skipping history entry due to format error: {entry}, Error: {e}")
            else:
                print(f"Warning: Skipping invalid history entry: {entry}")


        # 3. アイテムコンテキストの追加 (あれば)
        if item_context and item_context.strip():
            # アイテムコンテキストはユーザー指示の直前に配置する特別なユーザーメッセージとして扱うか、
            # あるいはシステム指示の一部としてモデル初期化時に渡すのが一般的。
            # ここでは、ユーザー指示の前に挿入する形で対応。
            # parts に直接文字列のリストとして渡すのがより堅牢か
            # genai.types.Content(parts=[genai.types.Part(text=item_context)], role="user") のようにする。
            # ただし、履歴と混ぜる場合、履歴の最後の発言が user だと連続 user になる可能性があるので注意。
            # ここでは単純にテキストとして追加
            full_prompt_parts.append(f"### 提供された追加情報 ###\\n{item_context}\\n### 上記情報を踏まえて以下の指示に答えてください ###\\n")


        # 4. ユーザー指示の追加
        full_prompt_parts.append(user_instruction)
        final_user_prompt_text = "\\n\\n".join(full_prompt_parts)

        # API呼び出し用のコンテンツリストを作成
        contents_for_api = []
        if history_for_api: 
            contents_for_api.extend(history_for_api)
        
        contents_for_api.append({'role': 'user', 'parts': [final_user_prompt_text]})
        
        # print(f"DEBUG:   Effective History for API ({len(history_for_api)} entries):")
        # for i, h_entry in enumerate(history_for_api):
        #     print(f"DEBUG:     [{i}] Role: {h_entry.get('role')}, Parts: {str(h_entry.get('parts', 'N/A'))[:100]}...") # 内容を一部表示
        # print(f"DEBUG:   Final User Prompt (last part of contents): {final_user_prompt_text[:200]}...")
        # print(f"DEBUG:   Full contents_for_api to be sent (first 2 entries and last entry):")
        # if len(contents_for_api) > 3:
        #     for i in range(2): print(f"DEBUG:     [{i}] {str(contents_for_api[i])[:200]}...")
        #     print("DEBUG:     ...")
        #     print(f"DEBUG:     [-1] {str(contents_for_api[-1])[:200]}...")
        # else:
        #     for i, c_entry in enumerate(contents_for_api): print(f"DEBUG:     [{i}] {str(c_entry)[:200]}...")
        # --- END DEBUG LOG ---

        # print(f"DEBUG: GeminiChatHandler: Sending request to model '{active_model_name}' (Streaming: {stream})")
        if self._system_instruction_text:
             # print(f"DEBUG:   With System Instruction (first 100 chars): {str(self._system_instruction_text)[:100]}...")
             pass
        else:
             # print("DEBUG:   With System Instruction: None")
             pass
        # print(f"DEBUG:   With Generation Config: {self.generation_config}")


        try:
            response = target_model.generate_content(
                contents=contents_for_api, # type: ignore
                stream=stream
            )

            # --- DEBUG LOG: APIからのレスポンスオブジェクト ---
            # print(f"DEBUG: GeminiChatHandler: Received response object from API. Type: {type(response)}")
            if not stream:
                 # print(f"DEBUG:   Response (non-streamed): {str(response)[:500]}...") # 最初の500文字程度
                 pass
            # --- END DEBUG LOG ---

            if stream:
                # --- DEBUG LOG: ストリーミングの場合のレスポンス詳細 ---
                # print(f"DEBUG:   Streaming response. Prompt Feedback: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'N/A'}")
                # --- END DEBUG LOG ---
                # ストリーミングモードの場合、ジェネレータ (GenerateContentResponse) をそのまま返す
                # ここでエラーチェックを行い、エラーならエラーメッセージをyieldするジェネレータを返す
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and \
                   response.prompt_feedback.block_reason != genai.types.BlockReason.BLOCK_REASON_UNSPECIFIED:
                    error_msg = f"ストリーミング応答がブロックされました。理由: {response.prompt_feedback.block_reason.name}"
                    # print(f"DEBUG: GeminiChatHandler Stream Error: {error_msg}")
                    def stream_error_gen_blocked():
                        yield f"GENERATE_CONTENT_ERROR_STREAM: {error_msg}"
                    return stream_error_gen_blocked()
                
                # 正常なストリームを返す前に、中身が空でないかチェックする試み（ただし、これはストリームを消費してしまうので注意）
                # resolved_response = response.resolve() # ストリームを解決しようとすると、ストリームが消費される
                # if not resolved_response.text and not resolved_response.parts:
                #    print("DEBUG: GeminiChatHandler Stream Warning: Resolved stream is empty (no text, no parts). Prompt Feedback:", resolved_response.prompt_feedback)

                return response
            else:
                # 非ストリーミングモード (従来通り)
                # --- DEBUG LOG: 非ストリーミングのレスポンス詳細 ---
                # print(f"DEBUG:   Non-streaming response. Text: {response.text[:200] if hasattr(response, 'text') else 'N/A'}...")
                # print(f"DEBUG:   Prompt Feedback: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'N/A'}")
                # print(f"DEBUG:   Candidates: {response.candidates if hasattr(response, 'candidates') else 'N/A'}")
                # --- END DEBUG LOG ---

                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and \
                   response.prompt_feedback.block_reason != genai.types.BlockReason.BLOCK_REASON_UNSPECIFIED:
                    error_msg = f"応答がブロックされました。理由: {response.prompt_feedback.block_reason.name}"
                    # print(f"DEBUG: GeminiChatHandler Non-Stream Error: {error_msg}")
                    return None, error_msg, None # usage_metadata はこの場合ないかもしれない

                full_response_text = response.text
                
                usage_metadata_dict: Optional[Dict[str, int]] = None
                try:
                    if response.usage_metadata: #
                        usage_metadata_dict = {
                            "prompt_token_count": response.usage_metadata.prompt_token_count,
                            "candidates_token_count": response.usage_metadata.candidates_token_count, # v0.5.0では candidates_token_count
                            "total_token_count": response.usage_metadata.total_token_count,
                        }
                except AttributeError:
                     # 古いバージョンや、メタデータがない場合のエラーを無視
                    print("Warning: Could not retrieve usage_metadata from response (AttributeError).")
                except Exception as e_meta:
                    print(f"Warning: Error retrieving usage_metadata: {e_meta}")

                return full_response_text, None, usage_metadata_dict

        except Exception as e:
            error_msg = f"Error during Gemini API call: {e}"
            # print(f"DEBUG: GeminiChatHandler Exception: {error_msg}") # DEBUG LOG
            import traceback
            # print(f"DEBUG: Traceback: {traceback.format_exc()}") # DEBUG LOG
            
            if stream:
                def exception_error_gen(): # DEBUG: ジェネレータを返す
                    yield f"GENERATE_CONTENT_ERROR_STREAM: {error_msg}"
                return exception_error_gen()

            return None, error_msg, None

    def add_user_message_to_history(self, user_text: str, timestamp: Optional[str] = None):
        """ユーザーのメッセージを純粋な会話履歴 (_pure_chat_history) に追加します。

        Args:
            user_text (str): ユーザーが入力したテキスト。
            timestamp (str, optional): メッセージのタイムスタンプ (ISO形式推奨)。Noneなら記録しない。
        """
        if not user_text:
            return

        history_entry = {
            'role': 'user',
            'parts': [{'text': user_text}]
        }
        if timestamp:
            history_entry['timestamp'] = timestamp
        
        self._pure_chat_history.append(history_entry)
        # _save_history_to_file() はAIの応答が完了した後の方が良いかもしれないが、
        # ユーザー入力の即時性を考慮するならここでも可。ただし頻繁な書き込みになる。
        # 現状は send_message完了時やリトライ完了時にまとめて保存しているので、ここでは保存しない。
        # print(f"User message added to _pure_chat_history (not saved to file yet): {user_text[:50]}...")


    @staticmethod
    def generate_single_response(model_name: str, 
                                 prompt_text: str,
                                 system_instruction: Optional[str] = None,
                                 generation_config: Optional[gtypes.GenerationConfigDict] = None,
                                 safety_settings: Optional[List[gtypes.SafetySettingDict]] = None, # この引数は無視される
                                 project_settings: Optional[dict] = None
                                 ) -> Tuple[Optional[str], Optional[str]]: # 戻り値は変更なし
        """履歴や既存のチャットセッションに影響を与えずに、単発の応答を生成します。
        APIキーが設定されている必要があります。
        safety_settings は常に固定値 (BLOCK_NONE) が使用されます。
        project_settings が提供された場合、AI編集支援用モデル設定を優先し、
        未設定の場合はプロジェクトモデルを、それもなければ引数の model_name を使用します。

        Args:
            model_name (str): フォールバックとして使用するGeminiモデルの名前。
            prompt_text (str): AIへの指示プロンプト。
            system_instruction (str, optional): この呼び出し専用のシステム指示。デフォルトはNone。
            generation_config (gtypes.GenerationConfigDict, optional): 生成制御パラメータ。
                                                                  Noneの場合、グローバル設定が使用される。
            safety_settings (List[gtypes.SafetySettingDict], optional): 無視されます。
            project_settings (dict, optional): プロジェクト設定の辞書。AI編集支援モデルとデフォルトモデルを含む。

        Returns:
            Tuple[Optional[str], Optional[str]]: (成功した場合は生成されたテキスト, エラーメッセージまたはNone)。
        """
        if not is_configured():
            return None, "APIキーが設定されていません。"

        actual_model_name = model_name # デフォルトは引数の model_name

        if project_settings:
            ai_edit_model = project_settings.get("ai_edit_model_name", "")
            project_default_model = project_settings.get("model", model_name) # フォールバック先も引数 model_name を考慮
            if ai_edit_model and ai_edit_model.strip():
                actual_model_name = ai_edit_model.strip()
                # print(f"generate_single_response: Using AI edit model: {actual_model_name}")
            else:
                actual_model_name = project_default_model
                # print(f"generate_single_response: AI edit model not set, using project model: {actual_model_name}")
        else:
            # print(f"generate_single_response: project_settings not provided, using model_name argument: {actual_model_name}")
            pass

        # generation_config がNoneの場合、グローバル設定から取得
        current_generation_config = generation_config
        if current_generation_config is None:
            g_config = load_global_config()
            current_generation_config = { # type: ignore
                "temperature": g_config.get("generation_temperature", 0.7),
                "top_p": g_config.get("generation_top_p", 0.95),
                "top_k": g_config.get("generation_top_k", 40),
                "max_output_tokens": g_config.get("generation_max_output_tokens", 2048),
            }
            # print(f"generate_single_response: Using global generation config for model {actual_model_name}")
        else:
            # print(f"generate_single_response: Using provided generation config for model {actual_model_name}")
            pass

        # safety_settings は常に固定値を使用
        current_safety_settings = FIXED_SAFETY_SETTINGS
        # print(f"generate_single_response: Safety settings for model {actual_model_name} are fixed to BLOCK_NONE.")

        try:
            model_args = {"model_name": actual_model_name}
            if system_instruction:
                model_args["system_instruction"] = system_instruction
            if current_generation_config: # current_generation_config を使用
                model_args["generation_config"] = current_generation_config
            # safety_settings はAPI送信時に含めない方針
            # if current_safety_settings:
            #     model_args["safety_settings"] = current_safety_settings
            
            # print(f"generate_single_response: Initializing model {actual_model_name} with system_instruction: {'Yes' if system_instruction else 'No'}, generation_config: {'Yes' if current_generation_config else 'No'}")
            model = genai.GenerativeModel(**model_args) # type: ignore
            
            # print(f"generate_single_response: Sending prompt to {actual_model_name}: '{prompt_text[:50]}...'")
            response = model.generate_content(prompt_text, safety_settings=current_safety_settings) # ここでsafety_settingsを渡す

            # --- レスポンスの検証とテキスト抽出 (より堅牢に) ---
            if response and response.parts:
                # Multi-candidate responseの場合も考慮 (candidates リストの最初の要素を見る)
                candidate = response.candidates[0] if response.candidates else None
                if candidate and candidate.content and candidate.content.parts:
                    full_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                    # print(f"generate_single_response: Received response from {actual_model_name}: '{full_text[:100]}...'")
                    return full_text, None
                else:
                    error_message = "AIからの応答に有効なコンテンツが含まれていません。"
                    if candidate and candidate.finish_reason:
                         error_message += f" 終了理由: {candidate.finish_reason.name}"
                    if candidate and candidate.safety_ratings:
                        error_message += f" 安全性評価: {[(rating.category.name, rating.probability.name) for rating in candidate.safety_ratings]}"
                    # print(f"generate_single_response: Error - {error_message} (Model: {actual_model_name})")
                    return None, error_message
            elif response and response.prompt_feedback:
                # ブロックされた場合など
                feedback = response.prompt_feedback
                error_message = f"プロンプトがAIによってブロックされました。理由: {feedback.block_reason.name if feedback.block_reason else '不明'}. "
                if feedback.safety_ratings:
                    error_message += f"安全性評価: {[(rating.category.name, rating.probability.name) for rating in feedback.safety_ratings]}"
                # print(f"generate_single_response: Error - {error_message} (Model: {actual_model_name})")
                return None, error_message
            else:
                # print(f"generate_single_response: Error - AIからの予期しない応答形式です。 (Model: {actual_model_name})")
                return None, "AIからの予期しない応答形式です。"
            # --- ------------------------------------ ---

        except Exception as e:
            error_msg = f"AI応答の生成中にエラーが発生しました ({actual_model_name}): {e}"
            print(f"generate_single_response: {error_msg}")
            return None, error_msg