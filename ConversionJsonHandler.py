# backend/api/services/handlers/ConversionJsonHandler.py
import json
import os
import zipfile
import uuid
from typing import Dict, Any

class ConversionJsonHandler:
    def __init__(self, llm_service, knowledge_manager):
        """
        :param llm_service: LLMを呼び出すサービス
        :param knowledge_manager: ファイル操作を行う KnowledgeManager のインスタンス
        """
        self.llm_service = llm_service
        self.knowledge_manager = knowledge_manager
        
        # 1度にLLMに投げるキーの数（トークン数上限に合わせて調整してください）
        self.chunk_size = 50 

    def handle(self, user_message: str, parsed_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON翻訳のメイン処理
        """
        print("🌍 [ConversionJsonHandler] JSONの英語翻訳を開始します...")

        targets = parsed_intent.get("targets", [])
        if not targets:
            return {"status": "error", "message": "翻訳するJSONファイルが指定されていません。"}
        
        results = []
        translated_files = [] # ZIPに含めるための成功したファイルパスリスト

        # 1. 複数ファイルをループ処理
        for target_file_path in targets:
            try:
                # ファイルの読み込み（※knowledge_managerの実装に合わせてメソッド名は変更してください）
                original_content_str = self.knowledge_manager.read_file(target_file_path)
                
                if not original_content_str:
                    raise ValueError("ファイルが空、または読み込めませんでした。")
                
                parsed_original = json.loads(original_content_str)
                
                # 2. 巨大なJSONを分割して翻訳
                translated_dict = self._translate_in_chunks(parsed_original)
                
                # 3. 整形と保存
                formatted_json_str = json.dumps(translated_dict, ensure_ascii=False, indent=2)
                new_file_path = self._generate_en_path(target_file_path)
                
                success = self.knowledge_manager.write_file(new_file_path, formatted_json_str)

                if success:
                    results.append({
                        "status": "success",
                        "original_path": target_file_path,
                        "new_file_path": new_file_path
                    })
                    translated_files.append(new_file_path)
                else:
                    results.append({
                        "status": "error",
                        "original_path": target_file_path,
                        "message": "ファイルの保存に失敗しました。"
                    })

            except Exception as e:
                print(f"⚠️ [ConversionJsonHandler] エラーが発生しました ({target_file_path}): {str(e)}")
                results.append({
                    "status": "error",
                    "original_path": target_file_path,
                    "message": f"処理エラー: {str(e)}"
                })

        # 4. 成功したファイルがあればZIPにまとめる (ClaudeのArtifactsライクな挙動)
        zip_download_url = None
        if len(translated_files) > 0:
            try:
                # ZIPファイルの保存先ディレクトリ（環境に合わせて調整してください）
                export_dir = os.path.join("data", "exports")
                os.makedirs(export_dir, exist_ok=True)
                
                # 同時実行時のかぶりを防ぐためUUIDを付与
                zip_filename = f"translated_jsons_{uuid.uuid4().hex[:8]}.zip"
                zip_filepath = os.path.join(export_dir, zip_filename)
                
                with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in translated_files:
                        # 実際のOS上の絶対パスを取得（※実装に合わせて変更してください）
                        # 例: actual_path = self.knowledge_manager.get_absolute_path(file_path)
                        actual_path = getattr(self.knowledge_manager, "get_absolute_path", lambda p: p)(file_path)
                        
                        # ZIP内でのファイル名を指定（ディレクトリ構造を維持しない場合はbasenameのみ）
                        arcname = os.path.basename(file_path)
                        
                        if os.path.exists(actual_path):
                            zipf.write(actual_path, arcname=arcname)
                
                # フロントエンドからのダウンロード用APIルートを指定（環境に合わせて調整）
                zip_download_url = f"/api/files/download?path={zip_filepath}"

            except Exception as e:
                print(f"⚠️ [ConversionJsonHandler] ZIPファイルの作成に失敗しました: {str(e)}")

        # 5. フロントエンドへ返すデータの構築
        return {
            "response_type": "ui_code",
            "message": f"{len(targets)}件中 {len(translated_files)}件 の翻訳処理が完了しました。",
            "blocks": [
                {
                    "type": "conversion_jsonBlock", 
                    "props": {
                        "results": results,
                        "zip_download_url": zip_download_url # フロントエンドでダウンロードボタン化する
                    }
                }
            ]
        }

    def _translate_in_chunks(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON（辞書）をチャンクごとに分割してLLMに翻訳させ、後で1つに結合する
        （※ネストが浅いフラットなキーバリューのJSONファイルに最適化されています）
        """
        keys = list(data.keys())
        translated_result = {}

        for i in range(0, len(keys), self.chunk_size):
            chunk_keys = keys[i:i + self.chunk_size]
            chunk_data = {k: data[k] for k in chunk_keys}
            
            prompt = self._build_prompt(json.dumps(chunk_data, ensure_ascii=False))
            translated_text = self.llm_service.generate_text(prompt)
            
            try:
                # LLMが余計なMarkdownやテキストをつけてきた場合の除去
                clean_text = translated_text.replace("```json", "").replace("```", "").strip()
                parsed_chunk = json.loads(clean_text)
                
                # 翻訳結果を統合
                translated_result.update(parsed_chunk)
            except json.JSONDecodeError:
                print("⚠️ [ConversionJsonHandler] LLMが不正なJSONを返しました。一部チャンクの原文を維持します。")
                # エラー時は元の日本語をそのまま保持するフェイルセーフ
                translated_result.update(chunk_data) 

        return translated_result

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
