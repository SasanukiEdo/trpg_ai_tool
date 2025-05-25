# ui/prompt_preview_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, 
    QScrollArea, QWidget, QDialogButtonBox, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt
import json 
from typing import Optional

class PromptPreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("送信内容の確認")
        self.setMinimumSize(800, 800) # 全体の最小サイズを調整 (content_group固定高さのため)

        self.layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(scroll_area)

        # --- 送信コンテンツセクション (会話履歴も含む) ---
        content_group = QGroupBox("送信コンテンツ詳細")
        content_layout = QFormLayout(content_group)

        self.transient_context_text = QTextEdit()
        self.transient_context_text.setReadOnly(True)
        self.transient_context_text.setPlaceholderText("一時的なコンテキストはありません。")
        self.transient_context_text.setFixedHeight(80) # 高さを固定
        content_layout.addRow("一時的コンテキスト:", self.transient_context_text)

        self.user_input_text = QTextEdit()
        self.user_input_text.setReadOnly(True)
        self.user_input_text.setPlaceholderText("ユーザー入力はありません。")
        self.user_input_text.setFixedHeight(50) # 高さを固定
        content_layout.addRow("ユーザー入力:", self.user_input_text)
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setPlaceholderText("送信に含める会話履歴はありません。")
        self.history_text.setFixedHeight(100) # 高さを固定
        content_layout.addRow("会話履歴 (送信対象):", self.history_text)
        
        # content_group の高さを固定 (内部ウィジェット、ラベル、マージンを考慮した値)
        content_group.setFixedHeight(270) # この値は必要に応じて調整してください
        self.scroll_layout.addWidget(content_group)

        # --- APIリクエストボディ風プレビューセクション ---
        api_preview_group = QGroupBox("APIリクエストボディ風プレビュー (主要部分)")
        api_preview_layout = QVBoxLayout(api_preview_group)
        
        self.api_preview_text = QTextEdit()
        self.api_preview_text.setReadOnly(True)
        self.api_preview_text.setPlaceholderText("APIに送信される主要な内容がここに表示されます。")
        self.api_preview_text.setMinimumHeight(250) # こちらは最小高さを維持 (可変)
        self.api_preview_text.setFontFamily("Courier New")
        self.api_preview_text.setLineWrapMode(QTextEdit.NoWrap)
        api_preview_layout.addWidget(self.api_preview_text)
        self.scroll_layout.addWidget(api_preview_group)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.accept)
        self.layout.addWidget(self.button_box)

    def _format_text_for_display(self, text_content: Optional[str]) -> str:
        if text_content is None:
            return ""
        processed_text = text_content.replace('\\\\n', '\\n')
        processed_text = processed_text.replace('/n', '\\n')
        processed_text = processed_text.replace('\\n', '\\n')
        return processed_text

    def update_preview(self, 
                       model_name: str, 
                       system_prompt: Optional[str], 
                       transient_context: Optional[str],
                       user_input: Optional[str],
                       full_prompt: Optional[str], 
                       history: list, 
                       generation_config: dict, 
                       safety_settings: list 
                       ):
        # 送信コンテンツ詳細
        self.transient_context_text.setPlainText(self._format_text_for_display(transient_context))
        self.user_input_text.setPlainText(self._format_text_for_display(user_input))

        history_display_text_full = ""
        if history:
            for item in history:
                role = item.get("role", "unknown")
                text_parts = item.get("parts")
                item_text_content = ""
                if isinstance(text_parts, list) and text_parts:
                    if isinstance(text_parts[0], dict):
                        item_text_content = text_parts[0].get("text", "")
                    elif isinstance(text_parts[0], str): 
                        item_text_content = text_parts[0]
                history_display_text_full += f"--- {role.upper()} ---\n{item_text_content}\n\n"
        self.history_text.setPlainText(
            self._format_text_for_display(history_display_text_full.strip()) or "送信に含める会話履歴はありません。"
        )

        # --- APIリクエストボディ風プレビュー --- 
        api_preview_dict = {}
        api_preview_dict["_model_name_for_request (client-side reference)"] = model_name or "N/A"
        if system_prompt:
            api_preview_dict["system_instruction"] = {
                "parts": [{"text": self._format_text_for_display(system_prompt)}]
            }

        api_contents_for_preview = []
        extracted_history_for_api = []
        num_total_history = len(history)
        if num_total_history > 0:
            if num_total_history <= 4:
                extracted_history_for_api.extend(history)
            else:
                extracted_history_for_api.append(history[0])
                extracted_history_for_api.append(history[1])
                extracted_history_for_api.append({"role": "system", "parts": [{"text": "... (中略) ..."}]})
                extracted_history_for_api.append(history[-2])
                extracted_history_for_api.append(history[-1])

        if extracted_history_for_api:
            for h_item in extracted_history_for_api:
                role = h_item.get("role", "unknown")
                text = ""
                parts_data = h_item.get("parts")
                if isinstance(parts_data, list) and parts_data:
                    if isinstance(parts_data[0], dict):
                        text = parts_data[0].get("text", "")
                if role == "system" and "... (中略) ..." in text: 
                    api_contents_for_preview.append({"role": role, "parts": [{"text": text}]})
                else:
                    api_contents_for_preview.append({"role": role, "parts": [{"text": self._format_text_for_display(text)}]})
        
        combined_input_parts = []
        if transient_context:
            combined_input_parts.append(transient_context)
        if user_input:
            combined_input_parts.append(user_input)
        final_user_content_text = full_prompt if full_prompt is not None else "\\\\n".join(combined_input_parts) 
        current_user_message_text_for_api = self._format_text_for_display(final_user_content_text)
        if current_user_message_text_for_api:
            api_contents_for_preview.append({"role": "user", "parts": [{"text": current_user_message_text_for_api}]})
        
        api_preview_dict["contents"] = api_contents_for_preview

        if generation_config:
            api_preview_dict["generation_config"] = generation_config
        if safety_settings:
            processed_safety_settings = []
            for ss in safety_settings:
                cat = ss.get("category")
                thr = ss.get("threshold")
                processed_safety_settings.append({"category": str(cat), "threshold": str(thr)})
            api_preview_dict["safety_settings"] = processed_safety_settings
        
        json_string_for_display = json.dumps(api_preview_dict, indent=2, ensure_ascii=False, default=str)
        final_api_preview_string = json_string_for_display.replace('\\\\n', '\\n')
        self.api_preview_text.setPlainText(final_api_preview_string)

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = PromptPreviewDialog()

    dummy_history = [
        {"role": "user", "parts": [{"text": "こんにちは"}]},
        {"role": "model", "parts": [{"text": "これは一つ目のAIの返答です。\\n複数行になっています。"}]},
        {"role": "user", "parts": [{"text": "今日の天気は？"}]},
        {"role": "model", "parts": [{"text": "晴れです。"}]},
        {"role": "user", "parts": [{"text": "ありがとう。\\nこれが最後のユーザー発言です。"}]},
        {"role": "model", "parts": [{"text": "どういたしまして！"}]},
    ]
    dummy_gen_config = {
        "temperature": 0.8, "top_p": 0.9, "top_k": 40, "max_output_tokens": 1024, "candidate_count": 1
    }
    dummy_safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
    ]

    dialog.update_preview(
        model_name="gemini-1.5-pro-latest",
        system_prompt="あなたはTRPGのゲームマスターアシスタントです。\\nプレイヤーの行動をサポートしてください。",
        transient_context="現在のシーン: 古代遺跡の入り口\\nプレイヤー選択中のアイテム: 松明",
        user_input="松明で周囲を照らしながら、慎重に遺跡の中へ足を踏み入れる。",
        full_prompt="現在のシーン: 古代遺跡の入り口\\nプレイヤー選択中のアイテム: 松明\\n\\n松明で周囲を照らしながら、慎重に遺跡の中へ足を踏み入れる。",
        history=dummy_history,
        generation_config=dummy_gen_config,
        safety_settings=dummy_safety_settings
    )
    dialog.show()
    sys.exit(app.exec_())