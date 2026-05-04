import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { assetApi } from "../api/assets";
import { formatBytes } from "../lib/utils";
import { Download, X } from "lucide-react";

export default function AssetGallery() {
  const { id } = useParams<{ id: string }>();
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [localeFilter, setLocaleFilter] = useState("");
  const [ratioFilter, setRatioFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["assets", id, localeFilter, ratioFilter],
    queryFn: () => assetApi.listByCampaign(id!, { locale: localeFilter || undefined, aspect_ratio: ratioFilter || undefined }),
    enabled: !!id,
  });

  const assets = data?.data ?? [];
  const locales = [...new Set(assets.map((a) => a.locale))];
  const ratios = [...new Set(assets.map((a) => a.aspect_ratio))];

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-4">Asset Gallery</h2>

      <div className="flex gap-3 mb-6">
        <select value={localeFilter} onChange={(e) => setLocaleFilter(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" aria-label="Filter by locale">
          <option value="">All Locales</option>
          {locales.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <select value={ratioFilter} onChange={(e) => setRatioFilter(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" aria-label="Filter by ratio">
          <option value="">All Ratios</option>
          {ratios.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {isLoading ? (
        <p className="text-gray-500">Loading assets...</p>
      ) : assets.length === 0 ? (
        <p className="text-gray-500">No assets generated yet.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {assets.map((asset) => (
            <div key={asset.id} onClick={() => setSelectedAsset(asset.id)} className="bg-white rounded-lg border shadow-sm overflow-hidden cursor-pointer hover:shadow-md transition-shadow">
              <div className="aspect-square bg-gray-100 flex items-center justify-center text-gray-400 text-sm">
                {asset.aspect_ratio}
              </div>
              <div className="p-3">
                <p className="text-sm font-medium truncate">{asset.product_id}</p>
                <p className="text-xs text-gray-500">{asset.locale} - {asset.aspect_ratio}</p>
                {asset.file_size_bytes && <p className="text-xs text-gray-400">{formatBytes(asset.file_size_bytes)}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedAsset && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedAsset(null)}>
          <div className="bg-white rounded-xl p-6 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">Asset Details</h3>
              <button onClick={() => setSelectedAsset(null)} aria-label="Close"><X size={20} /></button>
            </div>
            <a href={assetApi.downloadUrl(selectedAsset)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 w-fit">
              <Download size={16} /> Download
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
