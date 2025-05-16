# core/gemini_handler.py
"""
Gemini APIとのチャット形式の対話を処理するモジュール。

このモジュールは GeminiChatHandler クラスを提供し、システム指示、
会話履歴の管理、一時的なコンテキスト情報とユーザー入力を組み合わせた
メッセージ送信、およびAIからの応答取得を扱います。
会話履歴のプロジェクトごとの保存・読み込み機能を含む。
"""

import google.generativeai as genai
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
        _model (genai.GenerativeModel | None): Geminiモデルのインスタンス。
        _chat_session (genai.ChatSession | None): 現在のチャットセッション。
        _pure_chat_history (List[Dict[str, Union[str, List[Dict[str, str]]]]]):
            アプリケーション側で管理する「純粋な」会話履歴。
            各要素は {'role': 'user'/'model', 'parts': [{'text': ...}]} の形式。
        _system_instruction_text (str | None): 現在のチャットセッションのシステム指示。
    """

    def __init__(self, model_name: str, project_dir_name: Optional[str] = None): # ★ project_dir_name を追加
        """GeminiChatHandlerのコンストラクタ。

        Args:
            model_name (str): 使用するGeminiモデルの名前。
            project_dir_name (str, optional): 対象プロジェクトのディレクトリ名。
                                            Noneの場合、履歴の保存・読み込みは行われない。
        """
        self.project_dir_name: Optional[str] = project_dir_name
        self.model_name: str = model_name
        self._model: Optional[genai.GenerativeModel] = None
        self._chat_session: Optional[genai.ChatSession] = None
        self._pure_chat_history: List[Dict[str, Union[str, List[Dict[str, str]]]]] = []
        self._system_instruction_text: Optional[str] = None
        
        if self.project_dir_name: # プロジェクト名があれば履歴を読み込む試み
            self._load_history_from_file() # ★ 履歴読み込み
            
        self._initialize_model() # モデル初期化 (システム指示はまだ未設定)

    # --- ★★★ プライベートヘルパー: 履歴ファイルパス取得 ★★★ ---
    def _get_history_file_path(self) -> Optional[str]:
        """現在のプロジェクトの履歴ファイルへのフルパスを返します。
        プロジェクト名が設定されていなければ None を返します。
        """
        if not self.project_dir_name:
            return None
        # プロジェクトディレクトリの存在確認は呼び出し元で行うか、ここで簡易的に行う
        project_path = os.path.join(PROJECTS_BASE_DIR, self.project_dir_name)
        if not os.path.isdir(project_path): # プロジェクトディレクトリがない場合
            try: # ディレクトリ作成を試みる (MainWindow側でも作成されるはずだが念のため)
                os.makedirs(project_path, exist_ok=True)
                print(f"GeminiChatHandler: Created project directory for history: {project_path}")
            except Exception as e:
                print(f"GeminiChatHandler: Error creating project directory {project_path}: {e}")
                return None # ディレクトリ作成失敗ならパスも返せない
        return os.path.join(project_path, HISTORY_FILENAME)
    # --- ★★★ ----------------------------------------- ★★★ ---

    # --- ★★★ プライベートヘルパー: 履歴ファイル読み込み ★★★ ---
    def _load_history_from_file(self):
        """現在のプロジェクトの履歴ファイルから純粋な会話履歴を読み込みます。
        ファイルが存在しない、または読み込みに失敗した場合は、履歴は空のままです。
        """
        history_file_path = self._get_history_file_path()
        if not history_file_path:
            self._pure_chat_history = [] # プロジェクト名がないなら履歴もなし
            return

        if os.path.exists(history_file_path):
            try:
                with open(history_file_path, 'r', encoding='utf-8') as f:
                    loaded_history = json.load(f)
                if isinstance(loaded_history, list): # 形式チェック (簡易)
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
            # print("Debug: Project directory name not set, cannot save history.")
            return

        try:
            # 保存先のディレクトリが存在することを確認 (get_history_file_path内で作成試行済み)
            os.makedirs(os.path.dirname(history_file_path), exist_ok=True)
            with open(history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._pure_chat_history, f, ensure_ascii=False, indent=2)
            # print(f"Chat history saved to '{history_file_path}' ({len(self._pure_chat_history)} entries).")
        except Exception as e:
            print(f"Error saving chat history to '{history_file_path}': {e}")
    # --- ★★★ ----------------------------------------- ★★★ ---


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
            self._model = genai.GenerativeModel(model_name=self.model_name, system_instruction=self._system_instruction_text)
            # ★ モデル初期化時に、現在の純粋履歴でチャットセッションを開始
            if self._model: self.start_new_chat_session(keep_history=True, load_from_file_if_empty=False) # load_from_file_if_empty はコンストラクタで実施済み
        except Exception as e: print(f"Error initializing Gemini model '{self.model_name}': {e}"); self._model = None; self._chat_session = None


    def start_new_chat_session(self, 
                               keep_history: bool = False, 
                               system_instruction_text: Optional[str] = None, 
                               load_from_file_if_empty: bool = True,
                               max_history_pairs: Optional[int] = None): # ★★★ 送信履歴の最大往復数を指定する引数 ★★★
        """新しいチャットセッションを開始します。
        既存の純粋な会話履歴を引き継ぐか、クリアするかを選択できます。
        システム指示も更新可能。履歴は維持、クリア、またはファイルからロードできます。
        送信する履歴の量も制御できます。

        Args:
            keep_history (bool): Trueの場合、現在のメモリ上の純粋な会話履歴を維持。
                                 Falseの場合、メモリ上の純粋な会話履歴をクリア。
            system_instruction_text (str, optional): 新しいシステム指示。Noneの場合は現在の指示を維持。
            load_from_file_if_empty (bool): keep_history=False で履歴をクリアした後、
                                            またはメモリ上の履歴が空の場合に、
                                            ファイルから履歴を読み込む試みをするか。
            max_history_pairs (int, optional): AIに送信する会話履歴の最大往復数 (ユーザーとAIのペア)。
                                               None の場合は全ての履歴を送信。0 の場合は履歴なし。
        """
        model_or_system_changed = False
        if system_instruction_text is not None and self._system_instruction_text != system_instruction_text:
            self._system_instruction_text = system_instruction_text
            model_or_system_changed = True
        
        if self._model is None or model_or_system_changed:
             self._initialize_model(self._system_instruction_text) # 現在のシステム指示で再初期化
        
        if not self._model:
            print("Cannot start chat session: Model not initialized.")
            return

        if not keep_history:
            self._pure_chat_history = []
            print("Chat history cleared from memory.")
            if load_from_file_if_empty and self.project_dir_name: self._load_history_from_file()
        elif load_from_file_if_empty and not self._pure_chat_history and self.project_dir_name: self._load_history_from_file()


        # --- ★★★ 送信する履歴をスライス ★★★ ---
        history_for_api = self._pure_chat_history
        if max_history_pairs is not None:
            if max_history_pairs == 0:
                history_for_api = [] # 履歴なし
                print("  履歴はありません (max_history_pairs is 0).")
            elif max_history_pairs > 0:
                num_messages_to_send = max_history_pairs * 2 # 1往復 = 2メッセージ (user, model)
                history_for_api = self._pure_chat_history[-num_messages_to_send:] # 末尾から取得
                print(f"  送信履歴：最後から {len(history_for_api)} messages (max_history_pairs: {max_history_pairs}).")
            # else: max_history_pairs が負の場合は全ての履歴 (現状は考慮しない)
        else: # max_history_pairs is None
            print(f"  全ての履歴を送信 ({len(history_for_api)} messages).")
        # --- ★★★ ------------------------- ★★★ ---

        try:
            print(f"Starting new chat session with history (length for API: {len(history_for_api)}, total pure: {len(self._pure_chat_history)})")
            self._chat_session = self._model.start_chat(history=history_for_api) # ★ スライスした履歴を使用
        except Exception as e: print(f"Error starting chat session: {e}"); self._chat_session = None

    def send_message_with_context(self, 
                                  transient_context: str, 
                                  user_input: str,
                                  max_history_pairs_for_this_turn: Optional[int] = None
                                  ) -> Tuple[Optional[str], Optional[str]]:
        """一時的なコンテキストとユーザー入力を組み合わせてメッセージを送信し、AIの応答を取得します。
        このメソッドを呼び出す前に、start_new_chat_session で適切な履歴範囲が設定された
        チャットセッションが開始されていることを前提とします。
        実際には、毎回このメソッドの最初で start_new_chat_session を呼び出し、
        最新の履歴範囲設定を適用します。

        Args:
            transient_context (str): そのターン限りのコンテキスト情報。
            user_input (str): ユーザーが実際に入力したメッセージ。
            max_history_pairs_for_this_turn (int, optional): この送受信で使用する履歴の最大往復数。
                                                           Noneの場合は全ての履歴を送信。
        """
        if not self._model:
            # APIキー未設定などでモデルが初期化されていない場合
            # configure_gemini_api の呼び出しを MainWindow 側で行うように促す
            api_configured = is_configured()
            if not api_configured:
                return None, "Gemini APIが設定されていません。「設定」からAPIキーを再設定してください。"
            
            # モデルがない場合は、現在の設定で再初期化を試みる
            print("send_message_with_context: Model not found, attempting to re-initialize model and chat session.")
            self._initialize_model(self._system_instruction_text) # 現在のシステム指示でモデル初期化
            if not self._model: # それでもダメならエラー
                return None, "チャットセッションを開始できません: モデルの初期化に失敗しました。"
        
        # --- ★★★ 毎回 start_new_chat_session を呼び出し、最新の履歴範囲を適用 ★★★ ---
        # これにより、start_new_chat_session 内のデバッグログも毎回表示されるはず。
        # keep_history=True で現在の純粋履歴を維持し、max_history_pairs を渡す。
        self.start_new_chat_session(
            keep_history=True, 
            system_instruction_text=self._system_instruction_text, # 現在のシステム指示を維持
            load_from_file_if_empty=False, # 既にロード済みのはずなので不要
            max_history_pairs=max_history_pairs_for_this_turn # ★ 渡された履歴範囲を使用
        )
        # --- ★★★ -------------------------------------------------------------- ★★★ ---

        if not self._chat_session: # start_new_chat_session でセッション開始に失敗した場合
             return None, "チャットセッションの開始に失敗しました (send_message内)。"

        full_message_to_send = ""
        if transient_context and transient_context.strip():
            full_message_to_send += f"{transient_context.strip()}\n\n"
        full_message_to_send += f"## ユーザーの入力:\n{user_input.strip()}"

        print(f"Sending message to Gemini (total length approx {len(full_message_to_send)} chars).")
        
        try:
            response = self._chat_session.send_message(full_message_to_send)
            ai_response_text = response.text

            self._pure_chat_history.append({'role': 'user', 'parts': [{'text': user_input.strip()}]})
            self._pure_chat_history.append({'role': 'model', 'parts': [{'text': ai_response_text.strip()}]})
            print(f"  AI Response received. Pure history length: {len(self._pure_chat_history)}")
            self._save_history_to_file()
            
            return ai_response_text, None
        except Exception as e:
            print(f"Error sending message or receiving response from Gemini: {e}")
            return None, str(e)

    def get_pure_chat_history(self) -> List[Dict[str, Union[str, List[Dict[str, str]]]]]:
        """現在の純粋な会話履歴を取得します。

        Returns:
            List[Dict[str, Union[str, List[Dict[str, str]]]]]: 会話履歴のリスト。
        """
        return self._pure_chat_history.copy() # コピーを返す

    def clear_pure_chat_history(self): # ★ ファイルもクリアする
        """純粋な会話履歴をメモリとファイルからクリアします。
        チャットセッションも新しい履歴（空）で再開始します。
        """
        self._pure_chat_history = []
        print("Pure chat history cleared from memory.")
        if self.project_dir_name: # プロジェクト名があればファイルもクリア（空で上書き）
            self._save_history_to_file() 
            print(f"Chat history file for project '{self.project_dir_name}' also cleared/emptied.")
            
        if self._model:
            self.start_new_chat_session(keep_history=False, load_from_file_if_empty=False) # 履歴クリアでセッション開始

    def update_settings_and_restart_chat(self, new_model_name: Optional[str] = None, new_system_instruction: Optional[str] = None, new_project_dir_name: Optional[str] = None, max_history_pairs_for_restart: Optional[int] = None):
        """モデル名、システム指示、またはプロジェクト名を更新し、
        適切な会話履歴（現在のメモリ、または新プロジェクトのファイルからロード）で
        チャットセッションを再開（再初期化）します。

        Args:
            new_model_name (str, optional): 新しいモデル名。
            new_system_instruction (str, optional): 新しいシステム指示。
            new_project_dir_name (str, optional): 新しいプロジェクトディレクトリ名。
                                                 指定された場合、そのプロジェクトの履歴をロード。
                                                 Noneの場合、現在のプロジェクトの履歴を維持。
        """
        if not is_configured(): print("Warning: Gemini API not configured. Cannot update settings."); return

        project_changed = False
        if new_project_dir_name and self.project_dir_name != new_project_dir_name:
            self.project_dir_name = new_project_dir_name
            project_changed = True
            print(f"Chat handler: Project directory name updated to '{self.project_dir_name}'.")
            self._load_history_from_file() # ★ 新しいプロジェクトの履歴をロード
        
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

        if project_changed or model_changed or system_instruction_changed:
            try:
                print(f"Re-initializing Gemini model: {self.model_name} (due to settings/project change).")
                self._model = genai.GenerativeModel(model_name=self.model_name, system_instruction=self._system_instruction_text)
            except Exception as e:
                print(f"Error re-initializing Gemini model '{self.model_name}': {e}")
                self._model = None
                self._chat_session = None
                return # モデル初期化失敗ならチャット再開も不可
        
        # モデルが（再）初期化されていれば、現在の純粋な履歴でチャットセッションを開始
        if self._model:
            try:
                # --- ★★★ start_chat に max_history_pairs を渡す ★★★ ---
                # スライス処理は start_new_chat_session 内で行われるので、
                # ここでは start_new_chat_session を呼ぶ形の方が一貫する。
                # ただし、start_new_chat_session は keep_history, load_from_file_if_empty も持つので、
                # 引数が増えすぎる。直接 start_chat を呼ぶか、start_new_chat_session のロジックを調整。
                # ここでは、start_new_chat_session を呼び出す形に統一してみる。
                print(f"Restarting chat session with updated settings, current/loaded history, and range (max_pairs: {max_history_pairs_for_restart}).")
                self.start_new_chat_session(
                    keep_history=True, # 履歴は維持 (project_changedならファイルからロード済み)
                    system_instruction_text=self._system_instruction_text, # 現在のシステム指示
                    load_from_file_if_empty=(not self._pure_chat_history), # メモリに履歴がなければロード試行
                    max_history_pairs=max_history_pairs_for_restart # ★ 渡す
                )
                # --- ★★★ --------------------------------------- ★★★ ---
            except Exception as e: print(f"Error restarting chat session: {e}"); self._chat_session = None
        else: print("Cannot restart chat session: Model not properly initialized.")

    # --- ★★★ アプリ終了時の保存用メソッド (MainWindowから呼ばれる想定) ★★★ ---
    def save_current_history_on_exit(self):
        """現在の純粋な会話履歴をファイルに明示的に保存します。
        主にアプリケーション終了時に使用します。
        """
        if self.project_dir_name and self._pure_chat_history: # 保存すべき履歴がある場合のみ
             print(f"Saving chat history for project '{self.project_dir_name}' on exit...")
             self._save_history_to_file()
    # --- ★★★ ------------------------------------------------------ ★★★ ---

    # --- ★★★ 会話履歴を任意で含める単発応答生成メソッド (インスタンスメソッド) ★★★ ---
    def generate_response_with_optional_history(
        self, 
        main_prompt_text: str, 
        num_history_pairs_to_include: Optional[int] = 0
    ) -> Tuple[Optional[str], Optional[str]]:
        """指定された主要プロンプトと、オプションで現在の会話履歴の一部をコンテキストとして、
        AIからの単発の応答を生成します。
        このメソッドは、現在のチャットセッション (_chat_session) や
        永続的な純粋会話履歴 (_pure_chat_history) を変更しません。
        現在のモデルとシステム指示を使用します。

        Args:
            main_prompt_text (str): AIへの主要な指示や質問。
            num_history_pairs_to_include (int, optional): 
                コンテキストに含める純粋な会話履歴の最新の往復数。
                0 または None の場合は履歴を含めない。デフォルトは0。

        Returns:
            Tuple[Optional[str], Optional[str]]: (AIの応答テキスト, エラーメッセージ)
        """
        if not is_configured() or not self._model: # API未設定またはモデル未初期化
            # _model は _initialize_model で設定される
            if not is_configured():
                return None, "Gemini APIが設定されていません。"
            # モデルがない場合は、現在の設定で再初期化を試みる（呼び出し元に促すのがベターだが）
            print("generate_response_with_optional_history: Model not found, attempting to re-initialize.")
            self._initialize_model(self._system_instruction_text)
            if not self._model:
                return None, "AIモデルの準備ができていません。APIキーや設定を確認してください。"
        
        if not main_prompt_text:
            return None, "主要なプロンプトテキストが空です。"

        # --- 1. 送信する履歴を準備 ---
        history_context_parts = []
        if num_history_pairs_to_include and num_history_pairs_to_include > 0 and self._pure_chat_history:
            num_messages_from_history = num_history_pairs_to_include * 2
            # スライスした履歴を取得
            history_segment_to_include = self._pure_chat_history[-num_messages_from_history:]
            
            for message in history_segment_to_include:
                role = message.get("role", "unknown")
                text = ""
                if message.get("parts") and isinstance(message["parts"], list) and message["parts"]:
                    part_content = message["parts"][0]
                    if isinstance(part_content, dict) and "text" in part_content:
                        text = part_content["text"]
                    elif isinstance(part_content, str): # parts が文字列のリストの場合
                        text = part_content
                
                if text: # テキストがあれば整形して追加
                    # 役割に応じて整形 (例: "ユーザー: こんにちは", "AI: どうも")
                    # ここではシンプルな形式で
                    history_context_parts.append(f"{'ユーザー' if role == 'user' else 'AI'}: {text}")
            print(f"  Including {len(history_context_parts)} messages from history (latest {num_history_pairs_to_include} pairs).")

        # --- 2. 最終的なプロンプトを構築 ---
        final_prompt_for_generation = ""
        if history_context_parts:
            final_prompt_for_generation += "## 関連する過去の会話履歴:\n"
            final_prompt_for_generation += "\n".join(history_context_parts)
            final_prompt_for_generation += "\n\n---\n\n" # 履歴と主要プロンプトの区切り
        
        final_prompt_for_generation += "## AIへの現在の指示:\n"
        final_prompt_for_generation += main_prompt_text

        print(f"Generating response with optional history (model: {self.model_name}, prompt length approx: {len(final_prompt_for_generation)} chars).")
        # print(f"  Final prompt for generation:\n---\n{final_prompt_for_generation}\n---") # デバッグ用

        try:
            # --- 3. AIに応答を要求 (チャットセッションは使わない) ---
            # 現在のモデルインスタンス (_model) はシステム指示を含んでいる
            response = self._model.generate_content(final_prompt_for_generation) 
            
            ai_response_text = ""
            if hasattr(response, 'text') and response.text:
                ai_response_text = response.text
            elif response.parts:
                for part in response.parts:
                    if hasattr(part, 'text'):
                        ai_response_text += part.text
            
            if not ai_response_text.strip() and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                 block_reason = response.prompt_feedback.block_reason
                 return None, f"AIからの応答がブロックされました。理由: {block_reason}"

            print("Response with optional history generated successfully.")
            return ai_response_text, None
        except Exception as e:
            print(f"Error generating response with optional history from Gemini: {e}")
            return None, str(e)
    # --- ★★★ -------------------------------------------------------------- ★★★ ---


    # --- ★★★ 単発プロンプト応答用 静的メソッド ★★★ ---
    @staticmethod
    def generate_single_response(model_name: str, prompt_text: str) -> Tuple[Optional[str], Optional[str]]:
        """指定されたプロンプトに対して、単発のAI応答を生成します。
        チャット履歴は使用・更新しません。

        Args:
            model_name (str): 使用するGeminiモデルの名前。
            prompt_text (str): AIへの完全なプロンプトテキスト。

        Returns:
            Tuple[Optional[str], Optional[str]]: (AIの応答テキスト, エラーメッセージ)
                                                 成功時は (応答テキスト, None)、失敗時は (None, エラーメッセージ)。
        """
        if not is_configured(): # モジュールレベルの is_configured() を使用
            return None, "Gemini APIが設定されていません。"
        if not model_name:
            return None, "モデル名が指定されていません。"
        if not prompt_text:
            return None, "プロンプトテキストが空です。"

        try:
            print(f"Generating single response with model '{model_name}' (prompt length: {len(prompt_text)}).")
            # 単発応答用のモデルインスタンスをここで作成
            # システム指示は単発プロンプトの場合はプロンプトテキスト内に含める想定
            model_for_single_use = genai.GenerativeModel(model_name)
            response = model_for_single_use.generate_content(prompt_text)
            
            ai_response_text = ""
            # response.text が存在するか、または response.parts からテキストを抽出
            if hasattr(response, 'text') and response.text:
                ai_response_text = response.text
            elif response.parts:
                for part in response.parts:
                    if hasattr(part, 'text'):
                        ai_response_text += part.text
            
            if not ai_response_text.strip() and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                 # 応答が空で、ブロックされた理由がある場合
                 block_reason = response.prompt_feedback.block_reason
                 return None, f"AIからの応答がブロックされました。理由: {block_reason}"

            print("Single response generated successfully.")
            return ai_response_text, None
        except Exception as e:
            print(f"Error generating single response from Gemini: {e}")
            return None, str(e)
    # --- ★★★ ----------------------------------------- ★★★ ---

# --- 以前のグローバルな generate_response 関数は削除 ---
# def generate_response(model_name: str, prompt: str) -> Tuple[Optional[str], Optional[str]]:
# (これは GeminiChatHandler.generate_single_response に置き換えられました)