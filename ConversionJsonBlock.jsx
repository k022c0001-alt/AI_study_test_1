// frontend/src/components/blocks/conversion_jsonBlock.jsx
import React, { useState } from 'react';

export default function ConversionJsonBlock({ block, ...props }) {
  // バックエンドからのデータを配列として正規化
  // 新しい複数ファイル対応の場合は props.results が来る。
  // 古い単一ファイル対応の場合は props そのものを配列の1要素とする。
  const results = props.results || (props.status ? [props] : []);

  if (!results || results.length === 0) {
    return (
      <div className="p-4 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-500 text-sm">
        表示する処理結果がありません。
      </div>
    );
  }

  const successCount = results.filter(r => r.status === 'success').length;
  const errorCount = results.filter(r => r.status === 'error').length;

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden bg-white dark:bg-slate-900 shadow-sm w-full">
      
      {/* ヘッダー部分（サマリー） */}
      <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 p-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🌐</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              JSON 翻訳完了
            </h3>
            <div className="flex items-center gap-2 mt-1 text-xs font-mono">
              <span className="text-slate-500 dark:text-slate-400">
                Total: {results.length} files
              </span>
              {successCount > 0 && (
                <span className="px-1.5 py-0.5 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded">
                  ✓ {successCount} Success
                </span>
              )}
              {errorCount > 0 && (
                <span className="px-1.5 py-0.5 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded">
                  🚨 {errorCount} Error
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* 処理結果リスト（大量になっても大丈夫なようにスクロール領域化） */}
      <div className="max-h-96 overflow-y-auto p-2">
        <ul className="space-y-2">
          {results.map((item, index) => (
            <ResultItem key={index} item={item} />
          ))}
        </ul>
      </div>
    </div>
  );
}

// 各ファイルの結果を表示するサブコンポーネント
function ResultItem({ item }) {
  const isSuccess = item.status === 'success';
  const [isCopied, setIsCopied] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  // もしJSONの生データが渡されていればコピー機能を提供する
  const hasJsonContent = !!item.json_content;

  const handleCopy = (e) => {
    e.stopPropagation();
    if (!item.json_content) return;
    const textToCopy = typeof item.json_content === 'string' 
      ? item.json_content 
      : JSON.stringify(item.json_content, null, 2);
    
    navigator.clipboard.writeText(textToCopy);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <li className="border border-slate-100 dark:border-slate-800 rounded-md overflow-hidden bg-slate-50/50 dark:bg-slate-800/50">
      
      {/* リストの行（ヘッダー） */}
      <div 
        className={`flex items-start justify-between p-3 ${hasJsonContent ? 'cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800' : ''}`}
        onClick={() => hasJsonContent && setIsOpen(!isOpen)}
      >
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <span className="mt-0.5 text-sm shrink-0">
            {isSuccess ? <span className="text-green-500">✓</span> : <span className="text-red-500">✗</span>}
          </span>
          
          <div className="flex-1 min-w-0">
            {/* オリジナルパス (あれば) */}
            {item.original_path && (
              <p className="text-xs text-slate-400 dark:text-slate-500 truncate mb-0.5">
                {item.original_path}
              </p>
            )}
            
            {/* 新しいパス または エラーメッセージ */}
            {isSuccess ? (
              <p className="text-sm font-mono text-slate-700 dark:text-slate-300 truncate">
                {item.new_file_path || '変換成功 (パス不明)'}
              </p>
            ) : (
              <p className="text-sm text-red-600 dark:text-red-400">
                {item.message || "翻訳処理中にエラーが発生しました。"}
              </p>
            )}
          </div>
        </div>

        {/* JSONデータが含まれている場合のみコピー＆開閉ボタンを表示 */}
        {hasJsonContent && isSuccess && (
          <div className="flex items-center gap-2 shrink-0 ml-4">
            <button
              onClick={handleCopy}
              className="p-1.5 text-xs rounded-md bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 hover:bg-slate-100 transition-colors"
              title="JSONをコピー"
            >
              {isCopied ? <span className="text-green-500">✓</span> : <span>📋</span>}
            </button>
            <span className="text-slate-400 text-xs">
              {isOpen ? '▲' : '▼'}
            </span>
          </div>
        )}
      </div>

      {/* JSONプレビュー部分（アコーディオン） */}
      {hasJsonContent && isOpen && (
        <div className="border-t border-slate-200 dark:border-slate-700">
          <pre className="text-[11px] p-3 overflow-x-auto bg-slate-950 text-slate-300 font-mono leading-relaxed m-0 max-h-64">
            <code>
              {typeof item.json_content === 'string' 
                ? item.json_content 
                : JSON.stringify(item.json_content, null, 2)}
            </code>
          </pre>
        </div>
      )}
    </li>
  );
}
