import os
import json
import re
import traceback
from typing import Dict, Any, Tuple, Optional

# 事前に作成した PaperAnalysisHandler をインポート
from engine.handlers.paper_analysis_handler import PaperAnalysisHandler


class AnalysisOrchestrator:
    """
    論文データの逐次読み込み、補完・スコアリング解析、
    および JSON/JSONL での出力永続化と UI Block レンダリングを統括するオーケストレーター
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.handler = PaperAnalysisHandler()
        
        # 中間・最終成果物の保存用ディレクトリ
        self.output_dir = os.path.join(self.project_root, "backend", ".ai_memory", "analysis_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

    async def execute(self, request: Any) -> Tuple[str, Dict[str, Any]]:
        """
        ChatService から呼び出されるメインエントリーポイント。

        Args:
            request: ChatRequest (Pydanticモデル) または辞書形式のリクエスト

        Returns:
            Tuple[str, Dict[str, Any]]: (response_type, content)
        """
        try:
            # 1. リクエストメッセージの取り出し
            message_str = getattr(request, "message", None)
            if message_str is None and isinstance(request, dict):
                message_str = request.get("message", "")

            # 2. メッセージ文字列から JSON 論文データの自動抽出
            papers_data = self._extract_json_from_text(message_str)

            # JSONデータが存在しない場合のガード表示
            if not papers_data:
                return "ui_code", {
                    "message": "解析対象の論文JSONデータが見つかりませんでした。",
                    "blocks": [
                        {
                            "type": "MarkdownChatBlock",
                            "props": {
                                "content": "⚠️ **JSONデータが検出できませんでした**\n\n論文情報を含むJSONフォーマットのテキストを入力してください。自動的にスコア化とエビデンス構造化を行います。"
                            }
                        }
                    ]
                }

            # 3. Handler を呼び出してスコアリングおよび UI ブロック用のデータを生成
            handler_result = self.handler.analyze_papers(papers_data)

            # 4. スコア結果・根拠の保存（JSON / JSONL への永続化）
            self._save_analysis_results(handler_result)

            # 5. response_type と content を取得して返却
            response_type = handler_result.get("response_type", "ui_code")
            content = handler_result.get("content", {})

            return response_type, content

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"🚨 [AnalysisOrchestrator] エラー発生:\n{error_details}")

            return "ui_code", {
                "message": "論文解析処理の実行中にエラーが発生しました。",
                "blocks": [
                    {
                        "type": "MarkdownChatBlock",
                        "props": {
                            "content": f"❌ **処理エラーの詳細:**\n```\n{str(e)}\n```"
                        }
                    }
                ]
            }

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        テキストに含まれる ```json ... ``` や生のJSON文字列を安全に切り出してパースする
        """
        if not text:
            return {}

        # パターン1: コードブロック (```json ... ```) からの抽出し試行
        json_code_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_code_match:
            try:
                return json.loads(json_code_match.group(1))
            except json.JSONDecodeError:
                pass

        # パターン2: テキスト内の最も外側の中括弧 { ... } を探索
        curly_match = re.search(r"(\{[\s\S]*\})", text)
        if curly_match:
            try:
                return json.loads(curly_match.group(1))
            except json.JSONDecodeError:
                pass

        # パターン3: 全体を直接パース試行
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def _save_analysis_results(self, handler_result: Dict[str, Any]) -> None:
        """
        解析されたスコアと根拠論文データを JSON ファイルおよび JSONL 形式の履歴として追記保存する
        """
        try:
            content = handler_result.get("content", {})
            
            # 最新の集計結果ファイル (.json)
            latest_json_path = os.path.join(self.output_dir, "latest_analysis_score.json")
            with open(latest_json_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)

            # スコア履歴・エビデンス追記用ログ (.jsonl)
            history_jsonl_path = os.path.join(self.output_dir, "analysis_history.jsonl")
            with open(history_jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(content, ensure_ascii=False) + "\n")

            print(f"💾 [AnalysisOrchestrator] 解析データ（スコア・根拠）を保存完了: {latest_json_path}")
        except Exception as e:
            print(f"⚠️ [AnalysisOrchestrator] 保存処理失敗: {e}")


# スタンドアロン動作テスト
if __name__ == "__main__":
    import asyncio

    class DummyRequest:
        def __init__(self, message: str):
            self.message = message

    sample_message = """
    以下の論文を解析してください。
    ```json
    {
      "W4392162657": {
        "title": "Assessing urban livability in Shanghai...",
        "summary_ja": "住宅クラスター（RBC）を中心としたバッファ分析...",
        "key_method": "POIデータの密度と多様性を算出",
        "tags": ["POI", "バッファ分析"]
      }
    }
    ```
    """

    async def main():
        orchestrator = AnalysisOrchestrator(project_root=".")
        res_type, content = await orchestrator.execute(DummyRequest(sample_message))
        print("Response Type:", res_type)
        print("Response Content:", json.dumps(content, ensure_ascii=False, indent=2))

    asyncio.run(main())
