import { Routes, Route } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import CampaignList from "./pages/CampaignList";
import CampaignBuilder from "./pages/CampaignBuilder";
import CampaignDetail from "./pages/CampaignDetail";
import AssetGallery from "./pages/AssetGallery";
import ComplianceReview from "./pages/ComplianceReview";
import BrandList from "./pages/BrandList";
import BrandDetail from "./pages/BrandDetail";
import MetricsDashboard from "./pages/MetricsDashboard";
import JobMonitor from "./pages/JobMonitor";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import Register from "./pages/Register";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/campaigns" element={<CampaignList />} />
        <Route path="/campaigns/new" element={<CampaignBuilder />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
        <Route path="/campaigns/:id/assets" element={<AssetGallery />} />
        <Route path="/campaigns/:id/compliance" element={<ComplianceReview />} />
        <Route path="/brands" element={<BrandList />} />
        <Route path="/brands/:id" element={<BrandDetail />} />
        <Route path="/metrics" element={<MetricsDashboard />} />
        <Route path="/jobs" element={<JobMonitor />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
