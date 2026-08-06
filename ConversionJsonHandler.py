# backend/api/services/handlers/ConversionJsonHandler.py
import json
import os
from typing import Dict, Any

class ConversionJsonHandler:
    def __init__(self, llm_service, knowledge_manager):
        """
        :param llm_service: LLMを呼び出すサービス
        :param knowledge_manager: ファイル操作を行う KnowledgeManager のインスタンス
        """
        self.llm_service = llm_service
        self.knowledge_manager = knowledge_manager

    def handle(self, user_message: str, parsed_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON翻訳のメイン処理
        """
        print("🌍 [ConversionJsonHandler] JSONの英語翻訳を開始します...")

        # 1. ターゲットとなるJSONを特定（インテント解析結果から取得など）
        # ※ 実際の実装に合わせて取得元を変更してください
        targets = parsed_intent.get("targets", [])
        if not targets:
            return {"status": "error", "message": "翻訳するJSONファイルが指定されていません。"}
        
        target_file_path = targets[0] # 例: "data/locales/ja.json"

        # 2. （仮）対象ファイルの読み込み
        # 実際には LazyKnowledge やファイルを読んで中身を取得します
        # original_content_str = self._read_file(target_file_path)
        original_content_str = '{"greeting": "こんにちは", "farewell": "さようなら"}' # 仮データ

        # 3. LLMへ翻訳依頼
        prompt = self._build_prompt(original_content_str)
        translated_text = self.llm_service.generate_text(prompt)

        # 4. JSONとして正しいか検証＆整形
        try:
            # LLMが余計なMarkdown(```json)をつけてきた場合の除去など
            clean_text = translated_text.replace("```json", "").replace("```", "").strip()
            parsed_json = json.loads(clean_text)
            formatted_json_str = json.dumps(parsed_json, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            print("⚠️ [ConversionJsonHandler] LLMの出力が正しいJSONではありません。")
            return {"status": "error", "message": "翻訳結果のJSONフォーマットが不正です。"}

        # 5. KnowledgeManagerを使って保存
        new_file_path = self._generate_en_path(target_file_path)
        
        success = self.knowledge_manager.write_file(new_file_path, formatted_json_str)

        if success:
            return {
                "status": "success",
                "message": f"翻訳が完了し、{new_file_path} に保存しました！",
                "new_file_path": new_file_path,
                "content": parsed_json
            }
        else:
            return {
                "status": "error",
                "message": "ファイルの保存に失敗しました。"
            }

    def _build_prompt(self, json_str: str) -> str:
        return f"""
以下のJSONデータの「値（Value）」部分だけを自然な英語に翻訳してください。
キー（Key）は絶対に翻訳したり変更したりしないでください。
結果は純粋なJSONフォーマットのみを出力してください。

【対象のJSON】
{json_str}
"""

    def _generate_en_path(self, original_path: str) -> str:
        """
        'path/to/file.json' -> 'path/to/file.en.json' に変換
        """
        base_name, ext = os.path.splitext(original_path)
        if ext.lower() == '.json':
            return f"{base_name}.en.json"
        return f"{original_path}.en.json"
