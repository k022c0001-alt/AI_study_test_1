import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Circle, Marker, Popup, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Leafletのデフォルトアイコン設定
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});
L.Marker.prototype.options.icon = DefaultIcon;

// ==============================
// 1. カテゴリ初期定義 & 重み
// ==============================
const DEFAULT_CATEGORIES = [
  { id: 'Work', name: 'ワーク環境', icon: '💻', weight: 0.20, enabled: true },
  { id: 'Medical', name: '医療・病院', icon: '🏥', weight: 0.25, enabled: true },
  { id: 'Shopping', name: '買い物・スーパー', icon: '🛒', weight: 0.25, enabled: true },
  { id: 'Health', name: '健康・スポーツ', icon: '🏃', weight: 0.15, enabled: true },
  { id: 'Park', name: '公園・緑地', icon: '🌳', weight: 0.15, enabled: true },
];

// 2地点の緯度経度から距離(m)を計算（ヒュベニ/Haversine）
const calculateDistanceMeters = (lat1, lon1, lat2, lon2) => {
  const R = 6371e3; // 地球の半径(m)
  const φ1 = (lat1 * Math.PI) / 180;
  const φ2 = (lat2 * Math.PI) / 180;
  const Δφ = ((lat2 - lat1) * Math.PI) / 180;
  const Δλ = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

// 徒歩分数からスコア判定 (score_engine.py 準拠)
const getDistanceScore = (minutes) => {
  if (minutes <= 5) return 100;
  if (minutes <= 10) return 90;
  if (minutes <= 15) return 75;
  if (minutes <= 30) return 50;
  return 30;
};

// ==============================
// 2. 地図クリックイベント用子コンポーネント
// ==============================
function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

// ==============================
// 3. メインコンポーネント
// ==============================
export default function MapVisualizer() {
  // 状態管理
  const [center, setCenter] = useState([35.706, 139.559]); // ピンの位置
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [categories, setCategories] = useState(DEFAULT_CATEGORIES);
  const [score, setScore] = useState(85);

  // ダミーPOIデータ（実際はバックエンド/DBから取得）
  const [poiList] = useState([
    { id: 1, name: 'コワーキングカフェ', pos: [35.708, 139.558], category: 'Work' },
    { id: 2, name: '総合病院', pos: [35.702, 139.562], category: 'Medical' },
    { id: 3, name: '大型スーパー', pos: [35.705, 139.554], category: 'Shopping' },
    { id: 4, name: '24時間ジム', pos: [35.711, 139.560], category: 'Health' },
    { id: 5, name: '吉祥寺公園', pos: [35.701, 139.551], category: 'Park' },
  ]);

  // ==============================
  // スコア再計算ロジック
  // ==============================
  const recalculateScore = (targetPos, activeCategories) => {
    let totalScore = 0;
    let totalWeight = 0;

    activeCategories.forEach((cat) => {
      if (!cat.enabled) return;

      // 該当カテゴリのPOIを抽出
      const categoryPois = poiList.filter((poi) => poi.category === cat.id);
      if (categoryPois.length === 0) return;

      // 各POIへの徒歩分数を計算し、最高点（一番近い施設）を採用
      const scores = categoryPois.map((poi) => {
        const distMeters = calculateDistanceMeters(
          targetPos[0],
          targetPos[1],
          poi.pos[0],
          poi.pos[1]
        );
        const walkMinutes = distMeters / 80; // 80m = 徒歩1分
        return getDistanceScore(walkMinutes);
      });

      const maxCatScore = Math.max(...scores);
      totalScore += maxCatScore * cat.weight;
      totalWeight += cat.weight;
    });

    const finalScore = totalWeight > 0 ? Math.round(totalScore / totalWeight) : 0;
    setScore(finalScore);
  };

  // カテゴリトグル処理
  const toggleCategory = (id) => {
    const updated = categories.map((cat) =>
      cat.id === id ? { ...cat, enabled: !cat.enabled } : cat
    );
    setCategories(updated);
    if (!isEvaluating) {
      recalculateScore(center, updated);
    }
  };

  // マップクリック時の処理
  const handleMapClick = (newPos) => {
    setCenter(newPos);
    setIsEvaluating(true);

    // 評価ロード（1.0秒後に判定完了）
    setTimeout(() => {
      recalculateScore(newPos, categories);
      setIsEvaluating(false);
    }, 1000);
  };

  return (
    <div className="relative w-full h-[650px] rounded-xl overflow-hidden border border-slate-200 shadow-sm font-sans">
      
      {/* 📊 左上のスコアボード & カテゴリ選択UI（重ねて表示） */}
      <div className="absolute top-4 left-4 z-[400] bg-white/90 backdrop-blur-md p-5 rounded-xl shadow-lg border border-slate-200 w-80 max-h-[580px] overflow-y-auto">
        <h3 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2">
          <span>🌟</span> 総合生活利便性スコア
        </h3>
        
        {/* 点数表示 / ロード中メッセージ */}
        <div className="flex items-baseline gap-2 my-2">
          {isEvaluating ? (
            <div className="text-2xl font-bold text-blue-500 animate-pulse py-2">
              🔍 周辺施設を評価中...
            </div>
          ) : (
            <>
              <div className="text-5xl font-black text-blue-600 tracking-tighter">
                {score}
              </div>
              <span className="text-lg text-slate-400 font-normal">/100点</span>
            </>
          )}
        </div>

        <p className="text-xs text-slate-500 mb-4 border-b border-slate-100 pb-3">
          マップ上をクリックすると、その地点の利便性を再評価します。
        </p>

        {/* 🎛️ カテゴリチェック選択欄 */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            評価対象カテゴリ
          </div>
          {categories.map((cat) => (
            <label
              key={cat.id}
              className={`flex items-center justify-between p-2 rounded-lg border text-xs cursor-pointer transition-all ${
                cat.enabled
                  ? 'bg-blue-50/60 border-blue-200 text-slate-800 font-medium'
                  : 'bg-slate-50/50 border-slate-200 text-slate-400'
              }`}
            >
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={cat.enabled}
                  onChange={() => toggleCategory(cat.id)}
                  className="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                />
                <span>
                  {cat.icon} {cat.name}
                </span>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">
                {(cat.weight * 100).toFixed(0)}%
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* 🗺️ 地図本体 */}
      <MapContainer center={center} zoom={14} className="w-full h-full z-0">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* マップクリックイベント監視 */}
        <MapClickHandler onMapClick={handleMapClick} />

        {/* 🌊 ロード中の波紋アニメーションCircle */}
        {isEvaluating && (
          <>
            <Circle
              center={center}
              radius={400}
              pathOptions={{
                color: '#3b82f6',
                fillColor: '#3b82f6',
                fillOpacity: 0.3,
                weight: 2,
              }}
            />
            <Circle
              center={center}
              radius={800}
              pathOptions={{
                color: '#60a5fa',
                fillColor: '#60a5fa',
                fillOpacity: 0.15,
                weight: 1,
                dashArray: '4, 4',
              }}
            />
          </>
        )}

        {/* 🔵 通常時の 1km / 2km バッファ */}
        {!isEvaluating && (
          <>
            <Circle
              center={center}
              radius={1000}
              pathOptions={{
                color: '#3b82f6',
                fillColor: '#3b82f6',
                fillOpacity: 0.08,
                weight: 2,
              }}
            />
            <Circle
              center={center}
              radius={2000}
              pathOptions={{
                color: '#22c55e',
                fillColor: '#22c55e',
                fillOpacity: 0.03,
                weight: 1,
                dashArray: '5, 5',
              }}
            />
          </>
        )}

        {/* 🏠 評価・検討対象の中心ピン */}
        <Marker position={center}>
          <Popup>
            <div className="font-bold text-slate-800 text-sm">📍 評価指定地点</div>
            <div className="text-xs text-blue-600 mt-1 font-semibold">
              総合スコア: {score}点
            </div>
          </Popup>
        </Marker>

        {/* 📍 周辺POIのピン（有効なカテゴリのみ表示） */}
        {poiList.map((poi) => {
          const catDef = categories.find((c) => c.id === poi.category);
          if (catDef && !catDef.enabled) return null; // 無効化されたカテゴリは隠す

          return (
            <Marker key={poi.id} position={poi.pos}>
              <Popup>
                <div className="font-semibold text-slate-800">{poi.name}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  {catDef?.icon} {catDef?.name || poi.category}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
