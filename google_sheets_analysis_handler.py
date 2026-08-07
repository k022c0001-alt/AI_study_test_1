import os
import json
import traceback
from typing import Dict, Any, List, Optional, Union
import pandas as pd


class GoogleSheetsAnalysisHandler:
    """
    Googleスプレッドシート（またはスプレッドシート由来の行データ・JSON）を解析し、
    集計サマリー、異常・在庫アラート検知、および UI Block 用レスポンスを生成するハンドラー
    """

    def __init__(self, low_stock_threshold: int = 10):
        """
        Args:
            low_stock_threshold (int): 在庫不足アラートを出す閾値（デフォルト: 10）
        """
        self.low_stock_threshold = low_stock_threshold

    def analyze_sheets(self, sheets_input: Any) -> Dict[str, Any]:
        """
        メインエントリーポイント。

        Args:
            sheets_input: 
                - リスト形式: [{"商品コード": "A001", "商品名": "りんご", "在庫数": 5}, ...]
                - 辞書形式: {"sheet_name": "在庫一覧", "data": [...]}
                - CSV文字列など

        Returns:
            Dict[str, Any]: response_type と content (UI Blocks含む)
        """
        try:
            # 1. 入力データを pandas DataFrame に変換
            df, sheet_name = self._parse_to_dataframe(sheets_input)

            if df is None or df.empty:
                return self._build_error_response("解析対象のスプレッドシートデータが空か、正しい形式ではありません。")

            # 2. 基本データ統計の算出
            summary = self._generate_data_summary(df, sheet_name)

            # 3. 異常値・在庫アラート・注意点の抽出
            alerts = self._detect_alerts_and_insights(df)

            # 4. Chat UI 用の表示ブロック（Markdownやテーブル等）の構築
            blocks = self._build_ui_blocks(summary, alerts, df)

            return {
                "response_type": "ui_code",
                "content": {
                    "message": f"📊 Googleスプレッドシート[{sheet_name}]の解析が完了しました。",
                    "summary": summary,
                    "alerts": alerts,
                    "blocks": blocks
                }
            }

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"🚨 [GoogleSheetsAnalysisHandler] エラーが発生しました:\n{error_details}")
            return self._build_error_response(f"スプレッドシート解析中に例外が発生しました: {str(e)}")

    def _parse_to_dataframe(self, sheets_input: Any) -> tuple[Optional[pd.DataFrame], str]:
        """入力データを pandas DataFrame に正規化する"""
        sheet_name = "シート1"

        if isinstance(sheets_input, dict):
            sheet_name = sheets_input.get("sheet_name", sheet_name)
            data = sheets_input.get("data", sheets_input.get("rows", sheets_input))
            if isinstance(data, list):
                return pd.DataFrame(data), sheet_name
            elif isinstance(data, dict):
                # 辞書型のリスト（例: {"商品A": {...}, "商品B": {...}}）
                return pd.DataFrame.from_dict(data, orient="index"), sheet_name

        elif isinstance(sheets_input, list):
            return pd.DataFrame(sheets_input), sheet_name

        elif isinstance(sheets_input, str):
            # JSON文字列のパース試行
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

        # 数値カラムの特定と簡易集計
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

        # 1. 「在庫」「数量」「stock」などのカラムが存在する場合のアラートチェック
        stock_cols = [c for c in df.columns if any(k in c.lower() for k in ["在庫", "stock", "数量", "count"])]
        
        for col in stock_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                low_stock_items = df[df[col] <= self.low_stock_threshold]
                if not low_stock_items.empty:
                    item_names = []
                    # 商品名・品名を表すカラムを特定
                    name_cols = [c for c in df.columns if any(k in c.lower() for k in ["名", "品", "item", "title", "code", "コード"])]
                    name_col = name_cols[0] if name_cols else df.columns[0]

                    for _, row in low_stock_items.iterrows():
                        item_names.append(f"{row[name_col]} (残り: {row[col]})")

                    alerts.append({
                        "level": "warning",
                        "title": f"⚠️ 在庫不足アラート ({col})",
                        "description": f"以下の商品が発注点（{self.low_stock_threshold}個以下）を下回っています。",
                        "items": item_names[:10]  # 最大10件表示
                    })

        # 2. 欠損値（空欄）のチェック
        missing_info = df.isnull().sum()
        missing_cols = missing_info[missing_info > 0]
        if not missing_cols.empty:
            missing_details = [f"・{col}: {count}件の空欄" for col, count in missing_cols.items()]
            alerts.append({
                "level": "info",
                "title": "ℹ️ データの未記入（欠損値）を検出",
                "description": "一部のセルにデータが未入力です。確認・補完をおすすめします。",
                "items": missing_details
            })

        return alerts

    def _build_ui_blocks(self, summary: Dict[str, Any], alerts: List[Dict[str, Any]], df: pd.DataFrame) -> List[Dict[str, Any]]:
        """UI表示用（UI Blocks）の構造化データを構築"""
        blocks = []

        # 1. 基本サマリーマークダウン
        summary_md = f"### 📊 スプレッドシート概要 [{summary['sheet_name']}]\n"
        summary_md += f"- **総レコード数**: `{summary['total_records']} 件` | **項目数**: `{summary['total_columns']} 列`\n"
        summary_md += f"- **カラム一覧**: {', '.join([f'`{c}`' for c in summary['columns']])}\n"

        if summary["numeric_summary"]:
            summary_md += "\n#### 📈 数値項目の自動集計\n"
            for col, stats in summary["numeric_summary"].items():
                summary_md += f"- **{col}**: 合計 `{stats['total']}` / 平均 `{stats['mean']}` (最小 `{stats['min']}` 〜 最大 `{stats['max']}`)\n"

        blocks.append({
            "type": "MarkdownChatBlock",
            "props": {
                "content": summary_md
            }
        })

        # 2. アラート・アドバイス表示ブロック
        if alerts:
            alert_md = "### 🚨 検出された注意・AI助言\n"
            for alert in alerts:
                alert_md += f"#### {alert['title']}\n{alert['description']}\n"
                if alert.get("items"):
                    for item in alert["items"]:
                        alert_md += f"- {item}\n"
                alert_md += "\n"

            blocks.append({
                "type": "MarkdownChatBlock",
                "props": {
                    "content": alert_md
                }
            })

        # 3. データプレビューテーブル（先頭5件）
        preview_data = df.head(5).to_dict(orient="records")
        blocks.append({
            "type": "TableChatBlock",
            "props": {
                "title": "📋 データプレビュー（先頭5件）",
                "columns": summary["columns"],
                "rows": preview_data
            }
        })

        return blocks

    def _build_error_response(self, error_message: str) -> Dict[str, Any]:
        """エラー応答フォーマット"""
        return {
            "response_type": "ui_code",
            "content": {
                "message": "スプレッドシート解析に失敗しました。",
                "blocks": [
                    {
                        "type": "MarkdownChatBlock",
                        "props": {
                            "content": f"❌ **エラー:** {error_message}"
                        }
                    }
                ]
            }
        }


# 単体テスト用コード
if __name__ == "__main__":
    handler = GoogleSheetsAnalysisHandler(low_stock_threshold=5)

    # テストデータ（スプレッドシートから読み込んだデータを模したもの）
    sample_sheets_data = {
        "sheet_name": "店舗在庫データ_2026",
        "data": [
            {"商品コード": "A001", "商品名": "ワイヤレスマウス", "分類": "ガジェット", "在庫数": 12, "単価": 2980},
            {"商品コード": "A002", "商品名": "メカニカルキーボード", "分類": "ガジェット", "在庫数": 3, "単価": 12800},
            {"商品コード": "A003", "商品名": "USB-C ハブ", "分類": "アクセサリ", "在庫数": 2, "単価": 4500},
            {"商品コード": "A004", "商品名": "27インチモニター", "分類": "ディスプレイ", "在庫数": 15, "単価": 34800},
            {"商品コード": "A005", "商品名": "エルゴノミクスチェア", "分類": "家具", "在庫数": 0, "単価": 49800}
        ]
    }

    result = handler.analyze_sheets(sample_sheets_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
