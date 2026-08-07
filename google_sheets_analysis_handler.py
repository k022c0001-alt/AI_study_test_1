import os
import json
import re
import traceback
import base64
import io
from typing import Dict, Any, Tuple, Optional
from PIL import Image
from pyzbar.pyzbar import decode

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
                     (message フィールドに加え、image や image_data フィールドに対応)

        Returns:
            Tuple[str, Dict[str, Any]]: (response_type, content)
        """
        try:
            # 1. リクエストメッセージおよび画像データの取り出し
            message_str = getattr(request, "message", None)
            image_data = getattr(request, "image", None) or getattr(request, "image_data", None)

            if isinstance(request, dict):
                if message_str is None:
                    message_str = request.get("message", "")
                if image_data is None:
                    image_data = request.get("image") or request.get("image_data")

            # 2. 画像が送信されている場合は QR コードの解析を実行
            scanned_qr_data = None
            if image_data:
                scanned_qr_data = self._extract_qr_from_image(image_data)
                if scanned_qr_data:
                    print(f"🔍 [AnalysisOrchestrator] 画像からQRコードを検出: {scanned_qr_data}")
                    # テキストメッセージ側にQRコードの解析結果を結合
                    message_str = f"{message_str}\n{scanned_qr_data}".strip()

            # 3. メッセージ文字列から JSON データの自動抽出
            papers_data = self._extract_json_from_text(message_str)

            # JSONデータが存在せず、かつQRコードも読み取れなかった場合のガード表示
            if not papers_data:
                error_msg = "⚠️ **JSONデータまたは有効なQRコードが検出できませんでした**\n\nデータを含むJSONテキスト、またはQRコード画像を送信してください。"
                if image_data and not scanned_qr_data:
                    error_msg = "⚠️ **画像からQRコードを読み取れませんでした**\n\n画像が鮮明か、または直接JSONデータテキストを入力してください。"

                return "ui_code", {
                    "message": "解析対象のデータが見つかりませんでした。",
                    "blocks": [
                        {
                            "type": "MarkdownChatBlock",
                            "props": {
                                "content": error_msg
                            }
                        }
                    ]
                }

            # 4. Handler を呼び出してスコアリングおよび UI ブロック用のデータを生成
            handler_result = self.handler.analyze_papers(papers_data)

            # 5. スコア結果・根拠の保存（JSON / JSONL への永続化）
            self._save_analysis_results(handler_result)

            # 6. response_type と content を取得して返却
            response_type = handler_result.get("response_type", "ui_code")
            content = handler_result.get("content", {})

            return response_type, content

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"🚨 [AnalysisOrchestrator] エラー発生:\n{error_details}")

            return "ui_code", {
                "message": "解析処理の実行中にエラーが発生しました。",
                "blocks": [
                    {
                        "type": "MarkdownChatBlock",
                        "props": {
                            "content": f"❌ **処理エラーの詳細:**\n```\n{str(e)}\n```"
                        }
                    }
                ]
            }

    def _extract_qr_from_image(self, image_input: Any) -> Optional[str]:
        """
        Base64文字列またはバイナリの画像データから pyzbar を使ってQRコードを抽出しテキスト化する
        """
        try:
            image_bytes = None

            if isinstance(image_input, str):
                # Data URI 形式 ("data:image/png;base64,...") のヘッダー除去
                if "," in image_input:
                    image_input = image_input.split(",", 1)[1]
                image_bytes = base64.b64decode(image_input)
            elif isinstance(image_input, bytes):
                image_bytes = image_input

            if not image_bytes:
                return None

            image = Image.open(io.BytesIO(image_bytes))
            decoded_objects = decode(image)

            if decoded_objects:
                # 最初に読み取れたQRコードの内容を返す
                return decoded_objects[0].data.decode("utf-8")

        except Exception as e:
            print(f"⚠️ [AnalysisOrchestrator] QR画像解析に失敗しました: {e}")

        return None

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
        解析されたスコアと根拠データを JSON ファイルおよび JSONL 形式の履歴として追記保存する
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

            print(f"💾 [AnalysisOrchestrator] 解析データを保存完了: {latest_json_path}")
        except Exception as e:
            print(f"⚠️ [AnalysisOrchestrator] 保存処理失敗: {e}")


# スタンドアロン動作テスト
if __name__ == "__main__":
    import asyncio

    class DummyRequest:
        def __init__(self, message: str = "", image: Optional[str] = None):
            self.message = message
            self.image = image

    sample_message = """
    以下のデータを解析してください。
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
        res_type, content = await orchestrator.execute(DummyRequest(message=sample_message))
        print("Response Type:", res_type)
        print("Response Content:", json.dumps(content, ensure_ascii=False, indent=2))

    asyncio.run(main())
