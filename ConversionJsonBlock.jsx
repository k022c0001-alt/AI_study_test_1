// frontend/src/components/blocks/conversion_jsonBlock.jsx
import React from 'react';

export default function ConversionJsonBlock({ block, ...props }) {
  // バックエンドからのデータを配列として正規化
  // 新しい複数ファイル対応の場合は props.results が来る。
  // 古い単一ファイル対応の場合は props そのものを配列の1要素として扱う（後方互換性）
  const results = props.results || (props.status ? [props] : []);
  const { zip_download_url } = props;

  // 処理結果がない場合のフォールバック
  if (!results || results.length === 0) {
    return (
      <div className="p-4 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-500 text-sm">
        表示する処理結果がありません。
      </div>
    );
  }

  // 成功・失敗のカウント
  const successCount = results.filter(r => r.status === 'success').length;
  const errorCount = results.filter(r => r.status === 'error').length;

  // 🌟 ZIPを一括ダウンロードする関数
  const handleDownloadZip = () => {
    if (!zip_download_url) return;
    
    // aタグを動的に生成してクリックをシミュレートし、ダウンロードを発火させる
    const link = document.createElement('a');
    link.href = zip_download_url;
    link.download = 'translated_jsons.zip'; // ダウンロード時のデフォルトファイル名
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden bg-white dark:bg-slate-900 shadow-sm w-full">
      
      {/* ヘッダー部分（サマリーとダウンロードボタン） */}
      <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 p-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <span className="text-2xl">📦</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              翻訳ファイル生成完了
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

        {/* 🌟 一括ダウンロードボタン（ZIP URLがあり、成功したファイルがある場合のみ表示） */}
        {zip_download_url && successCount > 0 && (
          <button
            onClick={handleDownloadZip}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md shadow-sm transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            ZIPをダウンロード
          </button>
        )}
      </div>
      
      {/* 処理結果リスト（大量になっても大丈夫なようにスクロール領域化） */}
      <div className="max-h-64 overflow-y-auto p-2 bg-slate-50/50 dark:bg-slate-800/30">
        <ul className="space-y-1">
          {results.map((item, index) => {
            const isSuccess = item.status === 'success';
            
            return (
              <li 
                key={index} 
                className="flex items-center gap-3 text-xs p-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0 rounded-md hover:bg-white dark:hover:bg-slate-800 transition-colors"
              >
                {/* ステータスアイコン */}
                {isSuccess ? (
                  <span className="text-green-500 shrink-0 text-base">✓</span>
                ) : (
                  <span className="text-red-500 shrink-0 text-base">✗</span>
                )}
                
                {/* パス情報・エラー情報 */}
                <div className="flex-1 min-w-0 flex items-center gap-2">
                  {/* オリジナルのファイルパス */}
                  <span className="text-slate-500 dark:text-slate-400 truncate max-w-[40%]" title={item.original_path}>
                    {item.original_path}
                  </span>
                  
                  {isSuccess ? (
                    <>
                      <span className="text-slate-300 dark:text-slate-600 shrink-0">→</span>
                      <span className="font-mono text-slate-700 dark:text-slate-300 truncate" title={item.new_file_path}>
                        {item.new_file_path}
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="text-slate-300 dark:text-slate-600 shrink-0">-</span>
                      <span className="text-red-500 truncate" title={item.message}>
                        {item.message || "処理エラー"}
                      </span>
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
