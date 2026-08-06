import json
from typing import Dict, Any, List

class PaperAnalysisHandler:
    """
    論文JSONデータを解析し、スコア指標とエビデンス（論文根拠）を構造化して
    フロントエンドの UI Block 形式で返却するハンドラー
    """

    def __init__(self):
        pass

    def analyze_papers(self, raw_json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        論文データを読み込み、スコアと根拠を計算・補完して UI レスポンスを生成する
        """
        parsed_results = []
        
        for paper_id, paper_info in raw_json_data.items():
            # 1. 欠損値のフォールバック・補完処理
            title = paper_info.get("title", "不明なタイトル")
            summary = paper_info.get("summary_ja") or "要約未生成（PDFから抽出が必要です）"
            key_method = paper_info.get("key_method") or "解析手法未定義"
            pdf_url = paper_info.get("pdf_url")
            tags = paper_info.get("tags", [])

            # 2. 論文に基づく評価スコアの算出（ルールベース/ロジック計算の例）
            # 実データ（アクセス性や手法の具体性など）に応じてスコア付け
            accessibility_score = 9.0 if "バッファ分析" in tags or "POI" in tags else 5.0
            data_richness_score = 8.5 if paper_info.get("relevance_opendata") else 4.0
            overall_score = round((accessibility_score + data_richness_score) / 2, 1)

            # 3. エビデンス一体型構造の構築
            parsed_results.append({
                "paper_id": paper_id,
                "title": title,
                "overall_score": overall_score,
                "metrics": {
                    "accessibility_score": accessibility_score,
                    "data_richness_score": data_richness_score
                },
                "evidence": {
                    "summary": summary,
                    "key_method": key_method,
                    "pdf_url": pdf_url,
                    "tags": tags
                }
            })

        # 4. 全体サマリーとスコアの集計
        total_papers = len(parsed_results)
        avg_score = round(sum(p["overall_score"] for p in parsed_results) / total_papers, 1) if total_papers > 0 else 0.0

        formatted_payload = {
            "summary_metrics": {
                "analyzed_count": total_papers,
                "average_score": avg_score,
            },
            "evaluations": parsed_results
        }

        # 5. フロントエンド (blocks.jsx / AiChatMessageList.jsx) が解釈できるレスポンスを返却
        return {
            "response_type": "ui_code",
            "content": {
                "message": f"論文データ（{total_papers}件）の解析が完了しました。スコアおよび証拠一覧を出力します。",
                "blocks": [
                    {
                        # blocks.jsx に登録されている 'conversion_jsonBlock' や 'JsonViewerBlock' を使用
                        "type": "conversion_jsonBlock", 
                        "props": {
                            "title": "論文評価＆エビデンススコア集計",
                            "data": formatted_payload
                        }
                    }
                ]
            }
        }


# スタンドアロンテスト用
if __name__ == "__main__":
    sample_input = {
        "W4392162657": {
            "title": "Assessing urban livability in Shanghai...",
            "summary_ja": "本研究は...住宅から1kmおよび2km圏内のアクセス性を可視化...",
            "key_method": "住宅クラスター（RBC）を中心としたバッファ分析",
            "relevance_opendata": "適用可能",
            "tags": ["POI", "バッファ分析"],
            "pdf_url": "https://www.nature.com/articles/s42949-024-00146-z.pdf"
        },
        "W4285801620": {
            "title": "An Integrated Approach for Developing...",
            "summary_ja": "",
            "key_method": "",
            "relevance_opendata": "",
            "tags": [],
            "pdf_url": "https://www.mdpi.com/2071-1050/14/14/8755/pdf"
        }
    }

    handler = PaperAnalysisHandler()
    result = handler.analyze_papers(sample_input)
    print(json.dumps(result, ensure_ascii=False, indent=2))
