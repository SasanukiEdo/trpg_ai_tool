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

# --- グローバル変数 (APIキーと設定済みフラグ) ---
_API_KEY: Optional[str] = None
_IS_CONFIGURED: bool = False
HISTORY_FILENAME = "chat_history.json" # 履歴ファイル名
PROJECTS_BASE_DIR = "data" # プロジェクトのベースディレクトリ (config_managerと合わせる)

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
        
        # generation_config の初期化
        if generation_config is None:
            self.generation_config: Optional[gtypes.GenerationConfigDict] = { # type: ignore
                "temperature": 0.7,
                "top_p": 1.0,
                "top_k": 32,
                "max_output_tokens": 2048,
            }
        else:
            self.generation_config = generation_config

        # safety_settings は常に固定値を設定
        self.safety_settings: Optional[List[gtypes.SafetySettingDict]] = FIXED_SAFETY_SETTINGS # type: ignore
        print(f"GeminiChatHandler: Safety settings are fixed to BLOCK_NONE for all categories.")

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
                print(f"GeminiChatHandler: Created project directory for history: {project_path}")
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
                    print(f"Chat history loaded from '{history_file_path}' ({len(self._pure_chat_history)} entries).")
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
            
            print(f"Initializing Gemini model: {self.model_name} with system instruction: {'provided' if self._system_instruction_text else 'omitted'}, generation_config: {'provided' if self.generation_config else 'omitted'}, safety_settings: NOT SENT TO API")
            self._model = genai.GenerativeModel(**model_args) # type: ignore
            if self._model:
                print(f"  Gemini model '{self.model_name}' initialized successfully.")
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
                 print("Chat history cleared (not keeping existing, not loading from file).")

        # モデルの再初期化 (システム指示が変わった場合など)
        needs_reinitialization = False
        if system_instruction_text is not None:
            current_effective_instruction = self._system_instruction_text.strip() if self._system_instruction_text else ""
            new_effective_instruction = system_instruction_text.strip() if system_instruction_text else ""
            if current_effective_instruction != new_effective_instruction:
                needs_reinitialization = True
        
        if needs_reinitialization:
            print("System instruction will be updated. Re-initializing model.")
            self._initialize_model(system_instruction_text=system_instruction_text) 
        elif not self._model: 
            print("Model not yet initialized. Initializing now.")
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
                print(f"Using last {max_history_pairs} pairs ({num_messages_to_keep} messages) from history for new session.")
        
        # クリーニング処理: _pure_chat_history は常に正しい辞書形式であることを期待
        # ここでは、ChatSessionが期待する形式に変換する処理は不要（辞書のリストでOK）
        history_for_session_start = source_history_to_use
        # --- 履歴クリーニング処理ここまで ---

        try:
            if self._model:
                print(f"Attempting to start chat session with {len(history_for_session_start)} messages (max_history_pairs: {max_history_pairs}). System instruction is set in the model directly.")
                # ChatSession の history には、純粋な user/model のやり取りのみを渡す
                self._chat_session = self._model.start_chat(history=history_for_session_start) # type: ignore
            else:
                print("Error: Model is None, cannot start chat session.")
                self._chat_session = None
        except Exception as e:
            print(f"Error starting new chat session with Gemini API: {e}")
            self._chat_session = None

        if self._chat_session:
            print(f"Chat session started/restarted successfully (Session object: {self._chat_session}).")
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
            messages_for_api: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []

            # 1. 実際の会話履歴 (_pure_chat_history を利用)
            effective_history_pairs = max_history_pairs_for_this_turn if max_history_pairs_for_this_turn is not None else (len(self._pure_chat_history) // 2)
            history_to_send = []
            if self._pure_chat_history:
                num_history_items_to_send = effective_history_pairs * 2
                temp_history = list(self._pure_chat_history[-num_history_items_to_send:])
                for item in temp_history:
                    if not (
                        isinstance(item, dict) and
                        isinstance(item.get("role"), str) and
                        isinstance(item.get("parts"), list) and
                        all(isinstance(part, dict) and isinstance(part.get("text"), str) for part in item["parts"])
                    ):
                        print(f"Warning: Invalid history item format found and skipped: {item}")
                        continue
                    # item から "usage" を除外した新しい辞書を作成する
                    item_to_send = {k: v for k, v in item.items() if k != "usage"}
                    history_to_send.append(item_to_send)
            messages_for_api.extend(history_to_send)

            # 2. 一時的コンテキスト (user ロール)
            if transient_context and transient_context.strip(): 
                messages_for_api.append({
                    "role": "user",
                    "parts": [{"text": transient_context.strip()}]
                })

            # 3. 実際のユーザー入力 (user ロール)
            if not user_input or not user_input.strip():
                return None, "ユーザー入力が空です。", None
            messages_for_api.append({
                "role": "user",
                "parts": [{"text": user_input.strip()}]
            })

            print(f"GeminiChatHandler: Sending messages to API via generate_content ({len(messages_for_api)} entries). System instruction is set in model.")
            
            response = self._model.generate_content(
                contents=messages_for_api, # type: ignore
                generation_config=self.generation_config,
            )

            ai_response_text = ""
            usage_metadata_dict: Optional[Dict[str, int]] = None

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_metadata_dict = {
                    "input_tokens": response.usage_metadata.prompt_token_count,
                    "output_tokens": response.usage_metadata.candidates_token_count,
                    "total_token_count": response.usage_metadata.total_token_count
                }
                print(f"Usage metadata: {usage_metadata_dict}")

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
        print("Pure chat history (memory and file) cleared.")
        # チャットセッションもリセット（履歴なしで開始）
        if self._model: # モデルが初期化されていれば
            self.start_new_chat_session(keep_history=False, system_instruction_text=self._system_instruction_text, load_from_file_if_empty=False)
            print("Chat session restarted with empty history after clearing.")
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
        """設定を更新し、チャットセッションを再起動します。
        プロジェクトディレクトリやシステム指示、モデル名、履歴の最大ペア数、生成設定を更新できます。
        安全性設定は常にBLOCK_NONEに固定されているため、このメソッドからは変更できません。
        """
        print("GeminiChatHandler: Updating settings and restarting chat session...")
        
        if new_project_dir_name is not None and self.project_dir_name != new_project_dir_name:
            if self.project_dir_name is not None: # 既存のプロジェクトがあれば履歴を保存
                self._save_history_to_file()
            self.project_dir_name = new_project_dir_name
            self._pure_chat_history = [] # プロジェクト変更時は履歴をクリア
            self._load_history_from_file() # 新しいプロジェクトから履歴を読み込む
            print(f"  Project directory changed to: {self.project_dir_name}")

        if new_model_name is not None and self.model_name != new_model_name:
            self.model_name = new_model_name
            print(f"  Model name changed to: {self.model_name}")
            # モデル名が変更されたら、システム指示も合わせてモデルを再初期化する必要がある
            self._initialize_model(system_instruction_text=new_system_instruction if new_system_instruction is not None else self._system_instruction_text)
        
        if new_generation_config is not None:
            self.generation_config = new_generation_config
            print(f"  Generation config updated.")
            # generation_configが変更された場合、モデル再初期化が必要か確認 (通常は再初期化)
            # ただし、システム指示やモデル名が変わらない場合、start_new_chat_sessionでモデルが再利用されることを期待する
            if not (new_model_name or new_system_instruction):
                 self._initialize_model(system_instruction_text=self._system_instruction_text)

        # 安全設定は固定なので、new_safety_settings は無視する
        if new_safety_settings is not None:
            print("  Note: Safety settings are fixed and cannot be changed via this method.")

        # 新しいシステム指示があれば、それを使ってチャットを再開
        # モデルの再初期化は start_new_chat_session 内でシステム指示の変更を検知して行われる
        self.start_new_chat_session(
            keep_history=True, 
            system_instruction_text=new_system_instruction, 
            load_from_file_if_empty=False, # プロジェクト変更がなければ現在の履歴を引き継ぐ
            max_history_pairs=max_history_pairs_for_restart
        )
        print("GeminiChatHandler: Settings updated and chat session restarted.")

    # --- ★★★ ゲッターメソッド ★★★ ---
    def get_generation_config(self) -> Optional[gtypes.GenerationConfigDict]:
        """現在の生成制御パラメータを返します。"""
        return self.generation_config

    def get_safety_settings(self) -> Optional[List[gtypes.SafetySettingDict]]:
        """現在の安全性設定を返します。"""
        return self.safety_settings
    # --- ★★★ ------------------ ★★★ ---

    def save_current_history_on_exit(self):
        """アプリケーション終了時などに現在の履歴を保存するためのメソッド。
        実際には send_message_with_context 内で都度保存しているため、
        明示的な呼び出しは不要かもしれないが、念のため。
        """
        if self.project_dir_name: # プロジェクト名が設定されている場合のみ
            print("Attempting to save chat history on exit...")
            self._save_history_to_file()
            print("Chat history saving process on exit completed.")
        else:
            print("Project directory name not set, skipping history save on exit.")


    @staticmethod
    def generate_single_response(model_name: str, 
                                 prompt_text: str,
                                 system_instruction: Optional[str] = None,
                                 generation_config: Optional[gtypes.GenerationConfigDict] = None,
                                 safety_settings: Optional[List[gtypes.SafetySettingDict]] = None # この引数は無視される
                                 ) -> Tuple[Optional[str], Optional[str]]:
        """単一のプロンプトに対する応答を生成します。
        チャット履歴は考慮されません。
        safety_settings はAPIに送信しません。
        """
        if not is_configured():
            return None, "Error: Gemini API is not configured."
        
        try:
            # 安全設定をAPI送信から除外
            # effective_safety_settings = FIXED_SAFETY_SETTINGS # 参照しない
            
            model_args = {"model_name": model_name}
            if system_instruction:
                model_args["system_instruction"] = system_instruction
            if generation_config:
                model_args["generation_config"] = generation_config
            # model_args["safety_settings"] = effective_safety_settings # type: ignore # safety_settings をAPI送信から除外

            print(f"Generating single response with model: {model_name}, safety_settings: NOT SENT TO API (using SDK/API defaults)")
            model = genai.GenerativeModel(**model_args) # type: ignore
            response = model.generate_content(prompt_text)
            
            if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text, None
            elif response and response.prompt_feedback:
                return None, f"Error: Prompt was blocked. Feedback: {response.prompt_feedback}"
            else:
                return None, "Error: No content in response or response was empty."
        except Exception as e:
            return None, f"Error generating single response: {e}"