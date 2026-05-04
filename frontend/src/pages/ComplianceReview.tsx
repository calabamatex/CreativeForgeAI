import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ComplianceReport, Envelope } from "../api/types";
import { Shield, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

export default function ComplianceReview() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["compliance", id],
    queryFn: () => api.get<Envelope<ComplianceReport>>(`/campaigns/${id}/compliance`),
    enabled: !!id,
  });

  const report = data?.data;

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Compliance Review</h2>
      {isLoading ? (
        <p className="text-gray-500">Loading...</p>
      ) : !report ? (
        <div className="bg-white rounded-xl border p-6 text-center">
          <Shield size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No compliance report available. Run a compliance check first.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className={`rounded-xl border p-6 ${report.is_compliant ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
            <div className="flex items-center gap-3">
              {report.is_compliant ? <CheckCircle size={24} className="text-green-600" /> : <XCircle size={24} className="text-red-600" />}
              <span className="text-lg font-semibold">{report.is_compliant ? "Compliant" : "Violations Found"}</span>
            </div>
          </div>
          {report.violations.length > 0 && (
            <div className="bg-white rounded-xl border p-6">
              <h3 className="font-semibold mb-4">Violations ({report.violations.length})</h3>
              <div className="space-y-3">
                {report.violations.map((v, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <AlertTriangle size={18} className="text-yellow-500 mt-0.5 shrink-0" />
                    <div className="text-sm">
                      <pre className="text-gray-700 whitespace-pre-wrap">{JSON.stringify(v, null, 2)}</pre>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
