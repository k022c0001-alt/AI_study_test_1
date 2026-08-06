# backend/api/services/handlers/ConversionJsonHandler.py の成功時の return を変更

if success:
    return {
        # AiChatMessageList.jsx で UIブロック として認識させるための魔法の言葉
        "response_type": "ui_code",
        "message": f"ファイルの翻訳が完了し、`{new_file_path}` に保存しました。",
        
        # blocks.jsx に渡すブロックの配列
        "blocks": [
            {
                # blocks.jsx で登録した名前と完全一致させる
                "type": "conversion_jsonBlock", 
                "props": {
                    "status": "success",
                    "new_file_path": new_file_path,
                    "json_content": parsed_json  # 翻訳済みの辞書データ
                }
            }
        ]
    }
else:
    return {
        "response_type": "ui_code",
        "message": "エラーが発生しました。",
        "blocks": [
            {
                "type": "conversion_jsonBlock",
                "props": {
                    "status": "error",
                    "message": "ファイルの保存に失敗しました。"
                }
            }
        ]
    }
