import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Settings as SettingsIcon, CheckCircle, XCircle } from "lucide-react";

interface BackendInfo { name: string; available: boolean; model?: string }
interface SettingsData { default_image_backend: string; available_backends: BackendInfo[]; max_concurrent_requests: number; api_timeout: number }

export default function Settings() {
  const { data } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<{ data: SettingsData }>("/settings/backends"),
  });

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Settings</h2>
      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2"><SettingsIcon size={20} /> Image Backends</h3>
        <div className="space-y-3">
          {(data?.data?.available_backends ?? [
            { name: "Adobe Firefly", available: false },
            { name: "OpenAI DALL-E 3", available: false },
            { name: "Google Gemini Imagen 4", available: false },
          ]).map((b) => (
            <div key={b.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <span className="font-medium">{b.name}</span>
              <span className="flex items-center gap-1 text-sm">
                {b.available ? <><CheckCircle size={16} className="text-green-500" /> Configured</> : <><XCircle size={16} className="text-gray-400" /> Not configured</>}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
