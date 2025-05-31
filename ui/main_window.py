# ui/main_window.py

"""TRPG AI Toolのメインウィンドウとアプリケーション全体の制御を提供します。

このモジュールは `MainWindow` クラスを定義しており、ユーザーインターフェースの
主要な部分（メインプロンプト入力、AI応答表示、サブプロンプト管理、
データ管理など）を統合し、ユーザー操作に応じて各機能モジュールと連携します。

プロジェクト単位でのデータ管理の基盤となり、アクティブなプロジェクトの
設定やデータを読み込み、UIに反映する役割も担います。
プロジェクトの選択、新規作成、削除機能も提供します。
"""

import sys
import os
import json
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QTextBrowser, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView,
    QTabWidget, QApplication, QDialog, QSplitter, QFrame, QCheckBox,
    QSizePolicy, QStyle, qApp, QInputDialog, QComboBox, QLineEdit,QDialogButtonBox, QSlider, QGroupBox, QTreeWidgetItemIterator,
    QRadioButton # ★★★ QRadioButton を追加 ★★★
)
from PyQt5.QtGui import QTextCursor # ★★★ QTextCursor を QtGui からインポート ★★★
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QUrl, QEvent, QThread, QDateTime # ★★★ QEvent を追加 ★★★, QThread を追加, QDateTime を追加
import re # ディレクトリ名検証用
from typing import Optional, List, Dict, Tuple, Union # Union を追加

# --- プロジェクトルートをパスに追加 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- coreモジュールインポート ---
from core.config_manager import (
    load_global_config, save_global_config,
    load_project_settings, save_project_settings,
    list_project_dir_names,
    DEFAULT_PROJECT_SETTINGS,
    get_project_dir_path,
    delete_project_directory,
    DEFAULT_GLOBAL_CONFIG # ★ 追加
)
from core.subprompt_manager import load_subprompts, save_subprompts, DEFAULT_SUBPROMPTS_DATA # 新規作成時用
from core.data_manager import get_project_gamedata_path, create_category, get_item  # 新規作成時用
from core.api_key_manager import get_api_key as get_os_api_key # OS資格情報からAPIキー取得

# --- uiモジュールインポート ---
from ui.settings_dialog import SettingsDialog
from ui.subprompt_dialog import SubPromptEditDialog
from ui.data_widget import DataManagementWidget
from ui.prompt_preview_dialog import PromptPreviewDialog # ★ 追加

# --- Gemini API ハンドラー ---
from core.gemini_handler import GeminiChatHandler, configure_gemini_api, is_configured # クラスと関数をインポート
import google.generativeai as genai # for BlockReason


# ==============================================================================
# ストリーミング処理用ワーカースレッド
# ==============================================================================
class StreamingWorker(QThread):
    """AIからのストリーミング応答をバックグラウンドで処理するワーカースレッド。"""
    chunk_received = pyqtSignal(str)  # 逐次受信するテキストチャンク
    streaming_started = pyqtSignal(str, str) # AI名, モデル名
    streaming_finished = pyqtSignal(str, dict, str)  # 最終的な完全なテキスト, usage_metadata, モデル名
    streaming_error = pyqtSignal(str)  # エラーメッセージ

    def __init__(self, chat_handler: GeminiChatHandler,
                 user_instruction: str,
                 item_context: Optional[str],
                 chat_history_to_include: Optional[List[Dict]],
                 max_history_pairs: Optional[int],
                 override_model_name: Optional[str],
                 stream: bool, # ★ stream パラメータを追加
                 parent=None):
        super().__init__(parent)
        self.chat_handler = chat_handler
        self.user_instruction = user_instruction
        self.item_context = item_context
        self.chat_history_to_include = chat_history_to_include
        self.max_history_pairs = max_history_pairs
        self.override_model_name = override_model_name
        self.stream = stream # ★ インスタンス変数に保存
        self._raw_chunks_for_full_text = []

    def run(self):
        try:
            if not self.chat_handler:
                self.streaming_error.emit("Chat handler is not available.")
                return

            active_model_name = self.override_model_name if self.override_model_name else self.chat_handler.model_name
            # self.streaming_started.emit("AI", active_model_name) # ★ stream=Falseの場合は開始シグナルを遅延または変更検討

            self._raw_chunks_for_full_text = []
            
            response_data = self.chat_handler.generate_response_with_history_and_context(
                user_instruction=self.user_instruction,
                item_context=self.item_context,
                chat_history_to_include=self.chat_history_to_include,
                max_history_pairs=self.max_history_pairs,
                override_model_name=self.override_model_name,
                stream=self.stream
            )

            if not self.stream:
                # --- 非ストリーミングの場合の処理 ---
                self.streaming_started.emit("AI", active_model_name) # ★ここで開始通知
                if isinstance(response_data, tuple) and len(response_data) == 3:
                    full_response_text, error_msg, usage_metadata = response_data
                    if error_msg:
                        self.streaming_error.emit(error_msg)
                    elif full_response_text is not None: # 応答テキストがNoneでないことを確認
                        self.streaming_finished.emit(full_response_text, usage_metadata or {}, active_model_name)
                    else: # テキストもエラーもない場合は、何らかの問題があったと見なす
                        self.streaming_error.emit("AIからの応答が空でした（非ストリーミング）。")
                else:
                    # 予期しない形式のレスポンス
                    self.streaming_error.emit(f"AIからの応答が予期しない形式です（非ストリーミング）。Data: {str(response_data)[:100]}")
                return # 非ストリーミングの場合はここで終了

            # --- ストリーミングの場合の処理 (ここから下は self.stream が True の場合のみ実行) ---
            self.streaming_started.emit("AI", active_model_name) # ★ ストリーミングの場合もここで開始通知
            response_stream_iterable = response_data # stream=True の場合、response_data はイテラブル

            full_response_text = "" # この変数はストリーミングでは不要になった
            usage_metadata = {} 
            
            first_chunk_processed = False
            stream_had_error_flag = False

            for chunk in response_stream_iterable: # type: ignore
                if not first_chunk_processed:
                    first_chunk_processed = True
                    # ストリームの最初の要素がエラーメッセージ文字列かどうかを確認
                    if isinstance(chunk, str) and (chunk.startswith("Error: ") or chunk.startswith("GENERATE_CONTENT_ERROR_STREAM:")):
                        print(f"StreamingWorker: Detected error string in the stream: {chunk}")
                        self.streaming_error.emit(chunk)
                        stream_had_error_flag = True
                        # エラーが検出されたら、ジェネレータの残りを消費して正しく終了させる
                        for _ in response_stream_iterable: pass
                        break # エラーループから抜ける

                    # 最初のチャンクが genai.types.GenerateContentResponse の一部であるか基本的なチェック
                    # (本格的なチャンク処理は次で行う)
                    if not hasattr(chunk, 'text') and not hasattr(chunk, 'parts'): # GeminiのChunkは通常textかpartsを持つ
                        error_msg = f"ストリーミングエラー: 最初のチャンクが予期しない形式です。Type: {type(chunk)}"
                        if isinstance(chunk, str): error_msg += f", Content: {chunk[:100]}"
                        print(f"StreamingWorker: {error_msg}")
                        self.streaming_error.emit(error_msg)
                        stream_had_error_flag = True
                        for _ in response_stream_iterable: pass
                        break


                if stream_had_error_flag: # 上でエラーが検出されたら、以降のチャンク処理はスキップ
                    continue

                # --- 通常のチャンク処理 ---
                text_part = ""
                try:
                    # まず parts からテキストを取得試行
                    if hasattr(chunk, 'parts') and chunk.parts and hasattr(chunk.parts[0], 'text') and chunk.parts[0].text:
                        text_part = chunk.parts[0].text
                    # parts にテキストがない場合、次に chunk.text を試行 (これがエラーの原因だった箇所)
                    elif hasattr(chunk, 'text') and chunk.text: # ここで ValueError が発生する可能性
                        text_part = chunk.text
                    
                    # 取得したテキストパートがあれば処理
                    if text_part:
                        self._raw_chunks_for_full_text.append(text_part)
                        self.chunk_received.emit(text_part)

                except ValueError as e:
                    # chunk.text アクセス時に ValueError が発生した場合 (finish_reason が RECITATION など)
                    print(f"StreamingWorker: ValueError accessing chunk.text: {e}")
                    # finish_reason を確認
                    finish_reason_val = None
                    reason_name = "UNKNOWN"
                    if hasattr(chunk, 'candidates') and chunk.candidates and hasattr(chunk.candidates[0], 'finish_reason'):
                        finish_reason_val = chunk.candidates[0].finish_reason
                        # finish_reason はenumなので、名前を取得する試み (genai.types.Candidate.FinishReason にアクセスできるか不明)
                        try:
                            # genai.types.Candidate.FinishReason は直接アクセスできない可能性があるため、汎用的に
                            reason_name = finish_reason_val.name if hasattr(finish_reason_val, 'name') else str(finish_reason_val)
                        except Exception:
                            reason_name = str(finish_reason_val) # 最悪、数値で表示

                    error_msg_detail = f"AIの応答チャンク取得中にエラー。理由: {reason_name} ({e})"
                    if finish_reason_val == 5: # FINISH_REASON_RECITATION
                        error_msg_detail = f"AIが広範囲の引用を検出したため応答を停止しました (理由: RECITATION)。"
                    elif finish_reason_val == 2: # FINISH_REASON_SAFETY
                         error_msg_detail = f"AIが安全でない可能性のあるコンテンツを検出したため応答を停止しました (理由: SAFETY)。"
                # ストリーミング応答時に文章の重複が発生するため以下の処理はコメントアウト
                # if hasattr(chunk, 'text') and chunk.text:
                #    text_part = chunk.text
                #    self._raw_chunks_for_full_text.append(text_part)
                #    self.chunk_received.emit(text_part)
                    # full_response_text += text_part # 下でjoinするので不要

                # usage_metadata は通常、最後のチャンクまたは response オブジェクト自体に含まれる
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    try:
                        usage_metadata = {
                            "prompt_token_count": chunk.usage_metadata.prompt_token_count,
                            "candidates_token_count": chunk.usage_metadata.candidates_token_count,
                            "total_token_count": chunk.usage_metadata.total_token_count,
                        }
                    except AttributeError:
                        pass 
            
            if stream_had_error_flag: # エラーでループを抜けた場合はここで終了
                return

            # ストリーミング完了後、GenerateContentResponseオブジェクトから直接usage_metadataを取得試行
            # (response_stream_iterable が GenerateContentResponse の場合)
            if not usage_metadata and hasattr(response_stream_iterable, 'usage_metadata') and response_stream_iterable.usage_metadata: # type: ignore
                try:
                    final_usage = response_stream_iterable.usage_metadata # type: ignore
                    usage_metadata = {
                        "prompt_token_count": final_usage.prompt_token_count,
                        "candidates_token_count": final_usage.candidates_token_count, # Geminiのドキュメントではこれ
                        "total_token_count": final_usage.total_token_count,
                    }
                except Exception as e_meta_final:
                    print(f"Could not get final usage_metadata from GenerateContentResponse object: {e_meta_final}")
            
            # prompt_feedbackでエラーを確認 (GenerateContentResponseオブジェクトから)
            if hasattr(response_stream_iterable, 'prompt_feedback') and \
               response_stream_iterable.prompt_feedback and \
               response_stream_iterable.prompt_feedback.block_reason != genai.types.BlockReason.BLOCK_REASON_UNSPECIFIED: # type: ignore
                error_msg = f"ストリーミング応答がブロックされました。理由: {response_stream_iterable.prompt_feedback.block_reason.name}" # type: ignore
                self.streaming_error.emit(error_msg)
                return

            if not first_chunk_processed and not self._raw_chunks_for_full_text:
                 # チャンクが一つも処理されなかった場合（空のストリームだった場合など）
                 # これをエラーとして扱うか、空の成功として扱うかは要件による
                 # ここでは、空の成功として扱い、空のテキストで完了とする
                 print("StreamingWorker: Stream was empty or yielded no processable chunks, but no explicit error was caught. Completing with empty text.")


            final_text = "".join(self._raw_chunks_for_full_text)
            self.streaming_finished.emit(final_text, usage_metadata, active_model_name)

        except Exception as e:
            import traceback
            error_details = f"StreamingWorker error: {e}\\n{traceback.format_exc()}"
            print(error_details)
            self.streaming_error.emit(f"ストリーミング処理中に予期せぬエラーが発生しました: {e}")


# ==============================================================================
# サブプロンプト項目用カスタムウィジェット (MainWindow内で定義)
# ==============================================================================
class SubPromptItemWidget(QWidget):
    """サブプロンプトリストの各項目を表示・操作するためのカスタムウィジェット。

    サブプロンプト名を表示するチェックボックス、編集ボタン、削除ボタンを提供します。
    これらの操作はシグナルを通じて親ウィジェット（MainWindow）に通知されます。

    Attributes:
        checkStateChanged (pyqtSignal): チェックボックスの状態変更時に発行。bool値を渡す。
        editRequested (pyqtSignal): 編集ボタンクリック時に発行。
        deleteRequested (pyqtSignal): 削除ボタンクリック時に発行。
        name (str): このウィジェットが表すサブプロンプトの名前。
    """
    checkStateChanged = pyqtSignal(bool)
    editRequested = pyqtSignal()
    deleteRequested = pyqtSignal()

    def __init__(self, name: str, is_checked: bool = False, parent: QWidget | None = None):
        """SubPromptItemWidgetのコンストラクタ。

        Args:
            name (str): 表示するサブプロンプトの名前。
            is_checked (bool, optional): チェックボックスの初期状態。デフォルトは False。
            parent (QWidget | None, optional): 親ウィジェット。デフォルトは None。
        """
        super().__init__(parent)
        self.name: str = name
        """str: このウィジェットが表すサブプロンプトの名前。"""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        self.checkbox = QCheckBox(name)
        self.checkbox.setChecked(is_checked)
        self.checkbox.stateChanged.connect(lambda state: self.checkStateChanged.emit(state == Qt.Checked))
        layout.addWidget(self.checkbox, 1) # チェックボックスがスペースを優先的に使用

        edit_button = QPushButton()
        edit_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton)) # 編集アイコン
        edit_button.setToolTip(f"サブプロンプト「{name}」を編集")
        edit_button.setFixedSize(24, 24)
        edit_button.clicked.connect(self.editRequested.emit)
        layout.addWidget(edit_button)

        delete_button = QPushButton()
        delete_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon)) # 削除アイコン
        delete_button.setToolTip(f"サブプロンプト「{name}」を削除")
        delete_button.setFixedSize(24, 24)
        delete_button.clicked.connect(self.deleteRequested.emit)
        layout.addWidget(delete_button)

        self.setLayout(layout)

    def set_name(self, name: str):
        """ウィジェットに表示されるサブプロンプト名を更新します。

        Args:
            name (str): 新しいサブプロンプト名。
        """
        self.name = name
        self.checkbox.setText(name)

    def set_checked(self, checked: bool):
        """チェックボックスの状態をプログラムから設定します。シグナルは発行しません。

        Args:
            checked (bool): 新しいチェック状態。
        """
        self.checkbox.blockSignals(True) # シグナル発行を一時的に抑制
        self.checkbox.setChecked(checked)
        self.checkbox.blockSignals(False)

    def is_checked(self) -> bool:
        """現在のチェックボックスの状態を返します。

        Returns:
            bool: チェックされていれば True、そうでなければ False。
        """
        return self.checkbox.isChecked()

# ==============================================================================
# メインウィンドウクラス
# ==============================================================================
class MainWindow(QWidget):
    """TRPG AI Tool のメインウィンドウクラス。

    アプリケーションのUI全体の構築、ユーザーインタラクションの処理、
    コア機能モジュールとの連携、プロジェクトデータの管理など、
    アプリケーションの中心的な役割を担います。
    プロジェクト選択機能も提供します。

    Attributes:
        global_config (dict): アプリケーション全体のグローバル設定。
        current_project_dir_name (str): 現在アクティブなプロジェクトのディレクトリ名。
        current_project_settings (dict): 現在アクティブなプロジェクトの固有設定。
        subprompts (dict): 現在アクティブなプロジェクトのサブプロンプトデータ。
        checked_subprompts (dict): {カテゴリ名: {サブプロンプト名のセット}} でチェック状態を保持。
        gemini_configured (bool): Gemini APIが設定済みかを示すフラグ。
        project_selector_combo (QComboBox): プロジェクト選択用コンボボックス。
        system_prompt_input_main (QTextEdit): メインシステムプロンプト入力エリア。
        response_display (QTextBrowser): AI応答履歴表示エリア。
        user_input (QTextEdit): ユーザーメッセージ入力エリア。
        send_button (QPushButton): メッセージ送信ボタン。
        settings_button (QPushButton): 設定ダイアログを開くボタン。
        subprompt_tab_widget (QTabWidget): サブプロンプトカテゴリ表示用タブ。
        data_management_widget (DataManagementWidget): データ管理エリア用ウィジェット。
        new_project_button (QPushButton): 新規プロジェクト作成ダイアログを開くボタン。
        delete_project_button (QPushButton): 現在アクティブなプロジェクトを削除するボタン。
    """

    def __init__(self):
        """MainWindowのコンストラクタ。UIの初期化とプロジェクトデータの読み込みを行います。
        GeminiChatHandler のインスタンスも保持し、プロジェクト名を渡します。
        """
        super().__init__()
        self.global_config: dict = {}
        """dict: `data/config.json` から読み込まれたグローバル設定。"""
        self.current_project_dir_name: str = "default_project" # 初期プロジェクト名を設定
        """str: 現在アクティブなプロジェクトのディレクトリ名。"""
        self.current_project_settings: dict = {}
        """dict: 現在アクティブなプロジェクトの `project_settings.json` の内容。"""
        self.subprompts: dict = {}
        """dict: 現在アクティブなプロジェクトの `subprompts.json` の内容。
        {カテゴリ名: {サブプロンプト名: {"prompt": ..., "model": ...}}} の形式。
        """
        self.checked_subprompts: dict[str, set[str]] = {}
        # self.gemini_configured: bool = False # is_configured() で確認するので不要かも
        self._projects_list_for_combo: list[tuple[str, str]] = []

        # self.enable_streaming = True # ★ 初期化タイミングを global_config 確定後に変更
        self.streaming_checkbox: Optional[QCheckBox] = None # ★ チェックボックスのインスタンス (init_uiで作成)
        
        # --- ★★★ GeminiChatHandler のインスタンスを初期化 (プロジェクト名も渡す) ★★★ ---
        # current_project_dir_name は _initialize_configs_and_project の前に必要
        # まずグローバル設定からアクティブプロジェクト名を取得
        temp_global_config_for_init = load_global_config() # _initialize_configs_and_project より前に呼ぶ必要あり
        self.current_project_dir_name = temp_global_config_for_init.get("active_project", "default_project")
        
        # initial_model_name は self.global_config 確定後に設定
        self.chat_handler: Optional[GeminiChatHandler] = None

        # --- 送信履歴範囲用のメンバー変数 (初期値は self.global_config 確定後に設定) ---
        self.current_history_range_for_prompt: int = 25 # 一時的なデフォルト値
        self.item_history_range_for_prompt: int = 5 # アイテム履歴用はデフォルト5往復
        # --- --------------------------------- ---

        # --- アイテム履歴の送信数設定用メンバー変数 ---
        self.item_history_length_for_prompt: int = 10 # デフォルト10件
        # --- ----------------------------------------- ---

        # --- クイックセット関連のメンバー変数 ---
        from core.config_manager import NUM_QUICK_SET_SLOTS # スロット数をインポート
        self.num_quick_set_slots = NUM_QUICK_SET_SLOTS
        self.quick_sets_data: Dict[str, Optional[Dict]] = {} # ロードしたクイックセットデータ
        # UI要素をリストで保持 (後でループ処理するため)
        self.quick_set_name_labels: List[QLabel] = []
        self.quick_set_apply_buttons: List[QPushButton] = []
        self.quick_set_send_buttons: List[QPushButton] = []
        self.quick_set_save_buttons: List[QPushButton] = []
        self.quick_set_clear_buttons: List[QPushButton] = []
        # --- ------------------------------------ ---
        
        # --- 送信キーモード用のメンバー変数 (初期値は self.global_config 確定後に設定) ---
        self.send_on_enter_mode: bool = True # 一時的なデフォルト値
        # --- --------------------------------- ---

        # --- 状態表示ラベルを追加 ---
        self.status_label = QLabel() # 状態表示用ラベル
        # --- ----------------------- ---
        
        # --- ストリーミング有効状態 (初期値は self.global_config 確定後に設定) ---
        self.enable_streaming = True # 一時的なデフォルト値
        # --- ---------------------------------------------------- ---

        # --- 送信内容確認ボタン ---
        self.preview_prompt_button = QPushButton("送信内容確認")
        self.preview_prompt_button.setToolTip("送信するプロンプトの最終形や設定を確認します。")
        self.preview_prompt_button.clicked.connect(self._show_prompt_preview_dialog)
        # --- ----------------------- ---

        # --- リトライボタン ---
        self.retry_button = QPushButton("リトライ")
        self.retry_button.setToolTip("直前のAIの応答を削除し、同じメッセージを再送信します。")
        self.retry_button.clicked.connect(self._on_retry_button_clicked)
        self.retry_button.setEnabled(False) # 初期状態は無効
        # --- ----------------- ---

        self._initialize_configs_and_project()
        self.configure_gemini_and_chat_handler()  # APIキー設定、必要ならハンドラ再設定
        
        # --- ★★★ 各種設定値を self.global_config から読み込み、インスタンス変数に最終設定 ★★★ ---
        self.send_on_enter_mode = self.global_config.get("send_on_enter_mode", DEFAULT_GLOBAL_CONFIG.get("send_on_enter_mode", True))
        self.current_history_range_for_prompt = self.global_config.get("history_range_for_prompt", DEFAULT_GLOBAL_CONFIG.get("history_range_for_prompt", 25))
        self.enable_streaming = self.global_config.get("enable_streaming", DEFAULT_GLOBAL_CONFIG.get("enable_streaming", True))
        # --- ★★★ -------------------------------------------------------------------------- ★★★ ---

        initial_model_name = self.global_config.get(
            "default_model", 
            DEFAULT_PROJECT_SETTINGS.get("model", "gemini-1.5-flash") # フォールバック
        )
        initial_system_prompt = self.current_project_settings.get("main_system_prompt", "")
        self._initialize_chat_handler(model_name=initial_model_name, project_dir_name=self.current_project_dir_name, system_instruction=initial_system_prompt)
        
        self.init_ui() # ★★★ UI初期化を chat_handler 初期化後に移動 ★★★
                        # _redisplay_chat_history が self.response_display を使うため

        # --- ★★★ アプリケーション起動時に履歴を画面に表示 ★★★ ---
        if self.chat_handler and is_configured(): # API設定済みでハンドラがあれば
            self._redisplay_chat_history()
        # --- ★★★ ------------------------------------------ ★★★ ---
        self.update_status_label() # ★★★ 追加: 起動時にステータス更新 ★★★

        self.is_streaming = False # ストリーミング状態フラグ
        self._current_streaming_ai_message_id: Optional[str] = None # ストリーミング中のAIメッセージブロックのID
        self._current_streaming_content_element_id: Optional[str] = None # ストリーミング中のAIメッセージ本文のID

    def _initialize_chat_handler(self, model_name: str, project_dir_name: str, system_instruction: Optional[str] = None): # ★ project_dir_name を必須引数に
        if not project_dir_name:
            QMessageBox.critical(self, "致命的なエラー", "チャットハンドラの初期化にプロジェクト名が指定されませんでした。")
            self.chat_handler = None
            return

        # 既存のハンドラがあれば終了処理を試みる (ファイル保存など)
        if self.chat_handler:
            self.chat_handler.save_current_history_on_exit()

        # --- ★★★ global_config を使用して生成パラメータを設定 ★★★ ---
        gen_conf_from_global = {
            "temperature": self.global_config.get("generation_temperature", DEFAULT_PROJECT_SETTINGS.get("model_temperature", 0.7)), # プロジェクト設定も考慮
            "top_p": self.global_config.get("generation_top_p", DEFAULT_PROJECT_SETTINGS.get("model_top_p", 0.95)),
            "top_k": self.global_config.get("generation_top_k", DEFAULT_PROJECT_SETTINGS.get("model_top_k", 40)),
            "max_output_tokens": self.global_config.get("generation_max_output_tokens", DEFAULT_PROJECT_SETTINGS.get("model_max_tokens", 2048)),
        }
        # プロジェクト設定に specific な生成パラメータがあればそれで上書き
        # current_project_settings は _initialize_configs_and_project で設定される
        # ここでは、それが呼ばれる前なので、global のみで初期化し、プロジェクトロード後に update_chat_handler_settings で更新する
        # ↑ このコメントは古い。このメソッドは self.global_config 確定後に呼ばれる想定。
        
        effective_system_instruction = system_instruction
        if not effective_system_instruction and self.current_project_settings: # current_project_settings が利用可能なら
             effective_system_instruction = self.current_project_settings.get("main_system_prompt", "")


        print(f"Initializing GeminiChatHandler with model: {model_name}, project: {project_dir_name}, system_instr: {'Yes' if effective_system_instruction else 'No'}")
        self.chat_handler = GeminiChatHandler(
            model_name=model_name,
            project_dir_name=project_dir_name, # 必須
            generation_config=gen_conf_from_global # type: ignore
            # safety_settings はハンドラ内部で固定
        )
        # システム指示は start_new_chat_session で設定されるので、ここでは直接設定しないか、
        # あるいは start_new_chat_session をこの直後に呼ぶことを徹底する。
        # ここでは、直接 _initialize_model を呼んで設定を試みる
        if self.chat_handler:
            self.chat_handler._initialize_model(system_instruction_text=effective_system_instruction)
            # 履歴の再読み込みも必要に応じて行う。start_new_chat_sessionが良い。
            self.chat_handler.start_new_chat_session(keep_history=True, system_instruction_text=effective_system_instruction, load_from_file_if_empty=True)


    def _set_ui_for_streaming(self, is_streaming: bool):
        """ストリーミング状態に応じてUI要素の有効/無効を切り替える。"""
        self.is_streaming = is_streaming
        enable = not is_streaming

        # 1. 送信ボタン
        if hasattr(self, 'send_button'):
            self.send_button.setEnabled(enable)
        
        # 2. リトライボタン
        if hasattr(self, 'retry_button'):
            can_retry = enable and (self.chat_handler and len(self.chat_handler.get_pure_chat_history()) >= 2)
            self.retry_button.setEnabled(can_retry)

        # 3. チャット履歴の各エントリーの「編集」「削除」ボタン
        #    _handle_history_link_clicked で self.is_streaming をチェックして対応済

        # 4. プロジェクト切り替えメニュー (QComboBoxとして実装されている)
        if hasattr(self, 'project_selector_combo'):
             self.project_selector_combo.setEnabled(enable)
        
        # プロジェクト関連ボタンも無効化
        if hasattr(self, 'new_project_button'):
            self.new_project_button.setEnabled(enable)
        if hasattr(self, 'delete_project_button'): # delete_project_button の有効無効はプロジェクト選択状態にも依存する
            is_deletable_project = self.current_project_dir_name != "default_project" and self.current_project_dir_name is not None
            self.delete_project_button.setEnabled(enable and is_deletable_project)


        # 5. クイックセット機能の送信ボタン (self.quick_set_send_buttons)
        if hasattr(self, 'quick_set_send_buttons'):
            for btn in self.quick_set_send_buttons:
                btn.setEnabled(enable)
        
        # メッセージ入力欄も無効化
        if hasattr(self, 'user_input'):
            self.user_input.setEnabled(enable)
        
        # システムプロンプト入力欄も無効化
        if hasattr(self, 'system_prompt_input_main'):
            self.system_prompt_input_main.setReadOnly(is_streaming)

        # 設定ボタンも無効化
        if hasattr(self, 'settings_button'):
            self.settings_button.setEnabled(enable)

        # サブプロンプトタブの操作も無効化 (タブ切り替えは許可し、中身の操作を制限するか、タブ自体を無効化)
        if hasattr(self, 'subprompt_tab_widget'):
            self.subprompt_tab_widget.setEnabled(enable) # タブウィジェット自体を無効化

        # データ管理ウィジェットも無効化
        if hasattr(self, 'data_management_widget'):
            self.data_management_widget.setEnabled(enable)


        QApplication.processEvents() # UIの更新を即時反映


    def _initialize_configs_and_project(self):
        """グローバル設定を読み込み、アクティブなプロジェクトのデータをロードします。"""
        print("--- MainWindow: Initializing configurations and project data ---")
        self.global_config = load_global_config()
        # --- ★★★ 送信キーモードのデフォルト値をglobal_configに書き込む(初回起動時など) ★★★ ---
        if "send_on_enter_mode" not in self.global_config:
            self.global_config["send_on_enter_mode"] = True # デフォルト
            save_global_config(self.global_config) # 保存
        # --- ★★★ -------------------------------------------------------------- ★★★ ---
        self.current_project_dir_name = self.global_config.get("active_project", "default_project")
        print(f"  Active project directory name from global config: '{self.current_project_dir_name}'")
        self._load_current_project_data() # 実際のデータ読み込み

    def _load_current_project_data(self):
        """現在アクティブなプロジェクトの各種設定・データを読み込み、UI要素も更新します。

        `self.current_project_settings`, `self.subprompts` を更新し、
        ウィンドウタイトル、メインシステムプロンプト表示などを更新します。
        `DataManagementWidget` のプロジェクトも設定します（UI初期化後）。
        チェック状態もプロジェクト設定から復元します。
        """
        print(f"--- MainWindow: Loading data for project: '{self.current_project_dir_name}' ---")
        project_settings_loaded = load_project_settings(self.current_project_dir_name)
        if project_settings_loaded is None: # 読み込み/作成失敗
            print(f"  FATAL: Failed to load or initialize project settings for '{self.current_project_dir_name}'. Using fallback.")
            self.current_project_settings = DEFAULT_PROJECT_SETTINGS.copy()
            self.current_project_settings["project_display_name"] = f"{self.current_project_dir_name} (読込エラー)"
        else:
            self.current_project_settings = project_settings_loaded
        
        project_display_name_for_title = self.current_project_settings.get("project_display_name", self.current_project_dir_name)
        self.setWindowTitle(f"TRPG AI Tool - {project_display_name_for_title}")
        print(f"  Project settings loaded: Name='{project_display_name_for_title}', Model='{self.current_project_settings.get('model')}'")

        self.subprompts = load_subprompts(self.current_project_dir_name)
        
        # --- ★★★ チェック状態の復元 (サブプロンプト) ★★★ ---
        # プロジェクト設定から checked_subprompts を読み込む
        # 保存形式は {"カテゴリ名": ["サブプロンプト名1", "サブプロンプト名2"], ...} と想定
        # self.checked_subprompts は {カテゴリ名: set(サブプロンプト名)}
        saved_checked_subprompts_list_format = self.current_project_settings.get("checked_subprompts", {})
        self.checked_subprompts = {
            cat: set(names) for cat, names in saved_checked_subprompts_list_format.items()
            if cat in self.subprompts # 存在しないカテゴリは無視
        }
        # 存在しないサブプロンプト名もフィルタリング (任意だが安全のため)
        for cat, names_set in self.checked_subprompts.items():
            if cat in self.subprompts:
                self.checked_subprompts[cat] = {
                    name for name in names_set if name in self.subprompts[cat]
                }
        print(f"  Checked subprompts restored: {self.checked_subprompts}")
        # --- ★★★ ------------------------------------ ★★★ ---

        print(f"  Subprompts loaded: {len(self.subprompts)} categories.")

        # UI要素が既に初期化されていれば、内容を反映
        if hasattr(self, 'system_prompt_input_main'):
            self.system_prompt_input_main.setPlainText(
                self.current_project_settings.get("main_system_prompt", "")
            )
        
        # DataManagementWidget のプロジェクトも設定（UI初期化後）
        if hasattr(self, 'data_management_widget') and self.data_management_widget:
            self.data_management_widget.set_project(self.current_project_dir_name)
            # --- ★★★ チェック状態の復元 (データアイテム) ★★★ ---
            # プロジェクト設定から checked_data_items を読み込む
            # 保存形式は {"カテゴリ名": ["アイテムID1", "アイテムID2"], ...} と想定
            saved_checked_data_items_list_format = self.current_project_settings.get("checked_data_items", {})
            # DataManagementWidget の check_items_by_dict は Dict[str, List[str]] を期待
            # そのため、ここではセットに変換せず、そのまま渡す (存在チェックは DataWidget 側で行う想定)
            if saved_checked_data_items_list_format: # 空でなければ適用
                self.data_management_widget.uncheck_all_items() # 念のため全解除
                self.data_management_widget.check_items_by_dict(saved_checked_data_items_list_format)
            print(f"  Checked data items restored (passed to DataManagementWidget): {saved_checked_data_items_list_format}")
            # --- ★★★ -------------------------------------- ★★★ ---


        # サブプロンプトタブもUIがあれば更新
        if hasattr(self, 'subprompt_tab_widget'):
            self.refresh_subprompt_tabs() # これによりチェック状態もUIに反映される


    # --- ★★★ 新規: クイックセットデータをファイルからロードしUIに反映 ★★★ ---
    def _load_quick_sets(self):
        """現在のプロジェクトのクイックセットデータをファイルからロードし、
        UI（スロットのラベル名など）に反映します。
        """
        from core.config_manager import QUICK_SETS_FILENAME, PROJECTS_BASE_DIR # 定数をインポート
        
        self.quick_sets_data = {} # まずリセット
        qsets_file_path = os.path.join(PROJECTS_BASE_DIR, self.current_project_dir_name, QUICK_SETS_FILENAME)

        if os.path.exists(qsets_file_path):
            try:
                with open(qsets_file_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    self.quick_sets_data = loaded_data
                    print(f"Quick sets loaded from '{qsets_file_path}'.")
                else:
                    print(f"Warning: Invalid format in quick sets file '{qsets_file_path}'.")
            except Exception as e:
                print(f"Error loading quick sets from '{qsets_file_path}': {e}")
        else:
            print(f"No quick sets file found at '{qsets_file_path}'. Initializing with empty sets.")
            # ファイルがない場合は、空のデータで初期化 (各スロットをnullに)
            for i in range(self.num_quick_set_slots):
                self.quick_sets_data[f"slot_{i}"] = None

        # UIの更新
        self._update_quick_set_slots_display()
    # --- ★★★ --------------------------------------------------------- ★★★ ---

    # --- ★★★ 新規: クイックセットスロットの表示を更新するヘルパー ★★★ ---
    def _update_quick_set_slots_display(self):
        """現在の self.quick_sets_data に基づいて、
        各クイックセットスロットのラベル名とボタンの有効状態を更新します。
        """
        if not hasattr(self, 'quick_set_name_labels'): return # UI未初期化

        for i in range(self.num_quick_set_slots):
            slot_id = f"slot_{i}"
            slot_data = self.quick_sets_data.get(slot_id)

            if slot_data and isinstance(slot_data, dict) and "name" in slot_data:
                self.quick_set_name_labels[i].setText(f"{i+1}: {slot_data['name']}")
                self.quick_set_name_labels[i].setToolTip(f"クイックセット名: {slot_data['name']}")
                self.quick_set_apply_buttons[i].setEnabled(True)
                self.quick_set_send_buttons[i].setEnabled(True)
                # self.quick_set_save_buttons[i] は常に有効 (上書きのため)
                self.quick_set_clear_buttons[i].setEnabled(True)
            else: # スロットが空またはデータ不正
                self.quick_set_name_labels[i].setText(f"{i+1}:")
                self.quick_set_name_labels[i].setToolTip("このスロットは現在空です。")
                self.quick_set_apply_buttons[i].setEnabled(False)
                self.quick_set_send_buttons[i].setEnabled(False)
                # self.quick_set_save_buttons[i] は常に有効 (新規保存のため)
                self.quick_set_clear_buttons[i].setEnabled(False)
    # --- ★★★ --------------------------------------------------------- ★★★ ---



    def init_ui(self):
        """メインウィンドウのユーザーインターフェースを構築します。"""
        self.setWindowTitle(f"TRPG AI Tool - 初期化中...")
        self.setGeometry(200, 200, 1400, 1000)

        main_layout = QHBoxLayout(self)

        # --- 左側エリア (メインプロンプト、AI応答履歴、ユーザー入力) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_layout.addWidget(QLabel("<b>メインシステムプロンプト:</b>"))
        self.system_prompt_input_main = QTextEdit()
        self.system_prompt_input_main.setPlaceholderText("AIへの全体的な指示を入力...")
        self.system_prompt_input_main.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # 高さは固定
        left_layout.addWidget(self.system_prompt_input_main)
        self.system_prompt_input_main.setFixedHeight(100)

        # --- AI応答履歴ラベルとスクロールボタン ---
        history_display_header_layout = QHBoxLayout() # 水平レイアウト
        history_display_label = QLabel("<b>AI応答履歴:</b>")
        history_display_header_layout.addWidget(history_display_label)
        history_display_header_layout.addStretch() # ボタンを右に寄せるためのスペーサー

        self.scroll_to_top_button = QPushButton("↑ 先頭へ")
        self.scroll_to_top_button.setToolTip("履歴の先頭に移動します")
        self.scroll_to_top_button.setFixedSize(80, 25)
        self.scroll_to_top_button.clicked.connect(self._scroll_history_to_top)
        history_display_header_layout.addWidget(self.scroll_to_top_button)

        self.scroll_to_bottom_button = QPushButton("↓ 末尾へ")
        self.scroll_to_bottom_button.setToolTip("履歴の末尾（最新）に移動します")
        self.scroll_to_bottom_button.setFixedSize(80, 25)
        self.scroll_to_bottom_button.clicked.connect(self._scroll_history_to_bottom)
        history_display_header_layout.addWidget(self.scroll_to_bottom_button)
        
        left_layout.addLayout(history_display_header_layout)

        # --- QTextBrowser の設定変更とシグナル接続 ---
        self.response_display = QTextBrowser()
        self.response_display.setObjectName("responseDisplay")
        self.response_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.response_display.setOpenLinks(False)
        self.response_display.anchorClicked.connect(self._handle_history_link_clicked)

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            qss_file_path_for_document = os.path.join(current_dir, "style.qss")
            with open(qss_file_path_for_document, "r", encoding="utf-8") as f_doc_style:
                doc_style_sheet = f_doc_style.read()
                self.response_display.document().setDefaultStyleSheet(doc_style_sheet)
                print(f"Document stylesheet set for responseDisplay from: {qss_file_path_for_document}")
        except FileNotFoundError:
            print(f"Warning: Document stylesheet file not found at {qss_file_path_for_document} for responseDisplay.")
        except Exception as e:
            print(f"Error setting document stylesheet for responseDisplay: {e}")
            
        left_layout.addWidget(self.response_display)

        # --- ★★★ 状態表示ラベルをレイアウトに追加 ★★★ ---
        left_layout.addWidget(self.status_label) # response_display の下に配置
        # --- ★★★ ---------------------------------- ★★★ ---

        # --- メッセージ入力エリアと送信ボタン ---
        input_area_with_send_button_layout = QHBoxLayout()
        self.user_input = QTextEdit()
        self.user_input.setPlaceholderText("ここにメッセージを入力...")
        self.user_input.setAcceptRichText(False) # リッチテキストは無効
        self.user_input.setFixedHeight(100) # 高さを固定
        self.user_input.installEventFilter(self) # イベントフィルターでEnterキー処理
        input_area_with_send_button_layout.addWidget(self.user_input, 1) # ユーザー入力欄がスペースを優先的に使用

        self.send_button = QPushButton("送信")
        self.send_button.clicked.connect(self.on_send_button_clicked)
        self.send_button.setFixedHeight(self.user_input.height()) # ★ 入力欄の高さに合わせる
        input_area_with_send_button_layout.addWidget(self.send_button)
        left_layout.addLayout(input_area_with_send_button_layout)
        # --- ★★★ --------------------------- ★★★ ---

        # --- フッターコントロール群 (送信履歴範囲、送信キーモード、リトライ、確認ボタン) ---
        footer_controls_layout = QHBoxLayout()

        # --- 送信履歴範囲設定スライダー --- 
        history_slider_container = QWidget()
        history_slider_layout = QHBoxLayout(history_slider_container)
        history_slider_layout.setContentsMargins(0, 5, 0, 5)
        self.history_slider_label = QLabel(f"送信履歴範囲: {self.current_history_range_for_prompt} ")
        history_slider_layout.addWidget(self.history_slider_label)
        self.history_slider = QSlider(Qt.Horizontal)
        self.history_slider.setMinimum(0)
        self.history_slider.setMaximum(100)
        self.history_slider.setValue(self.current_history_range_for_prompt)
        self.history_slider.setFixedWidth(200)
        history_slider_layout.addWidget(self.history_slider)
        self.history_slider.valueChanged.connect(self._on_history_slider_changed)
        footer_controls_layout.addWidget(history_slider_container)

        # --- 送信キーモード選択ラジオボタン --- 
        send_key_mode_group = QGroupBox() # グループボックスのタイトルは不要なので削除
        send_key_mode_layout = QHBoxLayout(send_key_mode_group)
        self.radio_send_on_enter = QRadioButton("Enterで送信 (Shift+Enterで改行)")
        self.radio_send_on_enter.setChecked(self.send_on_enter_mode)
        self.radio_send_on_enter.toggled.connect(lambda: self._update_send_key_mode(True))
        send_key_mode_layout.addWidget(self.radio_send_on_enter)
        self.radio_send_on_shift_enter = QRadioButton("Shift+Enterで送信 (Enterで改行)")
        self.radio_send_on_shift_enter.setChecked(not self.send_on_enter_mode)
        send_key_mode_layout.addWidget(self.radio_send_on_shift_enter)
        footer_controls_layout.addWidget(send_key_mode_group)

        footer_controls_layout.addStretch(1) # ボタン群を右に寄せるためのスペーサー
        footer_controls_layout.addWidget(self.retry_button) # リトライボタン
        footer_controls_layout.addWidget(self.preview_prompt_button) # 送信内容確認ボタン

        # --- ★★★ ストリーミング有効化チェックボックスを追加 ★★★ ---
        self.streaming_checkbox = QCheckBox("ストリーミング応答")
        self.streaming_checkbox.setChecked(self.enable_streaming)
        self.streaming_checkbox.setToolTip("AIの応答を逐次表示するかどうかを切り替えます。")
        self.streaming_checkbox.stateChanged.connect(self._on_streaming_checkbox_changed)
        footer_controls_layout.addWidget(self.streaming_checkbox)
        # --- ★★★ ------------------------------------------ ★★★ ---

        left_layout.addLayout(footer_controls_layout) # 新しいフッターコントロールレイアウトをメインに追加
        # --- ★★★ --------------------------------------------------------- ★★★ ---

        # --- 右側エリア (設定ボタン、サブプロンプト、データ管理) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget) # 右側全体の縦レイアウト

        # --- 1. プロジェクト管理セクション ---
        project_management_header_layout = QHBoxLayout()
        project_management_header_layout.addWidget(QLabel("<b>プロジェクト管理:</b>"))
        project_management_header_layout.addStretch() # ラベルとボタンの間を広げる
        self.new_project_button = QPushButton("新規作成")
        self.new_project_button.setToolTip("新しいプロジェクトを作成します。")
        self.new_project_button.clicked.connect(self._on_new_project_button_clicked)
        project_management_header_layout.addWidget(self.new_project_button)
        self.delete_project_button = QPushButton("削除")
        self.delete_project_button.setToolTip("現在アクティブなプロジェクトを削除します。")
        self.delete_project_button.clicked.connect(self._on_delete_project_button_clicked)
        project_management_header_layout.addWidget(self.delete_project_button)
        self.settings_button = QPushButton("設定")
        self.settings_button.setToolTip("アプリケーション全体と現在のプロジェクトの設定を行います。")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        project_management_header_layout.addWidget(self.settings_button)
        right_layout.addLayout(project_management_header_layout)

        project_combo_layout = QHBoxLayout()
        project_combo_layout.addWidget(QLabel("  選択中のプロジェクト:")) # 少しインデント
        self.project_selector_combo = QComboBox()
        self.project_selector_combo.setToolTip("アクティブなプロジェクトを切り替えます。")
        self.project_selector_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.project_selector_combo.activated[str].connect(self._on_project_selected_by_display_name)
        project_combo_layout.addWidget(self.project_selector_combo, 1)
        right_layout.addLayout(project_combo_layout)

        # --- 区切り線1 ---
        right_layout.addWidget(self._create_separator_line())

        # --- 2. サブシステムプロンプト管理セクション ---        
        subprompt_header_layout = QHBoxLayout()
        subprompt_header_layout.addWidget(QLabel("<b>サブプロンプト管理:</b>"))
        subprompt_header_layout.addStretch()
        self.add_subprompt_category_button = QPushButton("カテゴリ追加")
        self.add_subprompt_category_button.setToolTip("サブプロンプトの新しいカテゴリを作成します。")
        self.add_subprompt_category_button.clicked.connect(self.add_subprompt_category)
        subprompt_header_layout.addWidget(self.add_subprompt_category_button)
        self.add_subprompt_button = QPushButton("プロンプト追加")
        self.add_subprompt_button.setToolTip("現在のカテゴリに新しいサブプロンプトを追加します。")
        self.add_subprompt_button.clicked.connect(lambda: self.add_or_edit_subprompt())
        subprompt_header_layout.addWidget(self.add_subprompt_button)
        right_layout.addLayout(subprompt_header_layout)

        self.subprompt_tab_widget = QTabWidget()
        self.subprompt_tab_widget.currentChanged.connect(self._on_subprompt_tab_changed)
        right_layout.addWidget(self.subprompt_tab_widget) # サブプロンプトタブを直接追加

        # --- 区切り線2 ---
        right_layout.addWidget(self._create_separator_line())

        # --- 3. アイテム管理セクション ---
        item_management_header_layout = QHBoxLayout()
        item_management_header_layout.addWidget(QLabel("<b>データ管理:</b>"))
        item_management_header_layout.addStretch()
        # DataManagementWidget 内部のボタンをこちらに移動（ただし、シグナル処理は DataManagementWidget に委譲する形を維持）
        self.data_category_add_button = QPushButton("カテゴリ追加")
        self.data_category_add_button.setToolTip("新しいデータカテゴリを作成します。")
        self.data_category_add_button.clicked.connect(
            lambda: self.data_management_widget.addCategoryRequested.emit() # DataWidgetのシグナルを発行
        )
        item_management_header_layout.addWidget(self.data_category_add_button)

        self.data_item_add_button = QPushButton("データの追加")
        self.data_item_add_button.setToolTip("現在のカテゴリに新しいデータを追加します。")
        self.data_item_add_button.clicked.connect(
            lambda: self.data_management_widget._request_add_item() # DataWidgetのメソッドを直接呼ぶかシグナル
        )
        item_management_header_layout.addWidget(self.data_item_add_button)

        self.data_item_delete_checked_button = QPushButton("チェック削除") # 名前を短縮
        self.data_item_delete_checked_button.setToolTip("現在のカテゴリでチェックされているデータを全て削除します。")
        self.data_item_delete_checked_button.clicked.connect(
            lambda: self.data_management_widget.delete_checked_items() # DataWidgetのメソッドを直接呼ぶ
        )
        item_management_header_layout.addWidget(self.data_item_delete_checked_button)
        right_layout.addLayout(item_management_header_layout)

        # --- ★★★ アイテム履歴数設定スライダーを追加 (アイテム管理セクション内) ★★★ ---
        item_history_slider_widget = QWidget() # ラベルとスライダーをまとめる
        item_history_slider_layout = QHBoxLayout(item_history_slider_widget)
        item_history_slider_layout.setContentsMargins(0, 2, 0, 2) # 少しマージン調整

        self.item_history_slider_label = QLabel(f"各データの履歴送信数: {self.item_history_length_for_prompt} ")
        item_history_slider_layout.addWidget(self.item_history_slider_label)

        self.item_history_slider = QSlider(Qt.Horizontal)
        self.item_history_slider.setMinimum(0)  # 0件 (履歴を含めない)
        self.item_history_slider.setMaximum(30) # 最大30件 (アイテム履歴なのでチャット履歴ほど多くはしない想定)
        self.item_history_slider.setValue(self.item_history_length_for_prompt)
        self.item_history_slider.setFixedWidth(180) # 幅を少し小さめに
        item_history_slider_layout.addWidget(self.item_history_slider)
        item_history_slider_layout.addStretch()

        self.item_history_slider.valueChanged.connect(self._on_item_history_slider_changed)
        
        right_layout.addWidget(item_history_slider_widget) # アイテム管理セクションのヘッダーの下に追加
        # --- ★★★ ------------------------------------------------------- ★★★ ---

        self.data_management_widget = DataManagementWidget(
            project_dir_name=self.current_project_dir_name,
            parent=self
        )
        # DataManagementWidget 内部のボタンレイアウトは非表示にする必要がある
        self.data_management_widget.add_category_button.setVisible(False) # DataWidget内のボタンを非表示
        self.data_management_widget.add_item_button.setVisible(False)
        self.data_management_widget.delete_checked_items_button.setVisible(False)
        
        self.data_management_widget.addCategoryRequested.connect(self._handle_add_data_category_request)
        self.data_management_widget.addItemRequested.connect(self._handle_add_data_item_request)
        right_layout.addWidget(self.data_management_widget) # アイテム管理ウィジェット本体を追加

        # スプリッターは使わない構成に変更
        # right_splitter = QSplitter(Qt.Vertical)
        # ...
        # right_layout.addWidget(right_splitter)


        # --- クイックセット管理セクション ---
        quick_set_groupbox = QGroupBox("クイックセット")
        quick_set_main_layout = QVBoxLayout(quick_set_groupbox)
        quick_set_main_layout.setSpacing(0) # ★ スロット間の垂直スペーシングを詰める

        for i in range(self.num_quick_set_slots):
            slot_widget = QWidget()
            slot_layout = QHBoxLayout(slot_widget)
            slot_layout.setContentsMargins(0, 0, 0, 0) # ← レイアウトのマージンよりスペーシングで調整
            slot_layout.setSpacing(1) # ★ ボタン間の水平スペーシングを詰める

            # 1. セット名ラベル
            name_label = QLabel(f"{i+1}:") # ★ ラベルも短縮
            name_label.setMinimumWidth(80)  # ★ 幅を少し詰める
            name_label.setToolTip("ここに保存されたクイックセット名が表示されます。")
            slot_layout.addWidget(name_label)
            self.quick_set_name_labels.append(name_label)

            # --- ★★★ ボタンのラベル名と幅を変更 ★★★ ---
            button_width = 30 # ★ ボタンの共通幅

            # 2. 「セット」ボタン → 「読」 (読み込み)
            apply_button = QPushButton("読") # ★ ラベル変更
            apply_button.setToolTip("このクイックセットの内容を入力欄と選択状態に反映します (送信はしません)。")
            apply_button.setProperty("slot_index", i)
            apply_button.clicked.connect(self._on_quick_set_apply_clicked)
            apply_button.setFixedWidth(button_width) # ★ 幅設定
            slot_layout.addWidget(apply_button)
            self.quick_set_apply_buttons.append(apply_button)

            # 3. 「送信」ボタン → 「送」
            send_button = QPushButton("送") # ★ ラベル変更
            send_button.setToolTip("このクイックセットの内容を反映し、AIに送信します。")
            send_button.setProperty("slot_index", i)
            send_button.clicked.connect(self._on_quick_set_send_clicked)
            send_button.setFixedWidth(button_width) # ★ 幅設定
            slot_layout.addWidget(send_button)
            self.quick_set_send_buttons.append(send_button)

            # 4. 「保存」ボタン → 「保」
            save_button = QPushButton("保") # ★ ラベル変更
            save_button.setToolTip("現在の入力内容と選択状態で、このスロットにクイックセットを保存（上書き）します。")
            save_button.setProperty("slot_index", i)
            save_button.clicked.connect(self._on_quick_set_save_clicked)
            save_button.setFixedWidth(button_width) # ★ 幅設定
            slot_layout.addWidget(save_button)
            self.quick_set_save_buttons.append(save_button)
            
            # 5. 「クリア」ボタン → 「消」
            clear_button = QPushButton("消") # ★ ラベル変更
            clear_button.setToolTip("このスロットのクイックセットを削除します。")
            clear_button.setProperty("slot_index", i)
            clear_button.clicked.connect(self._on_quick_set_clear_clicked)
            clear_button.setFixedWidth(button_width) # ★ 幅設定
            slot_layout.addWidget(clear_button)
            self.quick_set_clear_buttons.append(clear_button)
            # --- ★★★ ------------------------------------ ★★★ ---

            # slot_layout.addStretch() # 右端の余白は、グループボックス全体のサイズで調整されるので不要かも
            quick_set_main_layout.addWidget(slot_widget)
        
        # quick_set_main_layout.addStretch() # スロット間の余白はsetSpacingで調整
        right_layout.addWidget(quick_set_groupbox)
        # --- ★★★ ------------------------------------ ★★★ ---

        # ウィジェット間の伸縮性を調整
        right_layout.setStretchFactor(self.subprompt_tab_widget, 2) # サブプロンプトタブがある程度広がる
        right_layout.setStretchFactor(self.data_management_widget, 3) # データ管理エリアがより広がる
        # ----------------------------------------------------



        # 左右画面の比率設定
        main_layout.addWidget(left_widget, 7)
        main_layout.addWidget(right_widget, 3)
        right_widget.setMaximumWidth(350)

        # UI初期化後にプロジェクトコンボボックスを初期化・設定
        self._populate_project_selector()
        self._load_current_project_data()
        self._load_quick_sets() # ★★★ ここでクイックセットを読み込む ★★★

    def _create_separator_line(self) -> QFrame:
        """設定セクション間の区切り線を作成して返します。"""
        # このメソッドは SettingsDialog から MainWindow に移動しても良い
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line


    # --- プロジェクト選択関連メソッド ---
    def _populate_project_selector(self):
        """プロジェクト選択用コンボボックスに、利用可能なプロジェクトの一覧を設定します。

        `data/` ディレクトリをスキャンし、各プロジェクトの表示名とディレクトリ名を
        コンボボックスに登録します。現在アクティブなプロジェクトが選択された状態にします。
        """
        self.project_selector_combo.blockSignals(True) # 更新中のシグナル発行を抑制
        self.project_selector_combo.clear()
        self._projects_list_for_combo.clear()

        project_dir_names = list_project_dir_names()
        print(f"  Populating project selector. Found project dirs: {project_dir_names}")

        current_project_found_in_list = False
        for dir_name in project_dir_names:
            settings = load_project_settings(dir_name) # 表示名を取得するため設定をロード
            display_name = dir_name # フォールバック
            if settings and settings.get("project_display_name"):
                display_name = settings.get("project_display_name")
            
            self._projects_list_for_combo.append((display_name, dir_name))
            self.project_selector_combo.addItem(display_name) # コンボボックスには表示名を追加
            if dir_name == self.current_project_dir_name:
                self.project_selector_combo.setCurrentText(display_name)
                current_project_found_in_list = True
                print(f"    Set current project in combo: '{display_name}' (dir: '{dir_name}')")

        if not current_project_found_in_list and project_dir_names:
            # 現在のプロジェクトがリストにないが、他のプロジェクトはある場合
            # (例: config.jsonのactive_projectが不正だった場合など)
            # リストの最初のプロジェクトをアクティブにする
            print(f"  Warning: Current project '{self.current_project_dir_name}' not in valid list. Selecting first available.")
            if self._projects_list_for_combo:
                first_proj_display_name, first_proj_dir_name = self._projects_list_for_combo[0]
                self.project_selector_combo.setCurrentText(first_proj_display_name)
                # ここで実際にプロジェクトを切り替える処理を呼ぶ（_on_project_selected_by_display_name を直接呼ぶか、共通処理を切り出す）
                self._switch_project(first_proj_dir_name) # プロジェクト切り替え実行

        elif not project_dir_names: self.project_selector_combo.addItem("(プロジェクトがありません)"); self.project_selector_combo.setEnabled(False); self.delete_project_button.setEnabled(False) # ★ 削除ボタンも無効化
        else: self.delete_project_button.setEnabled(True) # プロジェクトがあれば削除ボタン有効化

        self.project_selector_combo.blockSignals(False) # シグナル発行を再開

    def _on_project_selected_by_display_name(self, selected_display_name: str):
        """プロジェクト選択コンボボックスで表示名によってプロジェクトが選択された際のスロット。

        選択された表示名に対応するディレクトリ名を見つけ、プロジェクトを切り替えます。

        Args:
            selected_display_name (str): コンボボックスで選択されたプロジェクトの表示名。
        """
        print(f"--- MainWindow: Project selected by display name: '{selected_display_name}' ---")
        selected_dir_name = None
        for display_name, dir_name in self._projects_list_for_combo:
            if display_name == selected_display_name:
                selected_dir_name = dir_name
                break
        
        if selected_dir_name and selected_dir_name != self.current_project_dir_name:
            self._switch_project(selected_dir_name)
        elif not selected_dir_name:
            print(f"  Error: Could not find directory name for display name '{selected_display_name}'.")
            # 念のためコンボボックスを再描画
            self._populate_project_selector()


    def _switch_project(self, new_project_dir_name: str):
        """指定されたディレクトリ名のプロジェクトに実際に切り替える内部メソッド。

        関連する設定の更新、データの再読み込み、UIの更新を行います。
        Chat Handler も新しいプロジェクト設定で再初期化し、新しいプロジェクトの履歴をロード・表示します。
        プロジェクト切り替え前に現在のチェック状態を保存します。

        Args:
            new_project_dir_name (str): 切り替え先のプロジェクトのディレクトリ名。
        """
        print(f"--- MainWindow: Switching project to '{new_project_dir_name}' ---")
        if self.current_project_dir_name == new_project_dir_name: # 同じプロジェクトなら何もしない
            print(f"  Already in project '{new_project_dir_name}'. No switch needed.")
            return

        # --- ★★★ 現在のプロジェクトの履歴とチェック状態を保存 ★★★ ---
        if self.chat_handler and self.chat_handler.project_dir_name == self.current_project_dir_name:
            self.chat_handler.save_current_history_on_exit() # 明示的に保存
        self._save_checked_states_to_project_settings() # ★ チェック状態を保存
        # --- ★★★ --------------------------------------------- ★★★ ---
            
        old_project_dir_name = self.current_project_dir_name # 保存後に更新
        self.current_project_dir_name = new_project_dir_name
        
        # グローバル設定のアクティブプロジェクトを更新・保存
        self.global_config["active_project"] = self.current_project_dir_name
        if not save_global_config(self.global_config):
            QMessageBox.warning(self, "保存エラー", "アクティブプロジェクトの変更の保存に失敗しました。")
            self.current_project_dir_name = old_project_dir_name # 元に戻す
            # Chat Handler も元に戻す必要があるか？現状はロード処理に任せる
            return

        self._load_current_project_data() 

        # クイックセットをロード
        self._load_quick_sets() 
        
        # --- ★★★ Chat Handler を新しいプロジェクトで再初期化 (新しい履歴がロードされる) ★★★ ---
        new_model = self.current_project_settings.get("model", self.global_config.get("default_model"))
        new_system_prompt = self.current_project_settings.get("main_system_prompt", "")
        
        # GeminiChatHandler の update_settings_and_restart_chat を使うか、
        # _initialize_chat_handler を直接呼び出す。
        # プロジェクトが変わるので、履歴は完全に新しいものになるべき。
        if self.chat_handler:
            # --- ★★★ update_settings_and_restart_chat を使う形に調整が必要 ★★★ ---
            # update_settings_and_restart_chat にも max_history_pairs を渡すように GeminiChatHandler を修正するか、
            # ここで start_new_chat_session を呼ぶ形にする。
            # 今回は、_initialize_chat_handler を呼ぶのが一貫性がある。
            # _initialize_chat_handler が内部でスライダーの値を参照して max_history_pairs を設定する。
            self._initialize_chat_handler( # これで新しいプロジェクトの履歴がロードされ、スライダー設定も適用される
                model_name=new_model,
                project_dir_name=new_project_dir_name,
                system_instruction=new_system_prompt
                )
            print(f"  Chat handler re-initialized for new project '{new_project_dir_name}'. History (with range) loaded/cleared.")
        else: 
            self._initialize_chat_handler(model_name=new_model, project_dir_name=new_project_dir_name, system_instruction=new_system_prompt)
        
        # --- ★★★ プロジェクト切り替え時に履歴を画面に再表示 ★★★ ---
        if self.chat_handler and is_configured():
            self._redisplay_chat_history()
        # --- ★★★ --------------------------------------------- ★★★ ---
            
        # コンボボックスの表示更新など
        current_display_name_in_combo = ""
        for disp_name, dir_name_map in self._projects_list_for_combo:
            if dir_name_map == self.current_project_dir_name:
                current_display_name_in_combo = disp_name
                break
        if self.project_selector_combo.currentText() != current_display_name_in_combo and current_display_name_in_combo:
            self.project_selector_combo.blockSignals(True)
            self.project_selector_combo.setCurrentText(current_display_name_in_combo)
            self.project_selector_combo.blockSignals(False)

        print(f"--- MainWindow: Project switched successfully to '{new_project_dir_name}' ---")
        self.update_status_label() # ★★★ 追加: プロジェクト切り替え時にステータス更新 ★★★


    # --- プロジェクト作成・削除関連メソッド ---
    def _on_new_project_button_clicked(self):
        """「新規プロジェクト作成」ボタンがクリックされたときの処理。
        プロジェクト名入力ダイアログを表示し、プロジェクトを作成します。
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("新規プロジェクト作成")
        layout = QVBoxLayout(dialog)

        # プロジェクト表示名入力
        layout.addWidget(QLabel("プロジェクト表示名:"))
        display_name_edit = QLineEdit(dialog)
        display_name_edit.setPlaceholderText("例: 龍の洞窟探検")
        layout.addWidget(display_name_edit)

        # プロジェクトディレクトリ名入力
        layout.addWidget(QLabel("プロジェクトディレクトリ名 (半角英数字とアンダースコアのみ):"))
        dir_name_edit = QLineEdit(dialog)
        dir_name_edit.setPlaceholderText("例: dragon_cave_expedition")
        layout.addWidget(dir_name_edit)

        # ディレクトリ名に関する注意書き
        dir_name_info_label = QLabel("<small><i>ディレクトリ名はファイルシステム上で使用されます。<br>一度作成すると変更できませんのでご注意ください。</i></small>")
        dir_name_info_label.setWordWrap(True)
        layout.addWidget(dir_name_info_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        
        def try_accept():
            display_name = display_name_edit.text().strip()
            dir_name = dir_name_edit.text().strip()
            if self._validate_and_create_project(display_name, dir_name):
                dialog.accept() # 検証成功ならダイアログを閉じる
            # 検証失敗時は _validate_and_create_project 内で QMessageBox が表示される

        button_box.accepted.connect(try_accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        dialog.setLayout(layout)
        dialog.setMinimumWidth(350)

        # ダイアログ実行は try_accept で閉じるので、ここでは exec_ の結果は使わない
        dialog.exec_()


    def _validate_and_create_project(self, display_name: str, dir_name: str) -> bool:
        """入力されたプロジェクト情報を検証し、問題なければプロジェクトを作成します。

        Args:
            display_name (str): 新しいプロジェクトの表示名。
            dir_name (str): 新しいプロジェクトのディレクトリ名。

        Returns:
            bool: プロジェクトの作成と初期化が成功した場合は True、
                  検証失敗または作成失敗の場合は False。
        """
        if not display_name:
            QMessageBox.warning(None, "入力エラー", "プロジェクト表示名を入力してください。") # Noneで親なしダイアログ
            return False
        if not dir_name:
            QMessageBox.warning(None, "入力エラー", "プロジェクトディレクトリ名を入力してください。")
            return False

        # ディレクトリ名の検証 (半角英数字とアンダースコアのみ)
        if not re.match(r"^[a-zA-Z0-9_]+$", dir_name):
            QMessageBox.warning(None, "入力エラー",
                                "プロジェクトディレクトリ名は半角英数字とアンダースコアのみ使用できます。")
            return False

        # ディレクトリ名の重複チェック
        project_path = get_project_dir_path(dir_name)
        if os.path.exists(project_path):
            QMessageBox.warning(None, "作成エラー",
                                f"ディレクトリ名 '{dir_name}' は既に使用されています。\n別の名前を指定してください。")
            return False

        print(f"--- MainWindow: Creating new project. Display: '{display_name}', Directory: '{dir_name}' ---")

        # 1. プロジェクト設定ファイルを作成 (config_manager)
        new_project_settings = DEFAULT_PROJECT_SETTINGS.copy()
        new_project_settings["project_display_name"] = display_name
        # 新規プロジェクトのモデルはグローバル設定の default_model を使用
        new_project_settings["model"] = self.global_config.get("default_model",
                                                               DEFAULT_PROJECT_SETTINGS["model"])
        if not save_project_settings(dir_name, new_project_settings):
            QMessageBox.critical(None, "作成エラー", f"プロジェクト設定ファイル ({dir_name}/{display_name}) の作成に失敗しました。")
            return False
        print(f"  Created project settings for '{dir_name}'.")

        # 2. サブプロンプトファイルを作成 (subprompt_manager) - 空のデータで
        if not save_subprompts(dir_name, DEFAULT_SUBPROMPTS_DATA.copy()):
            QMessageBox.warning(None, "作成警告", f"空のサブプロンプトファイル ({dir_name}/subprompts.json) の作成に失敗しました。")
            # 失敗してもプロジェクト作成自体は続行する (致命的ではないため)
        else:
            print(f"  Created empty subprompts file for '{dir_name}'.")

        # 3. gamedataディレクトリと、必要ならデフォルトカテゴリファイルを作成 (data_manager)
        gamedata_path = get_project_gamedata_path(dir_name)
        try:
            os.makedirs(gamedata_path, exist_ok=True)
            print(f"  Created gamedata directory for '{dir_name}'.")
            # オプション: デフォルトで「未分類」カテゴリなどを作成する
            if not create_category(dir_name, "キャラクター"): # 例として「キャラクター」
                 print(f"  Warning: Failed to create default category 'キャラクター' for new project '{dir_name}'.")
        except Exception as e:
            QMessageBox.warning(None, "作成警告", f"ゲームデータディレクトリ ({gamedata_path}) の作成に失敗しました: {e}")
            # これも致命的ではないとして続行

        QMessageBox.information(None, "作成完了", f"プロジェクト「{display_name}」({dir_name}) を作成しました。")
        self.project_selector_combo.setEnabled(True) # ★ プロジェクトが作成されたらコンボボックスを有効化
        self.delete_project_button.setEnabled(True) # ★ 削除ボタンも有効化
        self._populate_project_selector(); self._switch_project(dir_name)
        return True
        

    def _on_delete_project_button_clicked(self):
        """「プロジェクト削除」ボタンがクリックされたときの処理。
        現在アクティブなプロジェクトを削除します。
        """
        if not self.current_project_dir_name or self.current_project_dir_name == "(プロジェクトがありません)": # 特殊なケース
            QMessageBox.information(self, "削除不可", "削除するプロジェクトが選択されていません。")
            return

        project_display_name = self.current_project_settings.get("project_display_name", self.current_project_dir_name)
        reply = QMessageBox.question(self, "プロジェクト削除確認",
                                   f"本当にプロジェクト「{project_display_name}」({self.current_project_dir_name}) を削除しますか？\n"
                                   "この操作は元に戻せません。プロジェクト内の全てのデータが完全に削除されます。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            print(f"--- MainWindow: Deleting project '{self.current_project_dir_name}' ---")
            dir_name_to_delete = self.current_project_dir_name
            
            # 次にアクティブにするプロジェクトを決定 (削除するプロジェクト以外で最初に見つかったもの)
            next_active_project_dir_name = None
            for _, dir_name_iter in self._projects_list_for_combo:
                if dir_name_iter != dir_name_to_delete:
                    next_active_project_dir_name = dir_name_iter
                    break
            
            if delete_project_directory(dir_name_to_delete):
                QMessageBox.information(self, "削除完了", f"プロジェクト「{project_display_name}」を削除しました。")
                
                # プロジェクトリストとUIを更新
                self._populate_project_selector() # コンボボックス再描画
                
                if next_active_project_dir_name:
                    print(f"  Switching to next available project: '{next_active_project_dir_name}'")
                    self._switch_project(next_active_project_dir_name)
                elif not self._projects_list_for_combo: # プロジェクトが一つもなくなった場合
                    print("  No projects remaining. Clearing UI.")
                    self.current_project_dir_name = "" # アクティブプロジェクト名をクリア
                    self.current_project_settings = {}
                    self.subprompts = {}
                    self.checked_subprompts = {}
                    self.setWindowTitle("TRPG AI Tool - プロジェクトなし")
                    self.system_prompt_input_main.clear()
                    self.refresh_subprompt_tabs() # 空になるはず
                    if self.data_management_widget: self.data_management_widget.set_project("") # データウィジェットもクリア
                    self.project_selector_combo.addItem("(プロジェクトがありません)") # 再度表示
                    self.project_selector_combo.setEnabled(False)
                    self.delete_project_button.setEnabled(False) # 削除ボタンも無効化
                    self.update_status_label() # ★★★ 追加: プロジェクトなしの時にステータス更新 ★★★
                # else: next_active_project_dir_name が None で _projects_list_for_combo が空でないケースは
                # _populate_project_selector 内で処理されるはず

            else:
                QMessageBox.critical(self, "削除エラー", f"プロジェクト「{project_display_name}」の削除に失敗しました。")

    def configure_gemini_and_chat_handler(self):
        """Gemini APIクライアントを設定し、Chat Handlerも現在のプロジェクト設定で初期化または更新します。
        APIキー設定時、またはモデル名・システム指示が変更された場合にハンドラを更新（履歴は維持）。
        """
        api_key_from_os = get_os_api_key()
        config_success = False
        if api_key_from_os:
            success, message = configure_gemini_api(api_key_from_os) # gemini_handlerのグローバル関数
            if success:
                print(f"Gemini API設定完了。")
                config_success = True
            else:
                QMessageBox.warning(self, "API設定エラー", f"Gemini APIクライアントの設定に失敗しました:\n{message}")
        else:
            QMessageBox.information(self, "APIキー未設定",
                                    "Gemini APIキーがOSの資格情報に保存されていません。\n"
                                    "「設定」メニューからAPIキーを保存してください。")
        self.update_status_label() # ★★★ configure_gemini_api の結果に関わらずステータス更新 ★★★
        
        if config_success:
            # --- ★★★ API設定が成功した場合にハンドラを初期化または更新 ★★★ ---
            model_to_use = self.current_project_settings.get("model", self.global_config.get("default_model", "gemini-1.5-flash"))
            system_prompt = self.current_project_settings.get("main_system_prompt", "")

            if self.chat_handler is None:
                # 初めての初期化 (アプリケーション起動時など)
                print("MainWindow: API configured. Initializing chat handler for the first time.")
                self._initialize_chat_handler( # ★ ここで初期化
                    model_name=model_to_use,
                    project_dir_name=self.current_project_dir_name, # ★ プロジェクト名
                    system_instruction=system_prompt
                )
            else:
                # 既にハンドラが存在する場合 (設定ダイアログからの呼び出しなど)
                current_handler_model = self.chat_handler.model_name
                current_handler_system_instruction = self.chat_handler._system_instruction_text
                current_handler_project = self.chat_handler.project_dir_name

                if current_handler_model != model_to_use or \
                   current_handler_system_instruction != system_prompt or \
                   current_handler_project != self.current_project_dir_name: # プロジェクトも比較対象に加える
                    print("MainWindow: Settings (model, system prompt, or project) changed. Updating chat handler.")
                    self.chat_handler.update_settings_and_restart_chat(
                        new_model_name=model_to_use,
                        new_system_instruction=system_prompt,
                        new_project_dir_name=self.current_project_dir_name, # プロジェクト名も渡す
                        max_history_pairs_for_restart=self.current_history_range_for_prompt
                    )
                # else: 何も変更がなければ何もしない
            # --- ★★★ ---------------------------------------------------- ★★★ ---
        elif self.chat_handler: # API設定失敗したがハンドラは存在する場合
             self.chat_handler._model = None # モデルを無効化
             self.chat_handler._chat_session = None
             print("MainWindow: API configuration failed. Chat handler model invalidated.")

    def open_settings_dialog(self):
        """設定ダイアログを開き、変更があれば適用・保存します。"""
        if self.is_streaming:
            QMessageBox.information(self, "処理中", "AI応答生成中です。設定は変更できません。")
            return
        dialog = SettingsDialog(self.global_config, self.current_project_settings, self)
        if dialog.exec_():
            updated_global_config, new_project_settings = dialog.get_updated_configs() # ★ 修正: メソッド名と受け取り方
            self.global_config = updated_global_config # ★ 修正
            save_global_config(self.global_config)

            # --- ★★★ 送信キーモードをグローバル設定から読み込み ★★★ ---
            self.send_on_enter_mode = self.global_config.get("send_on_enter_mode", True)
            # ★★★ UI要素の存在チェックを追加 (init_ui完了前に呼ばれる可能性を考慮) ★★★
            if hasattr(self, 'radio_send_on_enter') and hasattr(self, 'radio_send_on_shift_enter'):
                self.radio_send_on_enter.setChecked(self.send_on_enter_mode)
                self.radio_send_on_shift_enter.setChecked(not self.send_on_enter_mode)
            # --- ★★★ ----------------------------------------------------------- ★★★ ---

            if self.current_project_settings != new_project_settings:
                self.current_project_settings = new_project_settings
                save_project_settings(self.current_project_dir_name, self.current_project_settings)
                QMessageBox.information(self, "設定保存", f"プロジェクト「{self.current_project_settings.get('project_display_name', self.current_project_dir_name)}」の設定を保存しました。")
                # チャットハンドラの設定も更新
                if self.chat_handler:
                    self.chat_handler.update_settings_and_restart_chat(
                        new_model_name=self.current_project_settings.get("model"),
                        new_system_instruction=self.current_project_settings.get("main_system_prompt"),
                        new_project_dir_name=self.current_project_dir_name, # プロジェクト名は変わらない
                        new_generation_config=self.current_project_settings.get("generation_config"), # settings_dialog で生成設定も編集できるようにする場合
                        max_history_pairs_for_restart=self.current_history_range_for_prompt
                    )
                    # システムプロンプトのUIも更新
                    self.system_prompt_input_main.setPlainText(self.current_project_settings.get("main_system_prompt", ""))
                    self._redisplay_chat_history() # モデルやシステム指示が変わった可能性があるので履歴再表示が良いか検討
            
            # APIキーの再設定もここで行う
            self.configure_gemini_and_chat_handler()
            self.update_status_label()

    def on_send_button_clicked(self):
        """ユーザー入力と選択されたコンテキスト情報を元に、AIにメッセージを送信し、応答を表示します。
        送信前にAPIキーの確認とChat Handlerの初期化を行います。
        応答やエラーは response_display に追記・表示されます。
        """
        if self.is_streaming:
            QMessageBox.information(self, "処理中", "AIが応答を生成中です。")
            return

        if not is_configured():
            QMessageBox.warning(self, "APIキー未設定", "Gemini APIキーが設定されていません。設定画面でキーを登録してください。")
            return

        if not self.chat_handler:
            QMessageBox.critical(self, "エラー", "チャットハンドラが初期化されていません。アプリケーションを再起動してください。")
            return

        user_input_text = self.user_input.toPlainText().strip()
        if not user_input_text:
            QMessageBox.warning(self, "入力なし", "送信するメッセージを入力してください。")
            return

        current_timestamp = QDateTime.currentDateTime().toString(Qt.ISODate)
        self.chat_handler.add_user_message_to_history(user_input_text, timestamp=current_timestamp)
        
        self._append_message_to_display({
            'role': 'user',
            'parts': [{'text': user_input_text}],
            'timestamp': current_timestamp
        })
        # self._scroll_history_to_bottom() # _append_message_to_display に含まれる

        transient_context = self._build_transient_context_string()
        
        num_history_entries_to_take = self.current_history_range_for_prompt * 2 
        # add_user_message_to_history で追加された最新のユーザーメッセージも含めてAPIに送る
        history_for_api_call = self.chat_handler._pure_chat_history[-num_history_entries_to_take:] if num_history_entries_to_take > 0 else []
        
        effective_model = self.current_project_settings.get("model", self.chat_handler.model_name)

        self.user_input.clear() 
        self.update_status_label() 

        self._initialize_streaming_worker_and_connections(
            user_instruction=user_input_text, 
            transient_context=transient_context, 
            history_to_send=history_for_api_call, 
            max_history=None, 
            effective_model=effective_model,
            stream=self.enable_streaming # ★ ストリーミング設定を渡す
        )

    def _append_message_to_display(self, message_data: dict, model_name_override: Optional[str] = None):
        """指定されたメッセージデータをresponse_displayの末尾に追加するヘルパー。"""
        # 既存の履歴表示フォーマット関数を利用
        # is_latest_model_entry は、これがモデルからの最後の応答である場合に編集・削除リンクを制御するために使うが、
        # ユーザーメッセージの場合はFalseでよい。
        # 実際の履歴リストのインデックスではなく、表示用のtimestampを使う方が安定するかも
        html_content = self._format_history_entry_to_html(
            index=len(self.chat_handler._pure_chat_history) -1 if self.chat_handler else -1, # 最新のインデックス
            message_data=message_data,
            model_name=model_name_override if message_data.get('role') == 'model' else None,
            is_latest_model_entry= (message_data.get('role') == 'model') # ストリーミング完了時にも呼ばれる想定
        )
        self.response_display.append(html_content)
        self._scroll_history_to_bottom_if_at_bottom()


    def _on_retry_button_clicked(self):
        """リトライボタンがクリックされたときの処理。"""
        if self.is_streaming:
            QMessageBox.information(self, "処理中", "AIが応答を生成中です。")
            return

        if not self.chat_handler:
            QMessageBox.warning(self, "エラー", "チャットハンドラが利用できません。")
            return

        last_user_message_text = self.chat_handler.delete_last_exchange_and_get_user_message()

        if last_user_message_text is None:
            QMessageBox.information(self, "リトライ不可", "リトライ可能な直前のメッセージ交換が見つかりません。")
            self._update_retry_button_state()
            return

        self._redisplay_chat_history() # 履歴から削除された状態をUIに反映
        self.update_status_label()
        QMessageBox.information(self, "リトライ実行", f"直前のAI応答を削除し、メッセージ「{last_user_message_text[:50]}...」を再送信します。")

        transient_context = self._build_transient_context_string()
        
        # APIに送る履歴 (delete_last_exchange_and_get_user_message 実行後の履歴)
        num_history_entries_to_take = self.current_history_range_for_prompt * 2
        history_for_api_call_before_re_add = self.chat_handler._pure_chat_history[-num_history_entries_to_take:] if num_history_entries_to_take > 0 else []
        
        effective_model = self.current_project_settings.get("model", self.chat_handler.model_name)
        
        # 削除されたユーザーメッセージを再度、現在のタイムスタンプで履歴とUIに追加
        current_timestamp = QDateTime.currentDateTime().toString(Qt.ISODate)
        self.chat_handler.add_user_message_to_history(last_user_message_text, timestamp=current_timestamp)
        self._append_message_to_display({
            'role': 'user',
            'parts': [{'text': last_user_message_text}],
            'timestamp': current_timestamp
        })
        # self._scroll_history_to_bottom() # _append_message_to_display に含まれる

        self._initialize_streaming_worker_and_connections(
            user_instruction=last_user_message_text, 
            transient_context=transient_context, 
            history_to_send=history_for_api_call_before_re_add, # ユーザーメッセージ再追加前の履歴を送る
            max_history=None, 
            effective_model=effective_model,
            stream=self.enable_streaming # ★ ストリーミング設定を渡す
        )

    # 新規: 会話履歴を response_display に再表示するメソッド
    def _redisplay_chat_history(self):
        """現在の GeminiChatHandler が保持する純粋な会話履歴を
        response_display エリアに整形して表示します。
        各履歴エントリは _format_history_entry_to_html を使って整形されます。
        表示前に現在の内容はクリアされます。
        """
        if not hasattr(self, 'response_display') or not self.response_display:
            print("Warning: response_display is not initialized. Skipping chat history redisplay.")
            return

        self.response_display.clear()
        if self.chat_handler:
            history = self.chat_handler.get_pure_chat_history()
            if not history:
                # self.response_display.append("<p style='color: gray;'>(まだ会話履歴はありません)</p>")
                # グローバルフォント設定を読み込み
                font_family = self.global_config.get("font_family", "MS Gothic")
                font_size = self.global_config.get("font_size", 10)
                self.response_display.append(f"<p style='font-family: {font_family}; font-size: {font_size}pt; color: gray;'>(まだ会話履歴はありません)</p>")
                return

            # 最後のモデル応答を特定するための準備
            last_model_entry_index = -1
            for i in range(len(history) - 1, -1, -1):
                if history[i]['role'] == 'model':
                    last_model_entry_index = i
                    break
            
            for i, entry_data in enumerate(history):
                # ★★★ model_name を渡すように変更 ★★★
                # プロジェクト設定から現在のモデル名を取得 (なければグローバルデフォルト)
                current_model_for_display = self.current_project_settings.get("model", self.global_config.get("default_model", "Unknown Model"))
                is_latest_model_entry = (entry_data['role'] == 'model' and i == last_model_entry_index)
                html_entry = self._format_history_entry_to_html(i, entry_data, current_model_for_display, is_latest_model_entry)
                self.response_display.append(html_entry)
        else:
            self.response_display.append("<p style='color: red;'>エラー: チャットハンドラが初期化されていません。</p>")
        self.response_display.ensureCursorVisible() # スクロールを一番下に
        # self._scroll_history_to_bottom() # こちらの方が確実かも

    # --- ★★★ 新規: 履歴エントリをHTMLに整形するヘルパー関数 ★★★ ---
    # ★★★ 引数を変更: text_content の代わりに message_dict を受け取る ★★★
    def _format_history_entry_to_html(self, index: int, message_data: dict, model_name: Optional[str] = None, is_latest_model_entry: bool = False) -> str:
        """指定された履歴エントリの情報を、編集・削除リンク付きのHTML文字列に整形します。
        スタイルは外部CSSファイルで定義されたクラスに依存します。
        AI応答の場合、トークン情報も表示します。
        フォント設定は self.global_config から読み込み、インラインスタイルとして適用します。

        Args:
            index (int): 履歴リスト内でのインデックス。
            message_data (dict): 履歴エントリの辞書データ。
                                 ('role', 'parts', オプションで 'usage' を含む)
            model_name (str, optional): AIの応答の場合、使用されたモデル名。
            is_latest_model_entry (bool): このエントリがAIの最新の応答であるかを示すフラグ。

        Returns:
            str: 整形されたHTML文字列。
        """
        from core.config_manager import DEFAULT_GLOBAL_CONFIG # デフォルト値取得のため

        role = message_data.get("role")
        text_content = ""
        if message_data.get("parts") and isinstance(message_data["parts"], list) and len(message_data["parts"]) > 0:
            part = message_data["parts"][0]
            if isinstance(part, dict) and "text" in part:
                text_content = part["text"]
            elif isinstance(part, str):
                text_content = part

        escaped_text = text_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        # --- フォント設定の取得 ---
        font_family = self.global_config.get("font_family", DEFAULT_GLOBAL_CONFIG.get("font_family", "MS Gothic"))
        font_size_pt = self.global_config.get("font_size", DEFAULT_GLOBAL_CONFIG.get("font_size", 10))
        font_line_height = self.global_config.get("font_line_height", DEFAULT_GLOBAL_CONFIG.get("font_line_height", 1.5)) # ★★★ 行間を取得 ★★★
        
        user_color = self.global_config.get("font_color_user", DEFAULT_GLOBAL_CONFIG.get("font_color_user", "#444444"))
        model_color_default = self.global_config.get("font_color_model", DEFAULT_GLOBAL_CONFIG.get("font_color_model", "rgb(0, 85, 177)"))
        model_color_latest = self.global_config.get("font_color_model_latest", DEFAULT_GLOBAL_CONFIG.get("font_color_model_latest", "rgb(0, 100, 200)"))

        # --- スタイル文字列の構築 ---
        base_font_style = f"font-family: '{font_family}'; font-size: {font_size_pt}pt;"
        entry_specific_color_style = ""
        comment_container_style = f"line-height: {font_line_height};" # ★★★ コメントコンテナのスタイル ★★★
        name_container_style = "text-decoration: none !important;" # ★★★ アンダーライン強制削除 ★★★

        edit_link = f'<a class="action-link" href="edit:{index}:{role}">[編集]</a>'
        delete_link = f'<a class="action-link" href="delete:{index}:{role}">[削除]</a>'
        actions_span = f'{edit_link} {delete_link}'

        entry_class = "history-entry "
        display_role_name = ""
        token_info_html = ""

        if role == "user":
            entry_class += "user-entry"
            display_role_name = f"あなた ({index + 1})"
            entry_specific_color_style = f"color: {user_color};"
        elif role == "model":
            entry_class += "model-entry"
            model_name_display = model_name if model_name else (self.chat_handler.model_name if self.chat_handler else "AI")
            display_role_name = f"Gemini ({model_name_display}, {index + 1})"
            current_model_color = model_color_latest if is_latest_model_entry else model_color_default
            entry_specific_color_style = f"color: {current_model_color};"
            
            usage_data = message_data.get("usage")
            if isinstance(usage_data, dict):
                prompt_tokens = usage_data.get("prompt_token_count", 0)
                candidates_tokens = usage_data.get("candidates_token_count", 0)
                total_tokens = usage_data.get("total_token_count", 0)

                token_parts = []
                if prompt_tokens is not None: # 0の場合も表示
                    token_parts.append(f"In: {prompt_tokens}")
                if candidates_tokens is not None:
                    token_parts.append(f"Out: {candidates_tokens}")
                if total_tokens is not None:
                    token_parts.append(f"Total: {total_tokens}")
                
                if token_parts:
                    token_info_html = f'<span class="token-info">({", ".join(token_parts)} トークン)</span>'
        else:
            display_role_name = f"{role or '不明'} ({index + 1})"
            entry_specific_color_style = f"color: {user_color};" # 不明な場合はユーザーカラーなど

        # --- HTML出力の構成 ---
        
        html_output = f'<div class="{entry_class}" style="{base_font_style} {entry_specific_color_style}">'
        html_output += f'<div class="name-container" style="{name_container_style}">{display_role_name} {token_info_html}</div>'
        html_output += f'<div class="comment-container" style="{comment_container_style}">{escaped_text}</div>'
        html_output += f'<div class="actions-container">{actions_span}</div>'
        html_output += '</div>'
        html_output += '<div class="separator">――――――――――――――――――――――――――――――――――――――――――――――――――――――</div>'
        
        return html_output
    # --- ★★★ ---------------------------------------------------- ★★★ ---

    # --- ★★★ 新規: 履歴リンククリック処理メソッド ★★★ ---
    def _handle_history_link_clicked(self, url: QUrl):
        """応答履歴内の編集・削除リンクがクリックされたときに呼び出されます。
        URLのカスタムスキーマをパースし、対応するアクションを実行します。
        今後、編集・削除以外のリンク処理にも利用することを想定しています。

        Args:
            url (QUrl): クリックされたリンクのURL。
                        カスタムスキーマ "action:index:role" を期待します。
                        例: "edit:0:user", "delete:1:model"
        """
        if self.is_streaming: # ストリーミング中は履歴操作を無視
            QMessageBox.information(self, "処理中", "AIが応答を生成中です。完了するまでお待ちください。")
            return

        if not self.chat_handler: return

        url_str = url.toString()
        print(f"History link clicked: {url_str}")

        try:
            parts = url_str.split(':')
            if len(parts) != 3:
                print(f"  Invalid link format: {url_str}")
                return

            action = parts[0]
            history_index = int(parts[1])
            role_clicked = parts[2] # 'user' or 'model'

            current_history = self.chat_handler.get_pure_chat_history()
            if not (0 <= history_index < len(current_history)):
                print(f"  Invalid history index: {history_index}")
                return
            
            target_entry = current_history[history_index]
            # ロールの整合性も確認 (必須ではないが、念のため)
            if target_entry.get("role") != role_clicked:
                print(f"  Warning: Role mismatch. Expected '{target_entry.get('role')}', clicked on link for '{role_clicked}'. Proceeding with index {history_index}.")

            original_text = ""
            if target_entry.get("parts") and target_entry["parts"]:
                original_text = target_entry["parts"][0].get("text", "")

            if action == "edit":
                new_text, ok = QInputDialog.getMultiLineText(
                    self,
                    f"履歴編集 ({'あなた' if role_clicked == 'user' else 'Gemini'} - {history_index + 1})",
                    "内容を編集してください:",
                    original_text
                )
                if ok and new_text.strip() != original_text.strip():
                    # _pure_chat_history を直接変更
                    # GeminiChatHandler に専用の編集メソッドを作るのがよりクリーンかも
                    self.chat_handler._pure_chat_history[history_index]['parts'][0]['text'] = new_text.strip()
                    self.chat_handler._save_history_to_file() # 保存
                    self._redisplay_chat_history() # 再表示
                    print(f"  History entry {history_index} ({role_clicked}) edited.")
                elif ok:
                    QMessageBox.information(self, "変更なし", "履歴内容は変更されませんでした。")

            elif action == "delete":
                reply = QMessageBox.question(
                    self,
                    "履歴削除確認",
                    f"履歴エントリ ({history_index + 1} - {'あなた' if role_clicked == 'user' else 'Gemini'}) を本当に削除しますか？\n\n「{original_text[:50] + '...' if len(original_text) > 50 else original_text}」\n\nこの操作は元に戻せません。",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    del self.chat_handler._pure_chat_history[history_index]
                    self.chat_handler._save_history_to_file() # 保存
                    self._redisplay_chat_history() # 再表示
                    print(f"  History entry {history_index} ({role_clicked}) deleted.")
            else:
                print(f"  Unknown action in link: {action}")

        except ValueError: # int(parts[1]) でエラーなど
            print(f"  Error parsing link: {url_str}")
        except Exception as e:
            print(f"  Error handling history link click: {e}")
            QMessageBox.warning(self, "処理エラー", f"履歴リンクの処理中にエラーが発生しました:\\n{e}")
    # --- ★★★ ------------------------------------------- ★★★ ---


    # --- サブプロンプト管理メソッド ---
    def refresh_subprompt_tabs(self):
        """サブプロンプトタブウィジェットの内容を現在のプロジェクトデータに基づいて再構築します。"""
        current_tab_text_before_refresh = None
        current_tab_idx = self.subprompt_tab_widget.currentIndex()
        if current_tab_idx != -1:
             current_tab_text_before_refresh = self.subprompt_tab_widget.tabText(current_tab_idx)

        self.subprompt_tab_widget.clear() # 既存のタブを全て削除
        # self.subprompt_lists は廃止 (SubPromptItemWidget が直接リストに追加される)

        categories_in_subprompts = sorted(self.subprompts.keys())
        if not categories_in_subprompts: # サブプロンプトデータが空またはカテゴリがない場合
             if "一般" not in self.subprompts: # デフォルトカテゴリ "一般" がメモリ上にもなければ作成
                  self.subprompts["一般"] = {}
                  categories_in_subprompts.append("一般")
                  if save_subprompts(self.current_project_dir_name, self.subprompts): # ファイルにも保存
                       print(f"プロジェクト '{self.current_project_dir_name}' にデフォルトカテゴリ'一般'(サブプロンプト)を作成・保存しました。")

        # チェック状態辞書の整合性を取る (存在しないカテゴリのエントリを削除)
        self.checked_subprompts = {
            cat: checked_names for cat, checked_names in self.checked_subprompts.items()
            if cat in categories_in_subprompts
        }

        new_selected_tab_index = -1
        for i, category_name in enumerate(categories_in_subprompts):
            list_widget_for_category = QListWidget()
            list_widget_for_category.setObjectName(f"subpromptList_{category_name}") # デバッグ用
            
            checked_names_in_this_category = self.checked_subprompts.get(category_name, set())
            subprompt_names_in_this_category = sorted(self.subprompts.get(category_name, {}).keys())

            for sub_name in subprompt_names_in_this_category:
                is_item_checked = sub_name in checked_names_in_this_category
                item_container = QListWidgetItem(list_widget_for_category)
                widget_for_item = SubPromptItemWidget(sub_name, is_item_checked)
                # シグナル接続
                widget_for_item.checkStateChanged.connect(
                    lambda checked_state, current_cat=category_name, current_s_name=sub_name:
                        self._handle_subprompt_check_change(current_cat, current_s_name, checked_state)
                )
                widget_for_item.editRequested.connect(
                    lambda current_cat=category_name, current_s_name=sub_name:
                        self.add_or_edit_subprompt(current_cat, current_s_name)
                )
                widget_for_item.deleteRequested.connect(
                    lambda current_cat=category_name, current_s_name=sub_name:
                        self.delete_subprompt(current_cat, [current_s_name]) # 単一削除
                )
                item_container.setSizeHint(widget_for_item.sizeHint())
                list_widget_for_category.setItemWidget(item_container, widget_for_item)
            
            self.subprompt_tab_widget.addTab(list_widget_for_category, category_name)
            if category_name == current_tab_text_before_refresh:
                new_selected_tab_index = i
        
        if new_selected_tab_index != -1:
             self.subprompt_tab_widget.setCurrentIndex(new_selected_tab_index)
        elif self.subprompt_tab_widget.count() > 0: # 何も一致しなかったがタブはある場合
             self.subprompt_tab_widget.setCurrentIndex(0) # 最初のタブを選択

    def _on_subprompt_tab_changed(self, index: int):
        """サブプロンプトのカテゴリタブが変更されたときに呼び出されるスロット。(現在は未使用)

        Args:
            index (int): 新しく選択されたタブのインデックス。
        """
        # print(f"Subprompt tab changed to index: {index}")
        pass # 必要に応じて、タブ変更時の追加処理をここに記述

    def _handle_subprompt_check_change(self, category: str, name: str, is_checked: bool):
        """サブプロンプトアイテムのチェック状態が変更されたときの内部処理。

        `self.checked_subprompts` を更新します。

        Args:
            category (str): チェック状態が変更されたサブプロンプトのカテゴリ名。
            name (str): チェック状態が変更されたサブプロンプトの名前。
            is_checked (bool): 新しいチェック状態。
        """
        if category not in self.checked_subprompts:
            self.checked_subprompts[category] = set()
        if is_checked:
            self.checked_subprompts[category].add(name)
        else:
            self.checked_subprompts[category].discard(name)
        print(f"Subprompt check state: Category='{category}', Name='{name}', Checked={is_checked}")

    def add_subprompt_category(self):
        """「サブプロンプトカテゴリ追加」ボタンがクリックされたときの処理。"""
        category_name, ok = QInputDialog.getText(self, "サブプロンプト カテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name.strip():
            category_name = category_name.strip() # 前後の空白を除去
            if category_name not in self.subprompts:
                self.subprompts[category_name] = {} # メモリ上に新しいカテゴリ作成
                if save_subprompts(self.current_project_dir_name, self.subprompts):
                    self.refresh_subprompt_tabs() # UI更新
                    # 追加したタブを選択状態にする
                    for i in range(self.subprompt_tab_widget.count()):
                        if self.subprompt_tab_widget.tabText(i) == category_name:
                            self.subprompt_tab_widget.setCurrentIndex(i)
                            break
                else:
                    QMessageBox.warning(self, "保存エラー", f"カテゴリ '{category_name}' の保存に失敗しました。")
                    del self.subprompts[category_name] # 保存失敗時はメモリからも削除
            else:
                QMessageBox.warning(self, "エラー", f"カテゴリ名 '{category_name}' は既に存在します。")
        elif ok : # OK押したが名前が空
            QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")

    def add_or_edit_subprompt(self, category_to_edit: str | None = None, name_to_edit: str | None = None):
        """サブプロンプトの追加または編集ダイアログを開きます。

        引数なしで呼び出された場合は「追加」モード（現在のタブカテゴリ対象）。
        引数ありの場合は「編集」モード。

        Args:
            category_to_edit (str | None, optional): 編集対象のカテゴリ名。
                                                     Noneの場合は現在のタブのカテゴリ。
            name_to_edit (str | None, optional): 編集対象のサブプロンプト名。
                                                 Noneの場合は新規追加。
        """
        target_category = category_to_edit
        is_editing_mode = bool(name_to_edit) # name_to_edit があれば編集モード

        if not target_category: # カテゴリ指定がない場合は現在のタブから取得
            current_tab_index = self.subprompt_tab_widget.currentIndex()
            if current_tab_index == -1: # タブが選択されていない（またはタブがない）
                # デフォルトカテゴリ「一般」がなければ作成を試みる
                if "一般" not in self.subprompts: self.add_subprompt_category() # これが成功すればタブができるはず
                # 再度タブを確認
                current_tab_index = self.subprompt_tab_widget.currentIndex()
                if current_tab_index == -1: # それでもダメならエラー
                     QMessageBox.warning(self, "カテゴリ未選択", "サブプロンプトを追加/編集するカテゴリがありません。\nまず「カテゴリ追加」でカテゴリを作成してください。")
                     return
            target_category = self.subprompt_tab_widget.tabText(current_tab_index)

        initial_prompt_data = {"name": "", "prompt": "", "model": ""} # 新規作成時のデフォルト
        if is_editing_mode and target_category in self.subprompts and name_to_edit in self.subprompts[target_category]:
            initial_prompt_data = self.subprompts[target_category][name_to_edit].copy()
            initial_prompt_data["name"] = name_to_edit
        dialog = SubPromptEditDialog(initial_data=initial_prompt_data, parent=self, is_editing=is_editing_mode, current_category=target_category)
        if dialog.exec_() == QDialog.Accepted:
            new_sub_data = dialog.get_data()
            new_sub_name = new_sub_data.pop("name") # 名前はキーとして使用

            if not target_category in self.subprompts: # 万が一カテゴリが消えていたら(通常ありえない)
                self.subprompts[target_category] = {}

            # 編集時で名前が変更された場合、古い名前のデータを削除
            if is_editing_mode and name_to_edit != new_sub_name and name_to_edit in self.subprompts[target_category]:
                del self.subprompts[target_category][name_to_edit]
                # チェック状態も移行
                if target_category in self.checked_subprompts and name_to_edit in self.checked_subprompts[target_category]:
                    self.checked_subprompts[target_category].remove(name_to_edit)
                    self.checked_subprompts[target_category].add(new_sub_name) # 新しい名前でチェック

            self.subprompts[target_category][new_sub_name] = new_sub_data # 新しいデータで登録/上書き
            if save_subprompts(self.current_project_dir_name, self.subprompts):
                self.refresh_subprompt_tabs() # UI更新
            else:
                QMessageBox.warning(self, "保存エラー", "サブプロンプトの保存に失敗しました。")
                # TODO: 保存失敗時のロールバック処理 (メモリ上の変更を元に戻すなど)

    def delete_subprompt(self, category_name: str, names_to_delete: list[str]):
        """指定されたカテゴリから、指定された名前のサブプロンプトを削除します。

        Args:
            category_name (str): 削除対象サブプロンプトが含まれるカテゴリ名。
            names_to_delete (list[str]): 削除するサブプロンプトの名前のリスト。
        """
        if not category_name in self.subprompts: return # カテゴリ存在チェック

        deleted_something = False
        for name in names_to_delete:
            if name in self.subprompts[category_name]:
                del self.subprompts[category_name][name]
                # チェック状態からも削除
                if category_name in self.checked_subprompts and name in self.checked_subprompts[category_name]:
                    self.checked_subprompts[category_name].remove(name)
                deleted_something = True
        
        if deleted_something:
            if save_subprompts(self.current_project_dir_name, self.subprompts):
                self.refresh_subprompt_tabs() # UI更新
            else:
                QMessageBox.warning(self, "保存エラー", "サブプロンプトの削除内容の保存に失敗しました。")
                # TODO: 保存失敗時のロールバック処理

    # --- データ管理ウィジェット連携メソッド ---
    def _handle_add_data_category_request(self):
        """`DataManagementWidget`からのカテゴリ追加要求を処理します。"""
        category_name, ok = QInputDialog.getText(self, "データカテゴリ追加", "新しいカテゴリ名:")
        if ok and category_name.strip():
            self.data_management_widget.add_new_category_result(category_name.strip())
        elif ok :
            QMessageBox.warning(self, "入力エラー", "カテゴリ名を入力してください。")

    def _handle_add_data_item_request(self, category_from_data_widget: str):
        """`DataManagementWidget`からのアイテム追加要求を処理します。

        Args:
            category_from_data_widget (str): アイテムを追加する対象のカテゴリ名。
        """
        item_name, ok = QInputDialog.getText(self, "アイテム追加",
                                             f"カテゴリ '{category_from_data_widget}' に追加するアイテムの名前:")
        if ok and item_name.strip():
            self.data_management_widget.add_new_item_result(category_from_data_widget, item_name.strip())
        elif ok:
            QMessageBox.warning(self, "入力エラー", "アイテム名を入力してください。")


    # --- ★★★ クイックセット操作ボタンのスロットメソッド群 ★★★ ---

    def _get_sender_slot_index(self) -> Optional[int]:
        """シグナルを送信したボタンからスロットインデックスを取得します。"""
        sender = self.sender()
        if sender:
            slot_index_prop = sender.property("slot_index")
            if isinstance(slot_index_prop, int):
                return slot_index_prop
        return None

    def _save_quick_sets_to_file(self):
        """現在の self.quick_sets_data をファイルに保存します。"""
        from core.config_manager import QUICK_SETS_FILENAME, PROJECTS_BASE_DIR
        qsets_file_path = os.path.join(PROJECTS_BASE_DIR, self.current_project_dir_name, QUICK_SETS_FILENAME)
        try:
            os.makedirs(os.path.dirname(qsets_file_path), exist_ok=True)
            with open(qsets_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.quick_sets_data, f, ensure_ascii=False, indent=2)
            print(f"Quick sets saved to '{qsets_file_path}'.")
        except Exception as e:
            print(f"Error saving quick sets to '{qsets_file_path}': {e}")
            QMessageBox.warning(self, "保存エラー", f"クイックセットの保存に失敗しました:\\n{e}")

    def _on_quick_set_save_clicked(self):
        """「保存」ボタンがクリックされたときの処理。
        現在の入力内容を対応するスロットのクイックセットとして保存します。
        """
        slot_index = self._get_sender_slot_index()
        if slot_index is None: return

        slot_id = f"slot_{slot_index}"
        
        # 現在の入力内容を取得
        current_message = self.user_input.toPlainText().strip()
        
        current_checked_subprompts = []
        for category, names in self.checked_subprompts.items():
            for name in names:
                current_checked_subprompts.append(f"{category}:{name}") # カテゴリと名前を結合して保存

        current_checked_items_dict: Dict[str, List[str]] = {}
        checked_items_from_widget = self.data_management_widget.get_checked_items()
        for category, item_ids_set in checked_items_from_widget.items():
            current_checked_items_dict[category] = list(item_ids_set)

        # セット名を入力させる (既存名があればそれをデフォルトに)
        existing_set_data = self.quick_sets_data.get(slot_id)
        default_name = existing_set_data.get("name", f"クイックセット {slot_index + 1}") if isinstance(existing_set_data, dict) else f"クイックセット {slot_index + 1}"
        
        set_name, ok = QInputDialog.getText(self, "クイックセット名入力", "このクイックセットの名前を入力してください:", text=default_name)
        if not ok or not set_name.strip():
            QMessageBox.information(self, "キャンセル", "クイックセットの保存をキャンセルしました。")
            return
        
        set_name = set_name.strip()

        # クイックセットデータを作成
        new_set_data = {
            "name": set_name,
            "message_template": current_message,
            "subprompts": current_checked_subprompts, # ["Category1:SubpromptName1", "Category2:SubpromptName2"]
            "data_items": current_checked_items_dict  # {"CategoryA": ["id1", "id2"], "CategoryB": ["id3"]}
        }
        
        self.quick_sets_data[slot_id] = new_set_data
        self._save_quick_sets_to_file()
        self._update_quick_set_slots_display() # UI更新
        QMessageBox.information(self, "保存完了", f"「{set_name}」をスロット {slot_index + 1} に保存しました。")
        print(f"Quick set '{set_name}' saved to slot {slot_index + 1}.")


    def _apply_quick_set_to_ui(self, slot_id: str) -> bool:
        """指定されたスロットIDのクイックセット内容をUIに適用します。
        成功した場合は True、セットデータがない場合は False を返します。
        """
        set_data = self.quick_sets_data.get(slot_id)
        if not set_data or not isinstance(set_data, dict):
            QMessageBox.warning(self, "エラー", f"スロット {slot_id} にクイックセットデータが見つかりません。")
            return False

        print(f"Applying quick set from {slot_id}: '{set_data.get('name', '(名称未設定)')}'")

        # 1. 送信メッセージをセット
        self.user_input.setPlainText(set_data.get("message_template", ""))

        # 2. サブプロンプトのチェック状態を更新
        #    まず全てのチェックを外し、その後セット内のものだけをチェック
        self.uncheck_all_subprompts() # 修正: メソッド名を変更
        subprompts_to_check = set_data.get("subprompts", []) # ["Category1:SubpromptName1", ...]
        if subprompts_to_check:
            self.check_subprompts_by_full_names(subprompts_to_check) # 修正: メソッド名を変更

        # 3. データアイテムのチェック状態を更新
        #    まず全てのチェックを外し、その後セット内のものだけをチェック
        self.data_management_widget.uncheck_all_items() # このメソッドがDataManagementWidgetに必要
        items_to_check = set_data.get("data_items", {})
        if items_to_check and isinstance(items_to_check, dict):
            # items_to_check は {"CategoryA": ["id1", "id2"], ...} の形式
            self.data_management_widget.check_items_by_dict(items_to_check)
            # 例: for category, item_ids in items_to_check.items():
            #         for item_id in item_ids:
            #             self.data_management_widget.set_item_checked_state(category, item_id, True)
        
        QApplication.processEvents() # UIの更新を即時反映
        return True


    def _on_quick_set_apply_clicked(self):
        """「セット」ボタンがクリックされたときの処理。
        対応するスロットのクイックセット内容をUIに反映します（送信はしない）。
        """
        slot_index = self._get_sender_slot_index()
        if slot_index is None: return
        slot_id = f"slot_{slot_index}"
        
        if self._apply_quick_set_to_ui(slot_id):
            set_name = self.quick_sets_data.get(slot_id, {}).get("name", f"スロット {slot_index + 1}")
            QMessageBox.information(self, "セット完了", f"「{set_name}」の内容を適用しました。")


    def _on_quick_set_send_clicked(self):
        """「送信」ボタンがクリックされたときの処理。
        対応するスロットのクイックセット内容をUIに反映し、その後AIに送信します。
        """
        slot_index = self._get_sender_slot_index()
        if slot_index is None: return
        slot_id = f"slot_{slot_index}"

        if self._apply_quick_set_to_ui(slot_id):
            set_name = self.quick_sets_data.get(slot_id, {}).get("name", f"スロット {slot_index + 1}")
            print(f"Quick set '{set_name}' applied. Now sending to AI...")
            # 通常の送信処理を呼び出す
            self.on_send_button_clicked() 


    def _on_quick_set_clear_clicked(self):
        """「クリア」ボタンがクリックされたときの処理。
        対応するスロットのクイックセットを削除します。
        """
        slot_index = self._get_sender_slot_index()
        if slot_index is None: return
        slot_id = f"slot_{slot_index}"

        slot_data = self.quick_sets_data.get(slot_id)
        if not slot_data: # スロットが既に空なら何もしない
            QMessageBox.information(self, "情報", f"スロット {slot_index + 1} は既に空です。")
            return

        set_name = slot_data.get("name", f"スロット {slot_index + 1}")
        reply = QMessageBox.question(
            self, "クリア確認",
            f"クイックセット「{set_name}」(スロット {slot_index + 1}) を本当にクリアしますか？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.quick_sets_data[slot_id] = None # スロットデータをNoneに
            self._save_quick_sets_to_file()
            self._update_quick_set_slots_display() # UI更新
            QMessageBox.information(self, "クリア完了", f"「{set_name}」をクリアしました。")
            print(f"Quick set in slot {slot_index + 1} ('{set_name}') cleared.")
    # --- ★★★ ------------------------------------------------- ★★★ ---

    # --- ★★★ サブプロンプトツリーウィジェット操作用メソッド ★★★ ---
    def uncheck_all_subprompts(self): # 旧: uncheck_all_subprompts_in_tree
        """全てのサブプロンプトのチェックを外し、内部状態もクリアします。"""
        if not hasattr(self, 'subprompt_tab_widget'): return

        for i in range(self.subprompt_tab_widget.count()):
            list_widget = self.subprompt_tab_widget.widget(i)
            if isinstance(list_widget, QListWidget):
                for j in range(list_widget.count()):
                    container_item = list_widget.item(j)
                    sub_item_widget = list_widget.itemWidget(container_item)
                    if isinstance(sub_item_widget, SubPromptItemWidget):
                        sub_item_widget.set_checked(False) # SubPromptItemWidgetのメソッドでチェックを外す

        self.checked_subprompts.clear() # 内部のチェック状態も全てクリア
        print("All subprompts unchecked in UI and internal state.")
        # 必要であれば、チェック状態変更を通知するシグナルなどを発行

    def check_subprompts_by_full_names(self, full_names_to_check: List[str]): # 旧: check_subprompts_in_tree_by_full_names
        """指定された \"カテゴリ:名前\" 形式のサブプロンプト名のリストに基づいて、
        UIの対応するアイテムにチェックを入れ、内部状態も更新します。
        このメソッドを呼ぶ前に uncheck_all_subprompts() で全解除推奨。
        """
        if not hasattr(self, 'subprompt_tab_widget'): return
        if not full_names_to_check: return

        print(f"Checking subprompts in UI: {full_names_to_check}")
        checked_count = 0
        
        # uncheck_all_subprompts で self.checked_subprompts はクリアされている前提

        for full_name in full_names_to_check:
            parts = full_name.split(":", 1)
            category_name_to_find = parts[0]
            subprompt_name_to_find = parts[1] if len(parts) > 1 else None

            if not subprompt_name_to_find:
                print(f"  Skipping invalid full_name (no subprompt name): {full_name}")
                continue

            found_category_tab = False
            for i in range(self.subprompt_tab_widget.count()):
                if self.subprompt_tab_widget.tabText(i) == category_name_to_find:
                    list_widget = self.subprompt_tab_widget.widget(i)
                    if isinstance(list_widget, QListWidget):
                        found_category_tab = True
                        for j in range(list_widget.count()):
                            container_item = list_widget.item(j)
                            sub_item_widget = list_widget.itemWidget(container_item)
                            if isinstance(sub_item_widget, SubPromptItemWidget) and sub_item_widget.name == subprompt_name_to_find:
                                sub_item_widget.set_checked(True) # SubPromptItemWidgetのメソッドでチェック
                                # self.checked_subprompts も更新
                                if category_name_to_find not in self.checked_subprompts:
                                    self.checked_subprompts[category_name_to_find] = set()
                                self.checked_subprompts[category_name_to_find].add(subprompt_name_to_find)
                                checked_count += 1
                                break 
                        if found_category_tab: 
                             break 
            if not found_category_tab:
                 print(f"  Warning: Category tab '{category_name_to_find}' not found for subprompt '{subprompt_name_to_find}'.")
        
        print(f"  {checked_count} subprompts checked based on the list and internal state updated.")
    # --- ★★★ --------------------------------------------------- ★★★ ---

    def closeEvent(self, event):
        """ウィンドウが閉じられる前に呼び出されるイベント。
        現在のプロジェクト設定（メインプロンプト、チェック状態）とチャット履歴を保存します。
        """
        print("--- MainWindow: Closing application ---")
        # メインシステムプロンプトの保存
        current_main_prompt_text = self.system_prompt_input_main.toPlainText()
        if self.current_project_settings.get("main_system_prompt") != current_main_prompt_text:
            self.current_project_settings["main_system_prompt"] = current_main_prompt_text
            # save_project_settings は _save_checked_states_to_project_settings の中で行われるのでここでは不要

        # --- ★★★ 現在のチェック状態を保存 ★★★ ---
        self._save_checked_states_to_project_settings()
        # --- ★★★ ----------------------------- ★★★ ---

        # 現在のチャット履歴を保存
        if self.chat_handler:
            self.chat_handler.save_current_history_on_exit()

        # DetailWindow が開いていれば閉じる (もしあれば)
        if hasattr(self, 'data_management_widget') and self.data_management_widget and \
           hasattr(self.data_management_widget, '_detail_window') and self.data_management_widget._detail_window:
            if self.data_management_widget._detail_window.isVisible():
                self.data_management_widget._detail_window.close()
        
        super().closeEvent(event)

    # --- ★★★ 新規: 送信キーモード更新用スロット ★★★ ---
    def _update_send_key_mode(self, send_on_enter_selected: bool):
        """送信キーモードのラジオボタンが変更されたときに呼び出されます。
        グローバル設定を更新・保存します。
        """
        # QRadioButtonのtoggledシグナルは、チェックが外れたときも発行されるため、
        # 実際にチェックされた方の状態をみて判定する
        if self.radio_send_on_enter.isChecked() == send_on_enter_selected:
            new_mode = send_on_enter_selected
        else: # もう片方が選択されたはず
            new_mode = not send_on_enter_selected
            
        if self.send_on_enter_mode != new_mode:
            self.send_on_enter_mode = new_mode
            self.global_config["send_on_enter_mode"] = self.send_on_enter_mode
            if save_global_config(self.global_config):
                print(f"送信キーモードを更新しました: {'Enterで送信' if self.send_on_enter_mode else 'Shift+Enterで送信'}")
            else:
                QMessageBox.warning(self, "設定保存エラー", "送信キーモード設定の保存に失敗しました。")
    # --- ★★★ ------------------------------------------ ★★★ ---

    # --- ★★★ 新規: イベントフィルターメソッド ★★★ ---
    def eventFilter(self, obj, event: QEvent) -> bool:
        """user_input QTextEdit のキーイベントを監視し、
        設定に応じた送信/改行処理を行います。
        """
        if obj is self.user_input and event.type() == QEvent.KeyPress:
            key_event = event # type: ignore (QKeyEventにキャストできるはず)
            key = key_event.key()
            modifiers = key_event.modifiers()

            is_shift_pressed = bool(modifiers & Qt.ShiftModifier)

            # Enterキー (ReturnまたはEnter)
            if key == Qt.Key_Return or key == Qt.Key_Enter:
                if self.send_on_enter_mode:
                    if is_shift_pressed:
                        # Enterで送信モード + Shiftキーあり => 改行
                        # デフォルトのQTextEditの動作に任せる
                        return super().eventFilter(obj, event)
                    else:
                        # Enterで送信モード + Shiftキーなし => 送信
                        self.on_send_button_clicked()
                        return True # イベントを消費 (改行させない)
                else: # Shift+Enterで送信モード
                    if is_shift_pressed:
                        # Shift+Enterで送信モード + Shiftキーあり => 送信
                        self.on_send_button_clicked()
                        return True # イベントを消費 (改行させない)
                    else:
                        # Shift+Enterで送信モード + Shiftキーなし => 改行
                        # デフォルトのQTextEditの動作に任せる
                        return super().eventFilter(obj, event)
            
        return super().eventFilter(obj, event) # 他のイベントは基底クラスに任せる
    # --- ★★★ ------------------------------------ ★★★ ---

    # --- ★★★ 新規: AI応答履歴スクロール用スロットメソッド ★★★ ---
    def _scroll_history_to_top(self):
        """AI応答履歴表示エリアを一番上にスクロールします。"""
        if hasattr(self, 'response_display') and self.response_display:
            scroll_bar = self.response_display.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.minimum()) 
            # print("Scrolled history to top.")

    def _scroll_history_to_bottom(self):
        """AI応答履歴表示エリアを一番下にスクロールします。"""
        if hasattr(self, 'response_display') and self.response_display:
            scroll_bar = self.response_display.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
            # print("Scrolled history to bottom.")
    # --- ★★★ ------------------------------------------------ ★★★ ---

    # --- ★★★ 新規: 送信履歴範囲スライダーの値変更時のスロット ★★★ ---
    def _on_history_slider_changed(self, value: int):
        """送信履歴範囲スライダーの値が変更されたときに呼び出されます。
        ラベル表示と内部変数を更新します。
        グローバル設定にも保存します。

        Args:
            value (int): スライダーの新しい値。
        """
        self.current_history_range_for_prompt = value
        self.history_slider_label.setText(f"送信履歴範囲: {value} ")
        # グローバル設定を更新して保存
        self.global_config["history_range_for_prompt"] = value
        if not save_global_config(self.global_config):
            QMessageBox.warning(self, "設定保存エラー", "送信履歴範囲の設定保存に失敗しました。")
    # --- ★★★ -------------------------------------------------- ★★★ ---

    # --- ★★★ 新規: アイテム履歴数スライダーの値変更時のスロット ★★★ ---
    def _on_item_history_slider_changed(self, value: int):
        """アイテム履歴表示数スライダーの値が変更されたときに呼び出されます。
        ラベル表示と内部変数を更新します。

        Args:
            value (int): スライダーの新しい値。
        """
        self.item_history_length_for_prompt = value
        self.item_history_slider_label.setText(f"アイテム履歴の送信数: {value} ")
    # --- ★★★ ----------------------------------------------------- ★★★ ---

    # --- ★★★ 新しいヘルパーメソッド: 一時的コンテキスト文字列の構築 ★★★ ---
    def _build_transient_context_string(self) -> str:
        """現在の選択状態に基づいて、指定されたフォーマットの一時的コンテキスト文字列を構築します。"""
        context_parts = []

        context_parts.append("これはロールプレイの指示及びロールプレイに必要な情報です\n")
        context_parts.append("---------------------------------------------------\n")

        # --- 1. サブプロンプト --- 
        active_subprompts_parts = []
        # カテゴリやサブプロンプト名の順序をある程度固定するためソート
        sorted_categories_sub = sorted(self.checked_subprompts.keys())
        for category_name in sorted_categories_sub:
            if category_name in self.subprompts:
                sorted_subprompt_names = sorted(list(self.checked_subprompts[category_name]))
                for sub_name in sorted_subprompt_names:
                    if sub_name in self.subprompts[category_name]:
                        sub_data = self.subprompts[category_name][sub_name]
                        prompt_content = sub_data.get("prompt", "")
                        if prompt_content:
                            active_subprompts_parts.append(f"## {sub_name}\n{prompt_content}")
        if active_subprompts_parts:
            context_parts.append("# サブプロンプト\n\n" + "\n\n".join(active_subprompts_parts))

        # --- 2. 選択されたデータアイテムの情報 --- 
        checked_data_from_widget = self.data_management_widget.get_checked_items() # {cat: {id1, id2}}
        sorted_categories_data = sorted(checked_data_from_widget.keys())
        
        selected_items_by_category_parts = []
        for category_name in sorted_categories_data:
            item_ids_in_category = checked_data_from_widget[category_name]
            if not item_ids_in_category: continue

            category_section_parts = [f"# {category_name}の情報"]
            sorted_item_ids = sorted(list(item_ids_in_category))

            for item_id in sorted_item_ids:
                item_detail = get_item(self.current_project_dir_name, category_name, item_id)
                if item_detail:
                    item_name = item_detail.get("name", "N/A")
                    item_desc = item_detail.get("description", "")
                    item_info_str = f"## {item_name}\n{item_desc}"
                    
                    item_histories_full = item_detail.get("history", [])
                    num_histories_to_include = self.item_history_length_for_prompt
                    
                    if num_histories_to_include > 0 and item_histories_full:
                        sliced_item_histories = item_histories_full[-num_histories_to_include:]
                        history_entries_text = []
                        for h_entry in sliced_item_histories:
                            entry_text = h_entry.get("entry", "")
                            if entry_text:
                                history_entries_text.append(entry_text.strip())
                        if history_entries_text:
                            item_info_str += f"\n\n### {item_name}の履歴情報\n" + "\n".join(history_entries_text)
                    elif num_histories_to_include == 0 and item_histories_full:
                         item_info_str += f"\n\n### {item_name}の履歴情報\n(履歴の送信数設定0件のため省略)"

                    category_section_parts.append(item_info_str)
            
            if len(category_section_parts) > 1: # カテゴリヘッダー以外にアイテムがあれば追加
                selected_items_by_category_parts.append("\n\n".join(category_section_parts))
        
        if selected_items_by_category_parts:
            context_parts.append("\n\n".join(selected_items_by_category_parts)) # 各カテゴリセクション間も2重改行


        # --- 3. タグによる関連情報 --- 
        from core.data_manager import find_items_by_tags # 関数をインポート
        
        all_reference_tags_set = set()
        # (3-1) チェックされたサブプロンプトからの参照タグ収集
        for cat_sp, names_sp_set in self.checked_subprompts.items():
            if cat_sp in self.subprompts:
                for name_sp in names_sp_set:
                    if name_sp in self.subprompts[cat_sp]:
                        ref_tags_sp = self.subprompts[cat_sp][name_sp].get("reference_tags", [])
                        if ref_tags_sp: all_reference_tags_set.update(ref_tags_sp)
        
        # (3-2) チェックされたデータアイテムからの参照タグ収集
        for cat_di, ids_di_set in checked_data_from_widget.items(): # checked_data_from_widget を再利用
            for id_di in ids_di_set:
                item_detail_di = get_item(self.current_project_dir_name, cat_di, id_di)
                if item_detail_di:
                    ref_tags_di = item_detail_di.get("reference_tags", [])
                    if ref_tags_di: all_reference_tags_set.update(ref_tags_di)
        
        sorted_unique_ref_tags = sorted(list(all_reference_tags_set))
        tagged_items_by_tag_parts = []

        if sorted_unique_ref_tags:
            for tag_name in sorted_unique_ref_tags:
                tag_section_parts = [f"# {tag_name}の関連情報"]
                # find_items_by_tags はタグのリストを受け取るが、ここでは個別のタグで検索
                found_tagged_items = find_items_by_tags(self.current_project_dir_name, [tag_name])
                
                items_for_this_tag_str = []
                if found_tagged_items:
                    # 重複排除: checked_data_from_widget を使って、既に「選択されたアイテム」として表示済みのものは除外
                    # checked_data_from_widget は {category: {id1, id2}} の形式
                    # find_items_by_tags は [{'id': ..., 'category': ..., ...}] のリストを返す
                    for item in found_tagged_items:
                        item_id_found = item.get("id")
                        item_cat_found = item.get("category")
                        # このアイテムが既に「選択されたアイテム」に含まれていないか確認
                        if item_cat_found in checked_data_from_widget and item_id_found in checked_data_from_widget[item_cat_found]:
                            continue # 既に表示済みなのでスキップ
                        
                        item_name = item.get("name", "N/A")
                        item_desc = item.get("description", "(説明なし)")
                        recent_hist_list = item.get("recent_history", []) # これは文字列のリスト
                        
                        tagged_item_info_str = f"## {item_name}（{item_cat_found}）\n{item_desc}"
                        if recent_hist_list:
                            tagged_item_info_str += "\n最新履歴：" + "\n".join(recent_hist_list)
                        items_for_this_tag_str.append(tagged_item_info_str)
                
                if items_for_this_tag_str:
                    tag_section_parts.append("\n\n".join(items_for_this_tag_str))
                    tagged_items_by_tag_parts.append("\n\n".join(tag_section_parts))
            
        if tagged_items_by_tag_parts:
            context_parts.append("\n\n".join(tagged_items_by_tag_parts))

        # print(context_parts)
        context_parts.append("---------------------------------------------------\n")
        context_parts.append("次に入力されているメッセージがユーザーのセリフおよび行動です。")

        return "\n\n\n".join(context_parts).strip() # 各大セクション間は3重改行
    # --- ★★★ ---------------------------------------------------- ★★★ ---

    # --- ★★★ 新しいヘルパーメソッド: プレビュー用の履歴取得 ★★★ ---
    def _get_history_for_preview(self) -> List[Dict[str, any]]:
        """プレビューダイアログ用に、現在の履歴設定に基づいた会話履歴のリストを返します。
        GeminiChatHandlerから純粋な履歴を取得し、設定された範囲で切り詰めます。
        形式: [{'role': 'user'/'model', 'parts': [{'text': ...}]}, ...]
        """
        if not self.chat_handler:
            return []

        pure_history = self.chat_handler.get_pure_chat_history()
        
        # current_history_range_for_prompt (往復数) に基づいて履歴を切り詰める
        # 1往復 = 2メッセージ (user, model)
        num_messages_to_keep = self.current_history_range_for_prompt * 2
        
        if self.current_history_range_for_prompt >= 0 and len(pure_history) > num_messages_to_keep:
            return pure_history[-num_messages_to_keep:]
        elif self.current_history_range_for_prompt < 0: # 履歴なしの場合
            return []
        else:
            return pure_history # 全履歴または指定範囲内
    # --- ★★★ ------------------------------------------------ ★★★ ---

    # --- ★★★ 送信内容確認ダイアログ表示メソッド ★★★ ---
    def _show_prompt_preview_dialog(self):
        """送信内容確認ダイアログを表示します。"""
        if not self.chat_handler:
            QMessageBox.warning(self, "エラー", "チャットハンドラが初期化されていません。")
            return

        model_name = self.chat_handler.model_name
        system_prompt = self.system_prompt_input_main.toPlainText().strip()
        transient_context = self._build_transient_context_string()
        user_input = self.user_input.toPlainText().strip()
        
        # ダイアログのAPIプレビューで表示する「メッセージ本体」のために結合しておく
        # 実際の送信では、transient_context と user_input は結合されて chat_handler.send_message_with_context に渡される
        full_prompt_for_preview = ""
        if transient_context:
            full_prompt_for_preview += transient_context
        if user_input:
            if full_prompt_for_preview: # 既にコンテキストがあれば改行を挟む
                full_prompt_for_preview += "\n\n" # プレビューなので分かりやすく2重改行
            full_prompt_for_preview += user_input
        
        history_for_preview = self._get_history_for_preview() # 送信対象の全履歴
        
        generation_config = self.chat_handler.get_generation_config() or {}
        safety_settings_raw = self.chat_handler.get_safety_settings() or []
        
        safety_settings_for_display = []
        for setting in safety_settings_raw:
            category_enum = setting.get("category")
            threshold_enum = setting.get("threshold")
            safety_settings_for_display.append({
                "category": category_enum.name if hasattr(category_enum, 'name') else str(category_enum),
                "threshold": threshold_enum.name if hasattr(threshold_enum, 'name') else str(threshold_enum)
            })

        dialog = PromptPreviewDialog(self)
        dialog.update_preview(
            model_name=model_name,
            system_prompt=system_prompt, 
            transient_context=transient_context, # 個別のコンテキストも渡す
            user_input=user_input,               # 個別のユーザー入力も渡す
            full_prompt=full_prompt_for_preview, # 結合したものをAPIプレビューのメッセージ部用として渡す
            history=history_for_preview,
            generation_config=generation_config,
            safety_settings=safety_settings_for_display
        )
        dialog.exec_()
    # --- ★★★ ------------------------------------ ★★★ ---

    # --- ★★★ 新しいヘルパーメソッド: チェック状態の保存 ★★★ ---
    def _save_checked_states_to_project_settings(self):
        """現在のサブプロンプトとデータアイテムのチェック状態を
        現在のプロジェクトの project_settings.json に保存します。
        """
        if not self.current_project_dir_name:
            print("Warning: Cannot save checked states, no current project directory name.")
            return

        # 1. サブプロンプトのチェック状態を取得・整形
        # self.checked_subprompts は {カテゴリ名: set(サブプロンプト名)}
        # 保存形式は {"カテゴリ名": ["サブプロンプト名1", ...]} にする
        subprompts_to_save = {
            cat: sorted(list(names)) for cat, names in self.checked_subprompts.items()
        }
        self.current_project_settings["checked_subprompts"] = subprompts_to_save
        print(f"  Preparing to save checked subprompts: {subprompts_to_save}")

        # 2. データアイテムのチェック状態を取得・整形 (DataManagementWidgetから)
        if hasattr(self, 'data_management_widget') and self.data_management_widget:
            # data_management_widget.get_checked_items() は {カテゴリ名: set(アイテムID)} を返す
            # これもリスト形式で保存
            checked_data_from_widget = self.data_management_widget.get_checked_items()
            data_items_to_save = {
                cat: sorted(list(ids)) for cat, ids in checked_data_from_widget.items()
            }
            self.current_project_settings["checked_data_items"] = data_items_to_save
            print(f"  Preparing to save checked data items: {data_items_to_save}")
        else:
            print("  DataManagementWidget not found, cannot save data item checked states.")
            # 存在しない場合はキーを削除するか、何もしないか (ここでは何もしない)

        # 3. プロジェクト設定ファイルに保存
        if save_project_settings(self.current_project_dir_name, self.current_project_settings):
            print(f"  Checked states (subprompts and data items) saved to project settings for '{self.current_project_dir_name}'.")
        else:
            QMessageBox.warning(self, "保存エラー", "チェック状態のプロジェクト設定への保存に失敗しました。")
            print(f"  ERROR: Failed to save checked states to project settings for '{self.current_project_dir_name}'.")
    # --- ★★★ ------------------------------------------------ ★★★ ---

    def update_status_label(self):
        """APIキーの状態と現在のプロジェクト名に基づいてステータスラベルを更新します。"""
        if not hasattr(self, 'status_label'): # UI初期化前は実行しない
            return

        api_key_ok = is_configured()
        project_name_display = "(プロジェクトなし)"
        if self.current_project_dir_name and self.current_project_settings:
            project_name_display = self.current_project_settings.get("project_display_name", self.current_project_dir_name)

        status_text = f"プロジェクト: {project_name_display}  |  APIキー: <font color='{'green' if api_key_ok else 'red'}'>{'設定済み' if api_key_ok else '未設定/エラー'}</font>"
        self.status_label.setText(status_text)
        print(f"Status label updated: {status_text}")

    def get_gemini_chat_handler(self) -> Optional[GeminiChatHandler]:
        """現在のGeminiChatHandlerのインスタンスを返します。"""
        return self.chat_handler

    def get_current_chat_history(self) -> List[Dict[str, Union[str, List[Dict[str, str]]]]]:
        """現在のプロジェクトのチャット履歴 (_pure_chat_history) のコピーを返します。"""
        if self.chat_handler:
            return self.chat_handler.get_pure_chat_history() # 既にコピーを返す想定
        return []

    def _initialize_configs_and_project(self):
        """グローバル設定を読み込み、アクティブなプロジェクトのデータをロードします。"""
        print("--- MainWindow: Initializing configurations and project data ---")
        self.global_config = load_global_config()
        # --- ★★★ 送信キーモードのデフォルト値をglobal_configに書き込む(初回起動時など) ★★★ ---
        if "send_on_enter_mode" not in self.global_config:
            self.global_config["send_on_enter_mode"] = True # デフォルト
            save_global_config(self.global_config) # 保存
        # --- ★★★ -------------------------------------------------------------- ★★★ ---
        self.current_project_dir_name = self.global_config.get("active_project", "default_project")
        print(f"  Active project directory name from global config: '{self.current_project_dir_name}'")
        self._load_current_project_data() # 実際のデータ読み込み

    def _on_retry_button_clicked(self):
        """「リトライ」ボタンがクリックされたときの処理。"""
        if not self.chat_handler:
            QMessageBox.warning(self, "エラー", "チャットハンドラが初期化されていません。")
            return

        user_message_to_retry = self.chat_handler.delete_last_exchange_and_get_user_message()

        if user_message_to_retry is not None:
            self.user_input.setPlainText(user_message_to_retry)
            self.on_send_button_clicked() # メッセージを再送信
            # 履歴の再表示とボタン状態更新は on_send_button_clicked 内で行われる
        else:
            QMessageBox.information(self, "リトライ不可", "リトライ可能な直前のやり取りが見つかりませんでした。")
            self._update_retry_button_state() # リトライできなかった場合もボタン状態を更新

    def _update_retry_button_state(self):
        """リトライボタンの有効/無効状態を更新します。"""
        if self.chat_handler and self.chat_handler._pure_chat_history:
            history = self.chat_handler._pure_chat_history
            if len(history) >= 1 and history[-1].get("role") == "model":
                 # 最後のメッセージがAIの応答であればリトライ可能
                # (delete_last_exchange_and_get_user_messageが履歴2件以上を要求するので、
                #  厳密には len(history) >= 2 でないとリトライは成功しないが、
                #  ボタンの有効化は最後のメッセージが model かどうかで判定する)
                self.retry_button.setEnabled(True)
                return
        self.retry_button.setEnabled(False)

    def _initialize_streaming_worker_and_connections(self, user_instruction: str, transient_context: str, history_to_send: List[Dict], max_history: Optional[int], effective_model: str, stream: bool): # ★ stream パラメータ追加
        """ストリーミングワーカーを初期化し、シグナルを接続して開始します。"""
        if not self.chat_handler:
            QMessageBox.warning(self, "エラー", "チャットハンドラが初期化されていません。")
            self._set_ui_for_streaming(False)
            return

        self.streaming_worker = StreamingWorker(
            chat_handler=self.chat_handler,
            user_instruction=user_instruction,
            item_context=transient_context,
            chat_history_to_include=history_to_send,
            max_history_pairs=max_history,
            override_model_name=effective_model if effective_model != self.chat_handler.model_name else None,
            stream=stream # ★ stream パラメータを渡す
        )
        self.streaming_worker.streaming_started.connect(self._handle_streaming_started)
        self.streaming_worker.chunk_received.connect(self._handle_chunk_received)
        self.streaming_worker.streaming_finished.connect(self._handle_streaming_finished)
        self.streaming_worker.streaming_error.connect(self._handle_streaming_error)
        self.streaming_worker.finished.connect(self._on_worker_finished) # QThread終了シグナル

        self._set_ui_for_streaming(True)
        self.streaming_worker.start()

    def _on_worker_finished(self):
        """ワーカースレッドが完全に終了した後にUIを確実に戻す処理。"""
        # ストリーミングが正常終了したかエラー終了したかに関わらず、
        # _handle_streaming_finished や _handle_streaming_error で is_streaming は False になっているはずだが、念のため。
        if self.is_streaming: # まだTrueなら、予期せぬ終了
            print("Warning: Worker finished but is_streaming was still True. Resetting UI.")
            self._handle_streaming_error("ストリーミング処理が予期せず終了しました。") # エラーとして扱う
        # self.streaming_worker = None # 必要に応じてワーカーインスタンスをクリア

    def _handle_streaming_started(self, ai_name: str, model_name: str):
        """ストリーミング開始時の処理。AI応答ヘッダーを表示。"""
        timestamp = QDateTime.currentDateTime().toString(Qt.ISODate)
        self._current_streaming_ai_message_id = f"ai_message_stream_{timestamp.replace(':', '-').replace('.', '-')}"
        self._current_streaming_content_element_id = f"ai_content_stream_{timestamp.replace(':', '-').replace('.', '-')}"

        from core.config_manager import DEFAULT_GLOBAL_CONFIG
        font_family = self.global_config.get("font_family", DEFAULT_GLOBAL_CONFIG.get("font_family", "MS Gothic"))
        font_size_pt = self.global_config.get("font_size", DEFAULT_GLOBAL_CONFIG.get("font_size", 10))
        font_line_height = self.global_config.get("font_line_height", DEFAULT_GLOBAL_CONFIG.get("font_line_height", 1.5))
        model_color = self.global_config.get("font_color_model_latest", DEFAULT_GLOBAL_CONFIG.get("font_color_model_latest", "rgb(0, 100, 200)"))

        base_font_style = f"font-family: '{font_family}'; font-size: {font_size_pt}pt;"
        entry_specific_color_style = f"color: {model_color};"
        comment_container_style = f"line-height: {font_line_height};" 
        name_container_style = "text-decoration: none !important;"

        # ストリーミング中はヘッダーと本文用コンテナのみ表示。フッターとセパレーターは表示しない。
        header_html = f'''
        <div id="{self._current_streaming_ai_message_id}" class="history-entry model-entry" style="{base_font_style} {entry_specific_color_style}" data-timestamp="{timestamp}">
            <div class="name-container" style="{name_container_style}">
                {ai_name} ({model_name}) 
                <span class="timestamp-display" style="font-size: {font_size_pt-2}pt; color: gray;">{QDateTime.currentDateTime().toString("yyyy/MM/dd HH:mm:ss")}</span>
            </div>
            <div class="comment-container" style="{comment_container_style}">
                <div id="{self._current_streaming_content_element_id}" class="message-text ai-message-text">
                </div>
            </div>
        </div>
        '''
        self.response_display.append(header_html)
        self._scroll_history_to_bottom_if_at_bottom() 

    def _get_streaming_placeholder_footer_html(self) -> str:
        """ストリーミング中に表示するフッターのプレースホルダーHTMLを返します。(今回は使用されない想定)"""
        return "" # ストリーミング中はフッターを表示しないので空文字列を返す

    def _handle_chunk_received(self, chunk_text: str):
        """受信したテキストチャンクを追記。"""
        # ストリーミング開始時にカーソルが本文用DIVの末尾にあると仮定し、そこにプレーンテキストを挿入。
        # _handle_streaming_started で追加したHTML要素の後にそのまま追加される形になる。
        self.response_display.moveCursor(QTextCursor.End) 
        self.response_display.insertPlainText(chunk_text) 
        self._scroll_history_to_bottom_if_at_bottom()

    def _handle_streaming_finished(self, full_text: str, usage_metadata: dict, model_name: str):
        """ストリーミング完了時の処理。フッター更新、履歴保存。"""
        if not self._current_streaming_ai_message_id: # ストリーミングIDがない場合はエラーとして扱うか、何もしない
            print("Error: Streaming finished but _current_streaming_ai_message_id is not set.")
            self._set_ui_for_streaming(False)
            self._update_retry_button_state()
            return

        # JavaScriptでのDOM操作は行わない。
        # ストリーミング開始時に表示されたヘッダー部分の更新は行わず、
        # 完了したメッセージとして、整形されたHTML全体を新たに追加する。
        # ただし、これだとヘッダーと本文が分離してしまう。
        # より良い方法は、ストリーミング開始時のプレースホルダーを削除し、
        # 完成したHTMLを追記するか、MainWindowレベルでメッセージのID管理と置換を行うこと。

        # ここでは、_current_streaming_ai_message_id を使って表示されたプレースホルダーを
        # 削除し、完成したメッセージを _append_message_to_display で表示する方針を試みる。
        
        # 1. 古いプレースホルダーを削除する (QTextBrowserではID指定での直接削除が困難なため、限定的な対応)
        #    ここでは単純に、最後に表示されたものがプレースホルダーだったと仮定して処理するのではなく、
        #    _redisplay_chat_history と同様のロジックで、メッセージを履歴に追加した後、
        #    全体を再表示するアプローチを取るのが最も安全かもしれない。
        #    しかし、それはUXとして望ましくない。

        #    今回の修正では、プレーンテキストで追記された内容が response_display に残っている状態。
        #    これを一度クリアし、整形されたメッセージを追記する。
        #    ただし、_current_streaming_ai_message_id を使って表示したヘッダーは残る。
        #    理想的には、そのヘッダーに対応する本文とフッターを更新したい。

        #    最も簡単な対処: 逐次表示されたプレーンテキストはそのままに、フッター情報などを追記する。
        #    または、ストリーミング開始時のヘッダーを削除し、完全なメッセージをappendする。

        #    今回は、ストリーミング開始時に表示した初期ブロック (_current_streaming_ai_message_id) を
        #    見つけて、その内容を完成版で更新する試みはQTextBrowserでは困難なので、
        #    チャット履歴に保存し、UIを更新する(_redisplay_chat_history と同様の処理を最後に行う)。
        #    ストリーミング中の逐次表示は insertPlainText で行い、完了時に完全な履歴を再描画する。

        timestamp_str = self.response_display.find(self._current_streaming_ai_message_id) # このIDはHTML要素のID
        # timestamp_str は QDateTime.currentDateTime().toString(Qt.ISODate) 形式だったはず
        # HTML要素から取得するのは困難なので、_handle_streaming_started で保存したタイムスタンプを使うべき。
        # しかし、そのタイムスタンプは streaming_worker からは直接渡されていない。

        # 暫定対応: 最後に表示されたメッセージがストリーミング中のものだったとして、それを更新する試みはせず、
        # 新たに完全なメッセージとして履歴に追加し、UIに表示する。
        # ユーザーメッセージ -> [AIヘッダー表示] -> [AI本文(逐次)] -> [AIフッター+完成本文(新規)] のような流れを避けるため、
        # _append_message_to_display を使う。

        current_timestamp_for_storage = QDateTime.currentDateTime().toString(Qt.ISODate) # 新しいタイムスタンプ

        # 履歴に保存するデータを作成
        history_entry = {
            'role': 'model',
            'parts': [{'text': full_text}],
            'model_name': model_name,
            'timestamp': current_timestamp_for_storage, # ストリーミング完了時のタイムスタンプ
            'usage': usage_metadata if usage_metadata else {}
        }

        if self.chat_handler:
            self.chat_handler._pure_chat_history.append(history_entry)
            self.chat_handler._save_history_to_file()

        # ストリーミング開始時に表示したプレースホルダー的な表示は、
        # この _redisplay_chat_history によって上書きされる（消える）。
        self._redisplay_chat_history() # これにより、全ての履歴が正しく整形されて表示される

        self._set_ui_for_streaming(False)
        self._update_retry_button_state()
        self._scroll_history_to_bottom_if_at_bottom() # 再表示後にスクロール
        self._current_streaming_ai_message_id = None
        self._current_streaming_content_element_id = None
        self.update_status_label()

    def _get_completed_footer_html(self, timestamp: str, usage: Optional[Dict[str, int]]) -> str:
        """ストリーミング完了後に表示するフッターHTMLを生成します。"""
        token_info_parts = []
        if usage:
            if "prompt_token_count" in usage: # Gemini API のキー名
                token_info_parts.append(f"In: {usage['prompt_token_count']}")
            if "candidates_token_count" in usage:
                token_info_parts.append(f"Out: {usage['candidates_token_count']}")
            if "total_token_count" in usage:
                token_info_parts.append(f"Total: {usage['total_token_count']}")
        token_info_str = " | ".join(token_info_parts) if token_info_parts else "N/A"
        
        # 履歴内のインデックスを見つける必要がある。ここでは単純化のためtimestampを使う
        # 実際には _redisplay_chat_history のようにインデックスを渡せるようにするべき
        # ここでは timestamp を使った仮のリンク
        edit_action = f'edit_history_item:{timestamp}'
        delete_action = f'delete_history_item:{timestamp}'

        return f'''
        <div class="message-footer">
            <span class="token-info">Tokens: {token_info_str}</span>
            <span class="actions">
                <a href="{edit_action}" class="action-link">編集</a>
                <a href="{delete_action}" class="action-link">削除</a>
            </span>
        </div>
        '''

    def _handle_streaming_error(self, error_message: str):
        """ストリーミングエラー発生時の処理。"""
        if self._current_streaming_ai_message_id:
            # 既存のストリーミング表示ブロックがあれば、そこにエラーメッセージを追記・更新
            # JavaScriptでの細かいDOM操作はQTextBrowserでは難しいため、エラーは新しい行として表示する方針に変更
            error_html_display = f'<div style="color: red;">AI応答生成中にエラー（ストリームID: {self._current_streaming_ai_message_id}）: {error_message}</div>'
            self.response_display.append(error_html_display)
            # 元のJavaScriptでのフッター更新処理は、ここでは実行できないためコメントアウトまたは削除
            # escaped_error_html_for_js = error_html.replace("`", "\\`") # バックスラッシュをエスケープ
            # script = f'''
            #     var element = document.getElementById("{self._current_streaming_content_element_id}");
            #     if (element) {{
            #         element.innerHTML += `{escaped_error_html_for_js}`;
            #     }}
            #     var footer = document.querySelector("#{self._current_streaming_ai_message_id} .streaming-placeholder-footer .token-info");
            #     if (footer) {{ footer.textContent = "エラー発生"; footer.style.color = "red"; }}
            # '''
            # self.response_display.page().runJavaScript(script) # この行がAttributeErrorの原因
        else:
            # まだ何も表示していなければ、新しいエラーブロックとして表示
            self.response_display.append(f'<div class="message-container error-message-container"><p style="color: red;">ストリーミングエラー: {error_message}</p></div>')
        
        QMessageBox.warning(self, "ストリーミングエラー", error_message)
        self._set_ui_for_streaming(False)
        self._update_retry_button_state()
        self._current_streaming_ai_message_id = None
        self._current_streaming_content_element_id = None
        self.update_status_label() # ステータス更新

    def _scroll_history_to_bottom_if_at_bottom(self):
        """応答表示エリアが最下部にある場合のみ、最下部にスクロールする。"""
        scrollbar = self.response_display.verticalScrollBar()
        # スクロールバーが一番下にあるか、あるいはスクロール可能な範囲が非常に小さい場合に自動スクロール
        # (コンテンツが少ない初期状態では maximum が minimum と同じか非常に近くなるため)
        at_bottom = scrollbar.value() >= (scrollbar.maximum() - 5) # 少しの誤差を許容
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum()) # 最下部にスクロール

    def _convert_markdown_to_html_for_display(self, markdown_text: str) -> str:
        """MarkdownテキストをHTMLに変換して表示用に整形する (既存の処理を参考に実装)。
           ひとまず簡易的な実装として、改行を <br> に、コードブロックを <pre> にする程度。
           実際には、 _format_history_entry_to_html のようなリッチな変換が必要。
        """
        if not hasattr(self, '_md_parser'): # Markdownパーサーをキャッシュ
            try:
                from markdown import Markdown
                self._md_parser = Markdown(extensions=[
                    'fenced_code', # ```code```
                    'codehilite',  # シンタックスハイライト (Pygmentsが必要)
                    'tables',      # テーブル
                    'nl2br'        # 改行を<br>に
                ])
                print("Markdown parser initialized with extensions.")
            except ImportError:
                self._md_parser = None
                print("Markdown library not found. Basic Markdown conversion will be used.")

        if self._md_parser:
            # HTMLエスケープ文字が混ざっていると二重エスケープされる可能性があるので注意
            # full_text は純粋なテキストであることを期待
            html = self._md_parser.convert(markdown_text)
        else:
            html = markdown_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html = html.replace("\n", "<br>")
            # Very basic code block ``` ... ``` (DOTALL makes . match newline)
            # html = re.sub(r"```(.*?)```", r"<pre><code>\1</code></pre>", html, flags=re.DOTALL) # Linter error source, temporarily commented out
            # html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
            # Fallback without complex regex for now if markdown library is not present
            if "```" in html:
                html = html.replace("```", "<pre>", 1) # Opening ```
                html = html.replace("```", "</pre>")   # Closing ``` (assumes only one block or simple cases)
            if "`" in html:
                 html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html) # Inline code still uses regex

        return html

    # --- ★★★ 新規: ストリーミングチェックボックスの状態変更スロット ★★★ ---
    def _on_streaming_checkbox_changed(self, state):
        """ストリーミング有効化チェックボックスの状態が変更されたときに呼び出されます。"""
        self.enable_streaming = bool(state == Qt.Checked)
        print(f"Streaming enabled: {self.enable_streaming}")
        # グローバル設定を更新して保存
        self.global_config["enable_streaming"] = self.enable_streaming
        if not save_global_config(self.global_config):
            QMessageBox.warning(self, "設定保存エラー", "ストリーミング設定の保存に失敗しました。")
    # --- ★★★ ---------------------------------------------------- ★★★ ---

if __name__ == '__main__':
    """MainWindowの基本的な表示・インタラクションテスト。"""
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())