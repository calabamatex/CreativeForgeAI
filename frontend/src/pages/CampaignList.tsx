import { useState } from "react";
import { Link } from "react-router-dom";
import { useCampaigns } from "../hooks/useCampaigns";
import { formatDate } from "../lib/utils";
import { Plus } from "lucide-react";

export default function CampaignList() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, isLoading } = useCampaigns(statusFilter ? { status: statusFilter } : undefined);
  const campaigns = data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Campaigns</h2>
        <Link to="/campaigns/new" className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <Plus size={18} /> New Campaign
        </Link>
      </div>

      <div className="flex gap-3 mb-4">
        {["", "draft", "processing", "completed", "failed"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm ${statusFilter === s ? "bg-blue-600 text-white" : "bg-white border text-gray-700 hover:bg-gray-50"}`}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm border">
        {isLoading ? (
          <p className="p-6 text-gray-500">Loading campaigns...</p>
        ) : campaigns.length === 0 ? (
          <p className="p-6 text-gray-500">No campaigns found.</p>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Name</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Brand</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Assets</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {campaigns.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/campaigns/${c.id}`} className="text-blue-600 hover:underline font-medium">{c.campaign_name}</Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.brand_name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      c.status === "completed" ? "bg-green-100 text-green-700" :
                      c.status === "processing" ? "bg-yellow-100 text-yellow-700" :
                      c.status === "failed" ? "bg-red-100 text-red-700" :
                      "bg-gray-100 text-gray-700"
                    }`}>{c.status}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.asset_count}</td>
                  <td className="px-4 py-3 text-gray-500 text-sm">{formatDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
