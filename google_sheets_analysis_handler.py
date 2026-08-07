import os
import json
import re
import io
import base64
import traceback
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
from PIL import Image

# OCR用ライブラリの読み込み（未アクセスの場合はエラーハンドリング）
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False


class GoogleSheetsAnalysisHandler:
    """
    Googleスプレッドシートデータ（JSON/辞書/CSV）および
    画像データ（OCRによる表文字起こし）をパース・解析し、
    集計サマリー・在庫アラート・UI Blockレスポンスを生成するハンドラー
    """

    def __init__(self, low_stock_threshold: int = 10, tesseract_cmd: Optional[str] = None):
        """
        Args:
            low_stock_threshold (int): 在庫不足アラートの閾値（デフォルト: 10）
            tesseract_cmd (str): tesseract実行ファイルのパス指定（必要な場合）
        """
        self.low_stock_threshold = low_stock_threshold
        if tesseract_cmd and HAS_PYTESSERACT:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def analyze_sheets(self, sheets_input: Any = None, image_input: Optional[Any] = None) -> Dict[str, Any]:
        """
        メインエントリーポイント。

        Args:
            sheets_input: JSON, リスト, 辞書, CSV文字列など
            image_input: 画像のBase64文字列、バイナリデータ、またはPIL Image

        Returns:
            Dict[str, Any]: response_type と content (UI Blocks含む)
        """
        try:
            df = None
            sheet_name = "シートデータ"

            # 1. 画像入力がある場合は OCR を実行してデータフレーム化
            if image_input or (isinstance(sheets_input, dict) and "image" in sheets_input):
                img_data = image_input or sheets_input.get("image")
                df, sheet_name = self._ocr_image_to_dataframe(img_data)
                
            # 2. テキスト・JSONデータからのパース
            if df is None and sheets_input is not None:
                df, sheet_name = self._parse_to_dataframe(sheets_input)

            # データが読み込めなかった場合のガード
            if df is None or df.empty:
                return self._build_error_response("解析可能な表データまたは画像を検出できませんでした。")

            # 3. 基本データ統計の算出
            summary = self._generate_data_summary(df, sheet_name)

            # 4. 異常値・在庫アラート・注意点の抽出
            alerts = self._detect_alerts_and_insights(df)

            # 5. Chat UI 用の表示ブロック（Markdownやテーブル等）の構築
            blocks = self._build_ui_blocks(summary, alerts, df)

            return {
                "response_type": "ui_code",
                "content": {
                    "message": f"📊 解析が完了しました（データソース: {sheet_name}）",
                    "summary": summary,
                    "alerts": alerts,
                    "blocks": blocks
                }
            }

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"🚨 [GoogleSheetsAnalysisHandler] エラーが発生しました:\n{error_details}")
            return self._build_error_response(f"データ解析中に例外が発生しました: {str(e)}")

    def _ocr_image_to_dataframe(self, image_input: Any) -> Tuple[Optional[pd.DataFrame], str]:
        """画像データに対してOCRを実行し、表構造のテキストを生成してDataFrameに変換する"""
        if not HAS_PYTESSERACT:
            print("⚠️ pytesseract が利用できません。`pip install pytesseract pillow` を確認してください。")
            return None, "OCRエラー"

        try:
            # 1. 入力画像を PIL Image オブジェクトに変換
            image = None
            if isinstance(image_input, str):
                # Base64 文字列のプレフィックス除去
                if "," in image_input:
                    image_input = image_input.split(",", 1)[1]
                image_bytes = base64.b64decode(image_input)
                image = Image.open(io.BytesIO(image_bytes))
            elif isinstance(image_input, bytes):
                image = Image.open(io.BytesIO(image_input))
            elif isinstance(image_input, Image.Image):
                image = image_input

            if image is None:
                return None, "画像読み込み失敗"

            # 2. Tesseract OCR の実行（日本語＋英語）
            ocr_text = pytesseract.image_to_string(image, lang='jpn+eng')
            
            if not ocr_text.strip():
                return None, "OCR空表示"

            # 3. テキストを行ごとに分解し、表形式として構造化パース
            lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
            parsed_rows = []
            
            for line in lines:
                # タブ、2文字以上のスペース、カンマ、パイプ(|)でカラムを分割
                row = re.split(r'\t|\s{2,}|,|\|', line)
                row = [cell.strip() for cell in row if cell.strip()]
                if row:
                    parsed_rows.append(row)

            if not parsed_rows:
                return None, "OCR表パース失敗"

            # 1行目をヘッダー（カラム名）、2行目以降をデータとして DataFrame 化
            headers = parsed_rows[0]
            data_rows = parsed_rows[1:]

            # カラム数の一致を補正
            valid_rows = []
            for r in data_rows:
                if len(r) == len(headers):
                    valid_rows.append(r)
                elif len(r) < len(headers):
                    # 足りない列を空文字で埋める
                    valid_rows.append(r + [""] * (len(headers) - len(r)))
                else:
                    # 多すぎる列を切り捨てる
                    valid_rows.append(r[:len(headers)])

            df = pd.DataFrame(valid_rows, columns=headers)

            # 数値型カラムの自動変換試行
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='ignore')

            return df, "OCR解析画像"

        except Exception as e:
            print(f"⚠️ [OCR解析エラー]: {e}")
            return None, "OCR処理例外"

    def _parse_to_dataframe(self, sheets_input: Any) -> Tuple[Optional[pd.DataFrame], str]:
        """JSON/辞書/リスト/CSV形式の入力データを DataFrame に変換"""
        sheet_name = "スプレッドシート"

        if isinstance(sheets_input, dict):
            sheet_name = sheets_input.get("sheet_name", sheet_name)
            data = sheets_input.get("data", sheets_input.get("rows", sheets_input))
            if isinstance(data, list):
                return pd.DataFrame(data), sheet_name
            elif isinstance(data, dict):
                return pd.DataFrame.from_dict(data, orient="index"), sheet_name

        elif isinstance(sheets_input, list):
            return pd.DataFrame(sheets_input), sheet_name

        elif isinstance(sheets_input, str):
            try:
                parsed_json = json.loads(sheets_input)
                return self._parse_to_dataframe(parsed_json)
            except json.JSONDecodeError:
                pass

        return None, sheet_name

    def _generate_data_summary(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """データ全体のサマリー情報を生成"""
        total_rows = len(df)
        total_cols = len(df.columns)
        col_names = list(df.columns)

        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        numeric_summary = {}

        for col in numeric_cols:
            numeric_summary[col] = {
                "total": float(df[col].sum()),
                "mean": round(float(df[col].mean()), 2),
                "min": float(df[col].min()),
                "max": float(df[col].max())
            }

        return {
            "sheet_name": sheet_name,
            "total_records": total_rows,
            "total_columns": total_cols,
            "columns": col_names,
            "numeric_summary": numeric_summary,
            "missing_count": int(df.isnull().sum().sum())
        }

    def _detect_alerts_and_insights(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """在庫不足や欠損値などのアラートを検出"""
        alerts = []
        stock_cols = [c for c in df.columns if any(k in str(c).lower() for k in ["在庫", "stock", "数量", "count"])]
        
        for col in stock_cols:
            # 数値型に変換可能な場合の判定
            numeric_series = pd.to_numeric(df[col], errors='coerce')
            if not numeric_series.isnull().all():
                low_stock_mask = numeric_series <= self.low_stock_threshold
                low_stock_items = df[low_stock_mask]
                
                if not low_stock_items.empty:
                    item_names = []
                    name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ["名", "品", "item", "title", "code", "コード"])]
                    name_col = name_cols[0] if name_cols else df.columns[0]

                    for idx, row in low_stock_items.iterrows():
                        val = numeric_series[idx]
                        item_names.append(f"{row[name_col]} (残り: {val})")

                    alerts.append({
                        "level": "warning",
                        "title": f"⚠️ 在庫不足アラート ({col})",
                        "description": f"発注点（{self.low_stock_threshold}個以下）を下回っている項目:",
                        "items": item_names[:10]
                    })

        return alerts

    def _build_ui_blocks(self, summary: Dict[str, Any], alerts: List[Dict[str, Any]], df: pd.DataFrame) -> List[Dict[str, Any]]:
        """UI表示用ブロックの生成"""
        blocks = []

        summary_md = f"### 📊 データ概要 [{summary['sheet_name']}]\n"
        summary_md += f"- **行数**: `{summary['total_records']} 行` | **列数**: `{summary['total_columns']} 列`\n"
        summary_md += f"- **項目名**: {', '.join([f'`{c}`' for c in summary['columns']])}\n"

        if summary["numeric_summary"]:
            summary_md += "\n#### 📈 自動集計（数値項目）\n"
            for col, stats in summary["numeric_summary"].items():
                summary_md += f"- **{col}**: 合計 `{stats['total']}` / 平均 `{stats['mean']}` (最小 `{stats['min']}` 〜 最大 `{stats['max']}`)\n"

        blocks.append({
            "type": "MarkdownChatBlock",
            "props": {"content": summary_md}
        })

        if alerts:
            alert_md = "### 🚨 検出された警告・通知\n"
            for alert in alerts:
                alert_md += f"#### {alert['title']}\n{alert['description']}\n"
                if alert.get("items"):
                    for item in alert["items"]:
                        alert_md += f"- {item}\n"
                alert_md += "\n"

            blocks.append({
                "type": "MarkdownChatBlock",
                "props": {"content": alert_md}
            })

        preview_data = df.head(5).to_dict(orient="records")
        blocks.append({
            "type": "TableChatBlock",
            "props": {
                "title": "📋 解析データプレビュー（先頭5行）",
                "columns": summary["columns"],
                "rows": preview_data
            }
        })

        return blocks

    def _build_error_response(self, error_message: str) -> Dict[str, Any]:
        return {
            "response_type": "ui_code",
            "content": {
                "message": "データ解析に失敗しました。",
                "blocks": [
                    {
                        "type": "MarkdownChatBlock",
                        "props": {"content": f"❌ **エラー:** {error_message}"}
                    }
                ]
            }
        }
