import { Link } from "react-router-dom";
import { useCampaigns } from "../hooks/useCampaigns";
import { Megaphone, Image, CheckCircle, Clock } from "lucide-react";

export default function Dashboard() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.data ?? [];

  const stats = {
    total: campaigns.length,
    active: campaigns.filter((c) => c.status === "processing").length,
    completed: campaigns.filter((c) => c.status === "completed").length,
    totalAssets: campaigns.reduce((sum, c) => sum + c.asset_count, 0),
  };

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Total Campaigns", value: stats.total, icon: Megaphone, color: "blue" },
          { label: "Active", value: stats.active, icon: Clock, color: "yellow" },
          { label: "Completed", value: stats.completed, icon: CheckCircle, color: "green" },
          { label: "Total Assets", value: stats.totalAssets, icon: Image, color: "purple" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{isLoading ? "-" : value}</p>
              </div>
              <div className={`p-3 rounded-lg bg-${color}-50`}>
                <Icon size={24} className={`text-${color}-600`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Recent Campaigns</h3>
          <Link to="/campaigns/new" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
            New Campaign
          </Link>
        </div>
        {isLoading ? (
          <p className="text-gray-500">Loading...</p>
        ) : campaigns.length === 0 ? (
          <p className="text-gray-500">No campaigns yet. Create your first one!</p>
        ) : (
          <div className="divide-y">
            {campaigns.slice(0, 5).map((c) => (
              <Link key={c.id} to={`/campaigns/${c.id}`} className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-2 px-2 rounded">
                <div>
                  <p className="font-medium text-gray-900">{c.campaign_name}</p>
                  <p className="text-sm text-gray-500">{c.brand_name} - {c.asset_count} assets</p>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  c.status === "completed" ? "bg-green-100 text-green-700" :
                  c.status === "processing" ? "bg-yellow-100 text-yellow-700" :
                  c.status === "failed" ? "bg-red-100 text-red-700" :
                  "bg-gray-100 text-gray-700"
                }`}>{c.status}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
