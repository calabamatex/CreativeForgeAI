import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { brandApi } from "../api/brands";
import { ArrowLeft } from "lucide-react";

export default function BrandDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({ queryKey: ["brand", id], queryFn: () => brandApi.get(id!), enabled: !!id });
  const brand = data?.data;

  if (isLoading) return <p className="text-gray-500">Loading...</p>;
  if (!brand) return <p className="text-gray-500">Brand not found.</p>;

  return (
    <div className="max-w-2xl">
      <Link to="/brands" className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-4"><ArrowLeft size={16} /> Back</Link>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">{brand.name}</h2>
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-2">Primary Colors</h3>
          <div className="flex gap-2">{brand.primary_colors.map((c, i) => <div key={i} className="w-10 h-10 rounded-lg border" style={{ backgroundColor: c }} title={c} />)}</div>
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Fonts</h3>
          <p className="text-gray-900">{brand.primary_font}{brand.secondary_font ? ` / ${brand.secondary_font}` : ""}</p>
        </div>
        {brand.brand_voice && <div><h3 className="text-sm font-medium text-gray-500 mb-1">Brand Voice</h3><p className="text-gray-900">{brand.brand_voice}</p></div>}
        {brand.photography_style && <div><h3 className="text-sm font-medium text-gray-500 mb-1">Photography Style</h3><p className="text-gray-900">{brand.photography_style}</p></div>}
      </div>
    </div>
  );
}
