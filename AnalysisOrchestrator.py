import os
import json
import re
import traceback
import base64
import io
from typing import Dict, Any, Tuple, Optional, Union
from PIL import Image

# QRコード解析用 (pyzbar) のインポート
try:
    from pyzbar.pyzbar import decode as decode_qr
    HAS_PYZBAR = True
except ImportError:
    HAS_PYZBAR = False

# ハンドラー類のインポート
try:
    from engine.handlers.paper_analysis_handler import PaperAnalysisHandler
except ImportError:
    PaperAnalysisHandler = None

try:
    from engine.handlers.google_sheets_analysis_handler import GoogleSheetsAnalysisHandler
except ImportError:
    GoogleSheetsAnalysisHandler = None


class AnalysisOrchestrator:
    """
    論文解析、スプレッドシート・在庫解析、QRコード/OCR解析、
    および成果物の永続化 (JSON/JSONL) と Chat UI Block レンダリングを統括するメインオーケストレーター
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        
        # ハンドラーの初期化
        self.paper_handler = PaperAnalysisHandler() if PaperAnalysisHandler else None
        self.sheets_handler = GoogleSheetsAnalysisHandler(low_stock_threshold=10) if GoogleSheetsAnalysisHandler else None
        
        # 中間・最終成果物の保存用ディレクトリ (.ai_memory/analysis_outputs)
        self.output_dir = os.path.join(self.project_root, "backend", ".ai_memory", "analysis_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

    async def execute(self, request: Any) -> Tuple[str, Dict[str, Any]]:
        """
        ChatService や API エンドポイントから呼び出されるメインエントリーポイント。

        Args:
            request: ChatRequest (Pydanticモデル) または辞書形式のリクエスト
                     (message, image, image_data, handler_type などのフィールドに対応)

        Returns:
            Tuple[str, Dict[str, Any]]: (response_type, content)
        """
        try:
            # 1. リクエストからのパラメータ抽出
            message_str, image_data, handler_type = self._extract_request_params(request)

            # 2. 画像が添付されている場合の QR コード読み取り試行
            scanned_qr_text = None
            if image_data:
                scanned_qr_text = self._extract_qr_from_image(image_data)
                if scanned_qr_text:
                    print(f"🔍 [AnalysisOrchestrator] 画像からQRコードを検出: {scanned_qr_text}")
                    # テキストメッセージにスキャン結果を追記
                    message_str = f"{message_str}\n{scanned_qr_text}".strip()

            # 3. テキストメッセージからの JSON 抽出
            parsed_data = self._extract_json_from_text(message_str)

            # 4. 適切なハンドラーの自動決定と実行
            handler_result = await self._route_and_execute_handler(
                parsed_data=parsed_data,
                raw_message=message_str,
                image_data=image_data,
                scanned_qr_text=scanned_qr_text,
                handler_type=handler_type
            )

            # 5. 解析結果の永続化保存（JSON / JSONL）
            self._save_analysis_results(handler_result)

            # 6. レスポンスフォーマットの返却
            response_type = handler_result.get("response_type", "ui_code")
            content = handler_result.get("content", {})

            return response_type, content

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"🚨 [AnalysisOrchestrator] 実行中にエラーが発生しました:\n{error_details}")

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

    def _extract_request_params(self, request: Any) -> Tuple[str, Optional[Any], Optional[str]]:
        """リクエストオブジェクト（Pydantic）または辞書からパラメータを安全に取り出す"""
        message_str = getattr(request, "message", None)
        image_data = getattr(request, "image", None) or getattr(request, "image_data", None)
        handler_type = getattr(request, "handler_type", None)

        if isinstance(request, dict):
            if message_str is None:
                message_str = request.get("message", "")
            if image_data is None:
                image_data = request.get("image") or request.get("image_data")
            if handler_type is None:
                handler_type = request.get("handler_type")

        return message_str or "", image_data, handler_type

    def _extract_qr_from_image(self, image_input: Any) -> Optional[str]:
        """Base64文字列またはバイナリ画像から pyzbar を使用して QR コードを解読する"""
        if not HAS_PYZBAR:
            print("⚠️ pyzbar が利用できないため、QRコードのスキャンをスキップします。")
            return None

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
            decoded_objects = decode_qr(image)

            if decoded_objects:
                # 最初に検出された QR コードのテキストを抽出
                return decoded_objects[0].data.decode("utf-8")

        except Exception as e:
            print(f"⚠️ [AnalysisOrchestrator] QR画像解析に失敗しました: {e}")

        return None

    def _extract_json_from_text(self, text: str) -> Union[Dict[str, Any], List[Any]]:
        """テキストに含まれる ```json ... ``` や生の JSON 文字列を安全に抽出・パースする"""
        if not text:
            return {}

        # パターン1: コードブロック (```json ... ```) からの抽出試行
        json_code_match = re.search(r"```(?:json)?\s*([\[\{][\s\S]*?[\]\}])\s*```", text)
        if json_code_match:
            try:
                return json.loads(json_code_match.group(1))
            except json.JSONDecodeError:
                pass

        # パターン2: 最も外側の { ... } または [ ... ] を探索
        curly_match = re.search(r"([\[\{][\s\S]*[\]\}])", text)
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

    async def _route_and_execute_handler(
        self,
        parsed_data: Any,
        raw_message: str,
        image_data: Optional[Any],
        scanned_qr_text: Optional[str],
        handler_type: Optional[str]
    ) -> Dict[str, Any]:
        """データ構造や明示的な指定に基づいて、適切な Handler へルーティング・実行する"""

        # A. Google Sheets / 在庫・OCR解析ハンドラーへの振分け判定
        is_sheets_target = (
            handler_type == "sheets"
            or (isinstance(parsed_data, dict) and ("sheet_name" in parsed_data or "data" in parsed_data))
            or isinstance(parsed_data, list)
            or (image_data is not None and not scanned_qr_text)  # OCR解析用の画像が存在する場合
        )

        if is_sheets_target and self.sheets_handler:
            print("🔀 [AnalysisOrchestrator] GoogleSheetsAnalysisHandler へルーティング")
            input_payload = parsed_data if parsed_data else raw_message
            return self.sheets_handler.analyze_sheets(sheets_input=input_payload, image_input=image_data)

        # B. 論文解析ハンドラーへの振分け
        if self.paper_handler and parsed_data:
            print("🔀 [AnalysisOrchestrator] PaperAnalysisHandler へルーティング")
            return self.paper_handler.analyze_papers(parsed_data)

        # C. どちらのデータも検出できなかった場合のエラーレスポンス構築
        error_msg = "⚠️ **解析対象のデータが検出できませんでした**\n\nJSON形式のテキスト（論文・在庫データ等）の入力、または画像データ/QRコードの送信を行ってください。"
        return {
            "response_type": "ui_code",
            "content": {
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
        }

    def _save_analysis_results(self, handler_result: Dict[str, Any]) -> None:
        """解析されたスコア・集計結果データを JSON ファイルおよび JSONL ログとして追記保存する"""
        try:
            content = handler_result.get("content", {})
            if not content:
                return

            # 最新の集計結果ファイル (.json)
            latest_json_path = os.path.join(self.output_dir, "latest_analysis_score.json")
            with open(latest_json_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)

            # 解析履歴・ログファイル (.jsonl)
            history_jsonl_path = os.path.join(self.output_dir, "analysis_history.jsonl")
            with open(history_jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(content, ensure_ascii=False) + "\n")

            print(f"💾 [AnalysisOrchestrator] 解析データを保存しました: {latest_json_path}")
        except Exception as e:
            print(f"⚠️ [AnalysisOrchestrator] 結果の保存処理に失敗しました: {e}")


# スタンドアロンテスト用実行処理
if __name__ == "__main__":
    import asyncio

    class DummyRequest:
        def __init__(self, message: str = "", image: Optional[str] = None, handler_type: Optional[str] = None):
            self.message = message
            self.image = image
            self.handler_type = handler_type

    sample_sheets_message = """
    以下の在庫データを解析してください。
    ```json
    {
      "sheet_name": "リアルタイム棚卸しデータ",
      "data": [
        {"商品コード": "P001", "商品名": "高精度ワイヤレスマウス", "在庫数": 3, "単価": 4980},
        {"商品コード": "P002", "商品名": "4K 27インチモニター", "在庫数": 15, "単価": 45000},
        {"商品コード": "P003", "商品名": "メカニカルキーボード", "在庫数": 2, "単価": 12800}
      ]
    }
    ```
    """

    async def main():
        orchestrator = AnalysisOrchestrator(project_root=".")
        res_type, content = await orchestrator.execute(DummyRequest(message=sample_sheets_message))
        print("Response Type:", res_type)
        print("Response Content:\n", json.dumps(content, ensure_ascii=False, indent=2))

    asyncio.run(main())
