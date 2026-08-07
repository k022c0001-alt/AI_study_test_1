// frontend/src/components/blocks/conversion_jsonBlock.jsx
import React from 'react';

export default function ConversionJsonBlock({ block, ...props }) {
  const results = props.results || (props.status ? [props] : []);
  const { zip_download_url } = props;

  if (!results || results.length === 0) {
    return <div className="p-4 text-slate-500 text-sm">処理結果がありません。</div>;
  }

  const successCount = results.filter(r => r.status === 'success').length;
  const errorCount = results.filter(r => r.status === 'error').length;

  // 🌟 ZIPを一括ダウンロードする関数
  const handleDownloadZip = () => {
    if (!zip_download_url) return;
    
    // aタグを動的に生成してクリックをシミュレートし、ダウンロードを発火
    const link = document.createElement('a');
    link.href = zip_download_url;
    link.download = 'translated_jsons.zip'; // ダウンロード時のデフォルトファイル名
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden bg-white dark:bg-slate-900 shadow-sm w-full">
      
      {/* ヘッダー部分 */}
      <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 p-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <span className="text-2xl">📦</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              翻訳ファイル生成完了
            </h3>
            <div className="text-xs text-slate-500 mt-1">
              成功: {successCount}件 {errorCount > 0 && `| エラー: ${errorCount}件`}
            </div>
          </div>
        </div>

        {/* 🌟 一括ダウンロードボタン */}
        {zip_download_url && successCount > 0 && (
          <button
            onClick={handleDownloadZip}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md shadow-sm transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            ZIPをダウンロード
          </button>
        )}
      </div>
      
      {/* 処理結果リスト（パスのみ表示、中身のプレビューは省略） */}
      <div className="max-h-64 overflow-y-auto p-2 bg-slate-50 dark:bg-slate-800/50">
        <ul className="space-y-1">
          {results.map((item, index) => (
            <li key={index} className="flex items-center gap-2 text-xs p-2 border-b border-slate-100 dark:border-slate-700 last:border-0">
              {item.status === 'success' ? (
                <span className="text-green-500 shrink-0">✓</span>
              ) : (
                <span className="text-red-500 shrink-0">✗</span>
              )}
              <div className="flex-1 truncate">
                <span className="text-slate-500">{item.original_path}</span>
                {item.status === 'success' && (
                  <>
                    <span className="mx-2 text-slate-300">→</span>
                    <span className="font-mono text-slate-700 dark:text-slate-300">{item.new_file_path}</span>
                  </>
                )}
                {item.status === 'error' && (
                  <span className="ml-2 text-red-500">{item.message}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
