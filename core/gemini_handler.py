# core/gemini_handler.py
"""
Gemini APIとのチャット形式の対話を処理するモジュール。

このモジュールは GeminiChatHandler クラスを提供し、システム指示、
会話履歴の管理、一時的なコンテキスト情報とユーザー入力を組み合わせた
メッセージ送信、およびAIからの応答取得を扱います。
会話履歴のプロジェクトごとの保存・読み込み機能を含む。
"""

import google.generativeai as genai
from google.generativeai import types as gtypes # ★ gtypesとしてインポート
from typing import List, Dict, Tuple, Optional, Union
import os # ファイルパス操作用
import json # JSONデータの読み書き用

# --- グローバル変数 (APIキーと設定済みフラグ) ---
_API_KEY: Optional[str] = None
_IS_CONFIGURED: bool = False
HISTORY_FILENAME = "chat_history.json" # 履歴ファイル名
PROJECTS_BASE_DIR = "data" # プロジェクトのベースディレクトリ (config_managerと合わせる)

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
                 generation_config: Optional[gtypes.GenerationConfigDict] = None, # ★ 追加
                 safety_settings: Optional[List[gtypes.SafetySettingDict]] = None  # ★ 追加
                 ):
        """GeminiChatHandlerのコンストラクタ。

        Args:
            model_name (str): 使用するGeminiモデルの名前。
            project_dir_name (str, optional): 対象プロジェクトのディレクトリ名。
                                            Noneの場合、履歴の保存・読み込みは行われない。
            generation_config (gtypes.GenerationConfigDict, optional): 生成制御パラメータ。
            safety_settings (List[gtypes.SafetySettingDict], optional): 安全性設定。
        """
        self.project_dir_name: Optional[str] = project_dir_name
        self.model_name: str = model_name
        
        # ★★★ generation_config と safety_settings の初期化 ★★★
        if generation_config is None:
            self.generation_config: Optional[gtypes.GenerationConfigDict] = { # type: ignore
                "temperature": 0.7,
                "top_p": 1.0,
                "top_k": 32,
                "max_output_tokens": 2048,
            }
        else:
            self.generation_config = generation_config

        if safety_settings is None:
            self.safety_settings: Optional[List[gtypes.SafetySettingDict]] = [ # type: ignore
                {"category": gtypes.HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": gtypes.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
                {"category": gtypes.HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": gtypes.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
                {"category": gtypes.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": gtypes.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
                {"category": gtypes.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": gtypes.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
            ]
        else:
            self.safety_settings = safety_settings
        # ★★★ --------------------------------------------- ★★★

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
        指定されたシステム指示、generation_config、safety_settingsでモデルを設定します。
        """
        if not is_configured():
            print("Error: Gemini API is not configured. Cannot initialize model.")
            self._model = None
            return

        if system_instruction_text is not None:
            self._system_instruction_text = system_instruction_text.strip() if system_instruction_text else None
        
        try:
            effective_system_instruction = self._system_instruction_text
            if effective_system_instruction and not effective_system_instruction.strip():
                effective_system_instruction = None

            model_args = {"model_name": self.model_name}
            if effective_system_instruction:
                model_args["system_instruction"] = effective_system_instruction
            if self.generation_config:
                model_args["generation_config"] = self.generation_config
            if self.safety_settings:
                model_args["safety_settings"] = self.safety_settings
            
            print(f"Initializing Gemini model: {self.model_name} with effective system instruction: {'provided' if effective_system_instruction else 'omitted'}, generation_config: {'provided' if self.generation_config else 'omitted'}, safety_settings: {'provided' if self.safety_settings else 'omitted'}")
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
                               max_history_pairs: Optional[int] = None): # ★★★ 送信履歴の最大往復数を指定する引数 ★★★
        """新しいチャットセッションを開始、または既存のセッションをシステム指示や履歴設定を更新して再開します。
        モデルの再初期化もここで行う。

        Args:
            keep_history (bool): Trueの場合、既存の純粋な会話履歴を保持します。Falseの場合はクリアします。
            system_instruction_text (str, optional): 新しいシステム指示。Noneの場合は既存の指示を維持します。
            load_from_file_if_empty (bool): keep_historyがFalseで、ファイルから履歴を読み込むか。
            max_history_pairs (int, optional): チャットセッションに含める履歴の最大往復数。
                                                Noneの場合は全履歴。
        """
        if not keep_history:
            self._pure_chat_history = [] 
            if load_from_file_if_empty and self.project_dir_name:
                self._load_history_from_file() 
            elif not load_from_file_if_empty:
                 print("Chat history cleared (not keeping existing, not loading from file).")

        # モデルの再初期化 (システム指示が変わった場合など)
        # _initialize_model は self._system_instruction_text を参照するので、先に更新
        needs_reinitialization = False
        if system_instruction_text is not None:
            # 新しい指示が提供され、かつ現在の指示と異なる場合
            if self._system_instruction_text is None or \
               (self._system_instruction_text.strip() != system_instruction_text.strip()): # バックスラッシュによる行継続
                needs_reinitialization = True
        
        if needs_reinitialization:
            print("System instruction will be updated. Re-initializing model with new system instruction.")
            self._initialize_model(system_instruction_text=system_instruction_text) 
        elif not self._model: 
            print("Model not yet initialized. Initializing now.")
            self._initialize_model(system_instruction_text=self._system_instruction_text)

        if not is_configured() or not self._model:
            print("Chat session cannot be started: Model is not configured or initialized.")
            self._chat_session = None
            return

        history_for_api: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []
        source_history_to_use = self._pure_chat_history

        if max_history_pairs is not None and max_history_pairs >= 0:
            num_messages_to_keep = max_history_pairs * 2
            if len(source_history_to_use) > num_messages_to_keep:
                source_history_to_use = source_history_to_use[-num_messages_to_keep:]
                print(f"Using last {max_history_pairs} pairs ({num_messages_to_keep} messages) from history for new session.")
        
        # --- 履歴クリーニング処理 ---
        for msg_dict in source_history_to_use:
            cleaned_msg = {}
            role = msg_dict.get("role")
            if isinstance(role, str) and role in ["user", "model"]:
                cleaned_msg["role"] = role
            else:
                print(f"Warning: Skipping history message due to invalid or missing role: '{role}' in {msg_dict}")
                continue

            parts = msg_dict.get("parts")
            if isinstance(parts, list) and parts:
                cleaned_parts = []
                for part_item in parts:
                    if isinstance(part_item, dict):
                        text = part_item.get("text")
                        if isinstance(text, str):
                            cleaned_parts.append({"text": text})
                    elif isinstance(part_item, str):
                        cleaned_parts.append({"text": part_item})
                
                if cleaned_parts:
                    cleaned_msg["parts"] = cleaned_parts
                else:
                    print(f"Warning: Skipping history message due to no valid parts after cleaning: {msg_dict}")
                    continue
            else:
                print(f"Warning: Skipping history message due to missing or invalid parts field: {msg_dict}")
                continue
            
            history_for_api.append(cleaned_msg)
        # --- 履歴クリーニング処理ここまで ---

        try:
            if self._model:
                print(f"Attempting to start chat session with {len(history_for_api)} cleaned messages (max_history_pairs: {max_history_pairs}).")
                self._chat_session = self._model.start_chat(history=history_for_api)
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
                                  max_history_pairs_for_this_turn: Optional[int] = None # ★ このターンでのみ有効な履歴数
                                  ) -> Tuple[Optional[str], Optional[str]]:
        """一時的なコンテキストとユーザー入力を組み合わせてメッセージを送信し、AIの応答を取得します。
        送信前に、このターンでのみ有効な履歴の長さを指定してチャットセッションを再構築することが可能。

        Args:
            transient_context (str): 一時的なコンテキスト情報。
            user_input (str): ユーザーからの入力。
            max_history_pairs_for_this_turn (int, optional): 
                この送受信でのみ使用する履歴の最大往復数。
                Noneの場合、最後にstart_new_chat_sessionで設定された履歴数が使われる。
                この機能は現在、直接send_messageではサポートされていないため、
                内部でセッションを再起動する必要があるかもしれない。
                現状の実装では、max_history_pairs_for_this_turn は直接使用されていません。
                もしターンごとに履歴数を変更したい場合は、start_new_chat_session を
                適切な max_history_pairs で呼び出す必要があります。

        Returns:
            Tuple[Optional[str], Optional[str]]: (AIの応答テキスト, エラーメッセージ)。
                                                 エラー時は応答テキストがNone。
        """
        if not self._chat_session:
            print("Chat session is not active. Attempting to restart.")
            # セッションがない場合、現在の設定で再開を試みる (履歴は保持)
            self.start_new_chat_session(keep_history=True, system_instruction_text=self._system_instruction_text) 
            if not self._chat_session:
                return None, "チャットセッションを開始できませんでした。"

        full_prompt = f"{transient_context}\n\n{user_input}".strip()
        if not full_prompt:
            return None, "送信するメッセージが空です。"

        try:
            print(f"Sending message to Gemini. Prompt length: {len(full_prompt)}")
            # ★★★ send_messageに generation_config と safety_settings を渡すか検討 ★★★
            # 通常、これらは GenerativeModel または ChatSession の開始時に設定される。
            # send_message 呼び出しごとに上書きしたい場合にのみ指定する。
            # response = self._chat_session.send_message(
            #     content=full_prompt,
            #     generation_config=self.generation_config, # type: ignore
            #     safety_settings=self.safety_settings # type: ignore
            # )
            # ↑ ChatSession.send_message は直接 config/settings を引数に取らないことが多い。
            #   Model の設定が使われる。もし上書きが必要なら、Model自体を再構成するか、
            #   generate_content のような低レベルAPIを使う。
            #   ここでは、Modelに設定されたものが使われると仮定。
            
            # ChatSessionのsend_messageにはgeneration_configやsafety_settingsを直接渡す口がないため、
            # モデル初期化時の設定が利用される。
            # もしリクエストごとに変更したい場合は、都度モデルを再作成するか、
            # model.generate_contentを直接使う必要がある。
            # ここでは、現在のチャットセッションの設定で送信する。
            
            request_args = {}
            # `stream`パラメータも`send_message`にはないので注意。ストリーミングの場合は別のメソッド。
            
            # content引数には Parts のリストも渡せるが、ここでは単純なテキストプロンプト
            response = self._chat_session.send_message(content=full_prompt) # type: ignore

            ai_response_text = ""
            if response and response.parts:
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        ai_response_text += part.text
            
            if not ai_response_text and response and response.candidates: # partsが空でもcandidatesに情報がある場合
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                             if hasattr(part, 'text') and part.text:
                                ai_response_text += part.text
                        break # 最初の候補のみ

            if not ai_response_text:
                # ブロックされた場合などの対応
                block_reason = None
                if response and response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason = response.prompt_feedback.block_reason
                    print(f"Prompt was blocked. Reason: {block_reason}")
                    if response.prompt_feedback.block_reason_message:
                         print(f"Block message: {response.prompt_feedback.block_reason_message}")
                    # MainWindowでユーザーに表示できるよう、エラーメッセージに含める
                    error_message = f"送信内容がブロックされました。理由: {block_reason}"
                    if response.prompt_feedback.block_reason_message:
                         error_message += f" ({response.prompt_feedback.block_reason_message})"
                    return None, error_message

                # レスポンス候補が安全でないと判断された場合
                if response and response.candidates:
                    for candidate in response.candidates:
                        if candidate.finish_reason == gtypes.Candidate.FinishReason.SAFETY:
                            print(f"Response candidate blocked due to safety. Ratings: {candidate.safety_ratings}")
                            # 詳細なブロック理由をエラーメッセージに含める
                            blocked_categories = [rating.category.name for rating in candidate.safety_ratings if rating.probability != gtypes.SafetyRating.HarmProbability.NEGLIGIBLE]
                            error_message = f"応答が安全でないと判断されブロックされました。関連カテゴリ: {', '.join(blocked_categories) if blocked_categories else '不明'}"
                            return None, error_message
                
                # その他の理由で応答がない場合
                print("AI response was empty or not found in expected structure.")
                # responseオブジェクトの内容をログに出力してデバッグしやすくする
                # print(f"Full response object: {response}") # 大量出力の可能性あり注意

            # --- 純粋な会話履歴の更新 ---
            # ユーザーメッセージ
            self._pure_chat_history.append({"role": "user", "parts": [{"text": user_input}]}) # transient_contextは履歴に含めない
            # AIメッセージ
            if ai_response_text: # 応答があった場合のみ履歴に追加
                self._pure_chat_history.append({"role": "model", "parts": [{"text": ai_response_text}]})
            
            self._save_history_to_file() # 履歴をファイルに保存

            return ai_response_text, None

        except Exception as e:
            import traceback # スタックトレース出力用
            print(f"Error sending message: {e}\n{traceback.format_exc()}")
            # エラーレスポンスに機密情報が含まれる可能性があるため、APIからの直接のエラーメッセージは慎重に扱う
            # ここでは汎用的なエラーメッセージを返す
            return None, f"メッセージ送信中にエラーが発生しました: {type(e).__name__}"


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
                                         new_generation_config: Optional[gtypes.GenerationConfigDict] = None, # ★ 追加
                                         new_safety_settings: Optional[List[gtypes.SafetySettingDict]] = None # ★ 追加
                                         ):
        """モデル名、システム指示、プロジェクトディレクトリ、履歴数、生成設定、安全設定を更新し、
        チャットセッションを再起動します。
        Noneが指定された設定は現在の値を維持します。

        Args:
            new_model_name (str, optional): 新しいモデル名。
            new_system_instruction (str, optional): 新しいシステム指示。
            new_project_dir_name (str, optional): 新しいプロジェクトディレクトリ名。
                                                  変更された場合、履歴は新しいプロジェクトから読み込まれる。
            max_history_pairs_for_restart (int, optional): 再起動後のチャットセッション履歴の最大往復数。
            new_generation_config (gtypes.GenerationConfigDict, optional): 新しい生成制御パラメータ。
            new_safety_settings (List[gtypes.SafetySettingDict], optional): 新しい安全性設定。
        """
        print("Updating settings and restarting chat...")
        model_changed = False
        project_changed = False
        config_changed = False

        if new_model_name and new_model_name != self.model_name:
            self.model_name = new_model_name
            print(f"  Model name updated to: {self.model_name}")
            model_changed = True
            config_changed = True # モデルが変わればconfigも影響する可能性があるため再初期化

        if new_generation_config is not None: # 空の辞書も有効な設定として扱う
            self.generation_config = new_generation_config
            print(f"  Generation config updated.")
            config_changed = True

        if new_safety_settings is not None: # 空のリストも有効な設定として扱う
            self.safety_settings = new_safety_settings
            print(f"  Safety settings updated.")
            config_changed = True
        
        # システム指示は _initialize_model に渡されて初めて self._system_instruction_text に影響
        # new_system_instruction が None でない場合、または既存の指示と異なる場合に initialize_model を呼ぶ必要がある
        system_instruction_to_use = new_system_instruction if new_system_instruction is not None else self._system_instruction_text
        if new_system_instruction is not None and new_system_instruction.strip() != (self._system_instruction_text or "").strip():
             print(f"  System instruction will be updated.")
             # self._system_instruction_text は _initialize_model 内で更新される
             config_changed = True # システム指示変更もモデル再初期化のトリガー

        if new_project_dir_name and new_project_dir_name != self.project_dir_name:
            self.project_dir_name = new_project_dir_name
            print(f"  Project directory name updated to: {self.project_dir_name}")
            project_changed = True
            # プロジェクトが変わったので、履歴をクリアして新しいプロジェクトから読み込む
            self._pure_chat_history = [] 
            self._load_history_from_file() # 新しいプロジェクトの履歴をロード

        if model_changed or config_changed : # モデル自体に関する変更があった場合
            print("  Re-initializing model due to changes in model name, system instruction, generation_config, or safety_settings.")
            self._initialize_model(system_instruction_text=system_instruction_to_use) # 更新された可能性のあるシステム指示を使用
            if not self._model:
                print("  Failed to re-initialize model. Chat session cannot be restarted.")
                self._chat_session = None
                return

        # モデルの再初期化後、またはプロジェクト変更後にチャットセッションを開始/再開
        # keep_history は True (プロジェクト変更時は上記でロード済み、それ以外は既存履歴維持)
        print("  Starting new chat session with updated settings...")
        self.start_new_chat_session(
            keep_history=True, # 履歴は既に処理済み (プロジェクト変更時ロード or 既存維持)
            system_instruction_text=self._system_instruction_text, # _initialize_modelで更新されたものを使う
            max_history_pairs=max_history_pairs_for_restart
        )
        print("Settings updated and chat restarted.")

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
                                 safety_settings: Optional[List[gtypes.SafetySettingDict]] = None
                                 ) -> Tuple[Optional[str], Optional[str]]:
        """チャット履歴なしで、単一のプロンプトに対する応答を生成します。
        特定のツール機能や、履歴に依存しない応答生成に使用できます。

        Args:
            model_name (str): 使用するモデル名。
            prompt_text (str): 送信するプロンプトテキスト。
            system_instruction (str, optional): システム指示。
            generation_config (gtypes.GenerationConfigDict, optional): 生成制御パラメータ。
            safety_settings (List[gtypes.SafetySettingDict], optional): 安全性設定。

        Returns:
            Tuple[Optional[str], Optional[str]]: (AIの応答テキスト, エラーメッセージ)。
        """
        if not is_configured():
            return None, "Gemini APIが設定されていません。"
        if not prompt_text:
            return None, "プロンプトが空です。"

        try:
            model_args = {"model_name": model_name}
            if system_instruction and system_instruction.strip():
                model_args["system_instruction"] = system_instruction.strip()
            
            # ★★★ generate_single_responseでもgeneration_configとsafety_settingsを渡す ★★★
            # こちらはGenerativeModelの初期化ではなく、generate_contentメソッドに渡す想定
            # genai.GenerativeModelのコンストラクタで設定するか、
            # model.generate_contentの引数で設定するか、SDKの仕様による。
            # ここでは、model.generate_contentの引数で渡す形を試みる。
            # いや、やはりModel初期化時に渡す方が一貫性がある。
            # ただし、この静的メソッドではHandlerインスタンスがないため、
            # デフォルト値を直接ここで定義するか、引数で受け取る必要がある。
            # 引数で受け取る方式を採用。

            if generation_config:
                model_args["generation_config"] = generation_config # type: ignore
            if safety_settings:
                model_args["safety_settings"] = safety_settings # type: ignore
            
            model = genai.GenerativeModel(**model_args) # type: ignore
            
            # generate_contentの引数にもconfigとsafety_settingsを渡せるが、
            # Model初期化時に渡したのであれば、そちらが優先されるか、上書きされる。
            # ここではModel初期化時に設定したため、generate_contentには渡さない。
            # もしgenerate_contentごとに変えたい場合は、以下のようにする。
            # response = model.generate_content(
            #    prompt_text,
            #    generation_config=generation_config, # type: ignore
            #    safety_settings=safety_settings # type: ignore
            # )
            response = model.generate_content(prompt_text) # type: ignore

            ai_response_text = ""
            if response and response.parts:
                 for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        ai_response_text += part.text
            elif response and response.candidates: # partsが空でもcandidatesに情報がある場合
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                             if hasattr(part, 'text') and part.text:
                                ai_response_text += part.text
                        break # 最初の候補のみ
            
            if not ai_response_text:
                 # ブロックされた場合の対応 (send_message_with_contextと同様のロジック)
                block_reason = None
                if response and response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason = response.prompt_feedback.block_reason
                    error_message = f"送信内容がブロックされました。理由: {block_reason}"
                    if response.prompt_feedback.block_reason_message:
                         error_message += f" ({response.prompt_feedback.block_reason_message})"
                    return None, error_message
                if response and response.candidates:
                    for candidate in response.candidates:
                        if candidate.finish_reason == gtypes.Candidate.FinishReason.SAFETY:
                            blocked_categories = [rating.category.name for rating in candidate.safety_ratings if rating.probability != gtypes.SafetyRating.HarmProbability.NEGLIGIBLE]
                            error_message = f"応答が安全でないと判断されブロックされました。関連カテゴリ: {', '.join(blocked_categories) if blocked_categories else '不明'}"
                            return None, error_message
                return None, "AIからの応答が空でした。"

            return ai_response_text, None
        except Exception as e:
            import traceback
            print(f"Error in generate_single_response: {e}\n{traceback.format_exc()}")
            return None, f"単一応答生成中にエラーが発生しました: {type(e).__name__}"