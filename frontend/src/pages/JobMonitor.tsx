import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Job, PaginatedEnvelope } from "../api/types";
import { formatDate } from "../lib/utils";
import { Activity } from "lucide-react";

export default function JobMonitor() {
  const { data, isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.get<PaginatedEnvelope<Job>>("/jobs"),
    refetchInterval: 5000,
  });

  const jobs = data?.data ?? [];

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Job Monitor</h2>
      {isLoading ? (
        <p className="text-gray-500">Loading...</p>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-xl border p-8 text-center">
          <Activity size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No jobs yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div key={job.id} className="bg-white rounded-xl border p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-medium text-gray-900">{job.id.slice(0, 8)}...</span>
                  <span className={`ml-3 px-2 py-0.5 rounded-full text-xs font-medium ${
                    job.status === "completed" ? "bg-green-100 text-green-700" :
                    job.status === "running" ? "bg-blue-100 text-blue-700" :
                    job.status === "failed" ? "bg-red-100 text-red-700" :
                    "bg-gray-100 text-gray-700"
                  }`}>{job.status}</span>
                </div>
                {job.current_stage && <span className="text-sm text-gray-500">{job.current_stage}</span>}
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className={`h-2 rounded-full transition-all ${job.status === "failed" ? "bg-red-500" : "bg-blue-600"}`} style={{ width: `${job.progress_percent}%` }} />
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>{job.progress_percent}%</span>
                {job.started_at && <span>{formatDate(job.started_at)}</span>}
              </div>
              {job.error_message && <p className="text-sm text-red-600 mt-2">{job.error_message}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
