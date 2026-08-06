// frontend/src/components/blocks/conversion_jsonBlock.jsx
import React, { useState } from 'react';

export default function ConversionJsonBlock({ block, ...props }) {
  const [isCopied, setIsCopied] = useState(false);
  
  // バックエンドから渡されるプロパティを受け取る
  const { status, new_file_path, json_content, message } = props;

  // JSONコピー機能
  const handleCopy = () => {
    const textToCopy = typeof json_content === 'string' 
      ? json_content 
      : JSON.stringify(json_content, null, 2);
    
    navigator.clipboard.writeText(textToCopy);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // エラー時の表示
  if (status === 'error') {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
        <p className="font-bold mb-1">🚨 翻訳エラー</p>
        <p>{message || "JSONの翻訳処理中にエラーが発生しました。"}</p>
      </div>
    );
  }

  // JSONを整形して文字列化
  const displayJson = typeof json_content === 'string' 
    ? json_content 
    : JSON.stringify(json_content, null, 2);

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden bg-white dark:bg-slate-900 shadow-sm w-full">
      
      {/* ヘッダー部分（ファイル名とコピーボタン） */}
      <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 p-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <span className="text-xl">🌐</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              翻訳完了
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">
              {new_file_path}
            </p>
          </div>
        </div>
        
        <button
          onClick={handleCopy}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors flex items-center gap-1.5"
        >
          {isCopied ? (
            <><span className="text-green-500">✓</span> Copied!</>
          ) : (
            <><span className="text-slate-500">📋</span> Copy</>
          )}
        </button>
      </div>
      
      {/* JSONプレビュー部分 */}
      <div className="relative">
        <div className="absolute top-0 right-0 p-2 text-[10px] text-slate-500 font-mono">
          JSON
        </div>
        <pre className="text-xs p-4 overflow-x-auto bg-slate-950 text-slate-300 font-mono leading-relaxed m-0 max-h-96">
          <code>{displayJson}</code>
        </pre>
      </div>
      
    </div>
  );
}
