import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { brandApi } from "../api/brands";
import { formatDate } from "../lib/utils";
import { Plus, BookOpen } from "lucide-react";

export default function BrandList() {
  const { data, isLoading } = useQuery({ queryKey: ["brands"], queryFn: brandApi.list });
  const brands = data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Brand Guidelines</h2>
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <Plus size={18} /> Upload Guidelines
        </button>
      </div>
      {isLoading ? (
        <p className="text-gray-500">Loading...</p>
      ) : brands.length === 0 ? (
        <div className="bg-white rounded-xl border p-8 text-center">
          <BookOpen size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No brand guidelines uploaded yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {brands.map((b) => (
            <Link key={b.id} to={`/brands/${b.id}`} className="bg-white rounded-xl border p-5 hover:shadow-md transition-shadow">
              <h3 className="font-semibold text-gray-900">{b.name}</h3>
              <div className="flex gap-1 mt-2">{b.primary_colors.map((c, i) => <div key={i} className="w-6 h-6 rounded" style={{ backgroundColor: c }} />)}</div>
              <p className="text-sm text-gray-500 mt-2">{b.primary_font}{b.secondary_font ? ` / ${b.secondary_font}` : ""}</p>
              <p className="text-xs text-gray-400 mt-1">{formatDate(b.created_at)}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
