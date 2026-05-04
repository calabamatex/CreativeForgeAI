import { useParams, Link } from "react-router-dom";
import { useCampaign } from "../hooks/useCampaigns";
import { formatDate } from "../lib/utils";
import { ArrowLeft, Image, Shield, BarChart3 } from "lucide-react";

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useCampaign(id!);
  const campaign = data?.data;

  if (isLoading) return <p className="text-gray-500">Loading...</p>;
  if (!campaign) return <p className="text-gray-500">Campaign not found.</p>;

  return (
    <div>
      <Link to="/campaigns" className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={16} /> Back to campaigns
      </Link>

      <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{campaign.campaign_name}</h2>
            <p className="text-gray-500 mt-1">{campaign.brand_name} - {campaign.image_backend}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            campaign.status === "completed" ? "bg-green-100 text-green-700" :
            campaign.status === "processing" ? "bg-yellow-100 text-yellow-700" :
            campaign.status === "failed" ? "bg-red-100 text-red-700" :
            "bg-gray-100 text-gray-700"
          }`}>{campaign.status}</span>
        </div>

        <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 text-sm">
          <div><dt className="text-gray-500">Assets</dt><dd className="text-lg font-semibold">{campaign.asset_count}</dd></div>
          <div><dt className="text-gray-500">Locales</dt><dd className="text-lg font-semibold">{campaign.target_locales.length}</dd></div>
          <div><dt className="text-gray-500">Ratios</dt><dd className="text-lg font-semibold">{campaign.aspect_ratios.length}</dd></div>
          <div><dt className="text-gray-500">Created</dt><dd className="text-sm font-medium">{formatDate(campaign.created_at)}</dd></div>
        </dl>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link to={`/campaigns/${id}/assets`} className="bg-white rounded-xl shadow-sm border p-5 hover:border-blue-300 transition-colors">
          <Image size={24} className="text-blue-600 mb-2" />
          <h3 className="font-semibold">Asset Gallery</h3>
          <p className="text-sm text-gray-500">View and download generated assets</p>
        </Link>
        <Link to={`/campaigns/${id}/compliance`} className="bg-white rounded-xl shadow-sm border p-5 hover:border-blue-300 transition-colors">
          <Shield size={24} className="text-green-600 mb-2" />
          <h3 className="font-semibold">Compliance Review</h3>
          <p className="text-sm text-gray-500">Check legal compliance status</p>
        </Link>
        <Link to={`/metrics`} className="bg-white rounded-xl shadow-sm border p-5 hover:border-blue-300 transition-colors">
          <BarChart3 size={24} className="text-purple-600 mb-2" />
          <h3 className="font-semibold">Metrics</h3>
          <p className="text-sm text-gray-500">View performance and business metrics</p>
        </Link>
      </div>
    </div>
  );
}
