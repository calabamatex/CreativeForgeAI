import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateCampaign } from "../hooks/useCampaigns";
import { ChevronLeft, ChevronRight, Send } from "lucide-react";

const schema = z.object({
  campaign_name: z.string().min(3).max(100),
  brand_name: z.string().min(1),
  target_market: z.string().default("Global"),
  target_audience: z.string().default("General"),
  image_backend: z.enum(["firefly", "openai", "gemini"]),
  headline: z.string().min(1).max(80),
  subheadline: z.string().min(1).max(120),
  cta: z.string().min(1).max(40),
  enable_localization: z.boolean().default(false),
  target_locales: z.array(z.string()).default(["en-US"]),
  aspect_ratios: z.array(z.string()).min(1),
});

type FormData = z.infer<typeof schema>;

const STEPS = ["Campaign Details", "Messaging", "Aspect Ratios", "Review & Submit"];

export default function CampaignBuilder() {
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const createCampaign = useCreateCampaign();

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      image_backend: "firefly",
      target_market: "Global",
      target_audience: "General",
      enable_localization: false,
      target_locales: ["en-US"],
      aspect_ratios: ["1:1", "9:16", "16:9"],
    },
  });

  const values = watch();

  const onSubmit = async (data: FormData) => {
    const brief = {
      campaign_id: `CAMP-${Date.now()}`,
      campaign_name: data.campaign_name,
      brand_name: data.brand_name,
      target_market: data.target_market,
      target_audience: data.target_audience,
      campaign_message: { locale: "en-US", headline: data.headline, subheadline: data.subheadline, cta: data.cta },
      products: [{ product_id: "PROD-001", product_name: "Default Product", product_description: "Product description", product_category: "General", key_features: [] }],
      aspect_ratios: data.aspect_ratios,
      image_generation_backend: data.image_backend,
      enable_localization: data.enable_localization,
      target_locales: data.target_locales,
    };
    await createCampaign.mutateAsync({ brief, image_backend: data.image_backend });
    navigate("/campaigns");
  };

  const inputClass = "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none";
  const labelClass = "block text-sm font-medium text-gray-700 mb-1";

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Create Campaign</h2>
      <div className="flex gap-2 mb-8">
        {STEPS.map((s, i) => (
          <div key={s} className={`flex-1 h-1 rounded ${i <= step ? "bg-blue-600" : "bg-gray-200"}`} />
        ))}
      </div>
      <p className="text-sm text-gray-500 mb-6">Step {step + 1}: {STEPS[step]}</p>

      <form onSubmit={handleSubmit(onSubmit)} className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
        {step === 0 && (
          <>
            <div><label className={labelClass}>Campaign Name</label><input {...register("campaign_name")} className={inputClass} />{errors.campaign_name && <p className="text-red-500 text-sm mt-1">{errors.campaign_name.message}</p>}</div>
            <div><label className={labelClass}>Brand Name</label><input {...register("brand_name")} className={inputClass} /></div>
            <div><label className={labelClass}>Target Market</label><input {...register("target_market")} className={inputClass} /></div>
            <div><label className={labelClass}>Image Backend</label>
              <select {...register("image_backend")} className={inputClass}>
                <option value="firefly">Adobe Firefly</option>
                <option value="openai">OpenAI DALL-E 3</option>
                <option value="gemini">Google Gemini Imagen 4</option>
              </select>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <div><label className={labelClass}>Headline (max 80 chars)</label><input {...register("headline")} className={inputClass} maxLength={80} /></div>
            <div><label className={labelClass}>Subheadline (max 120 chars)</label><input {...register("subheadline")} className={inputClass} maxLength={120} /></div>
            <div><label className={labelClass}>CTA (max 40 chars)</label><input {...register("cta")} className={inputClass} maxLength={40} /></div>
            <div className="flex items-center gap-2">
              <input type="checkbox" {...register("enable_localization")} id="loc" className="rounded" />
              <label htmlFor="loc" className="text-sm text-gray-700">Enable localization</label>
            </div>
          </>
        )}

        {step === 2 && (
          <div>
            <label className={labelClass}>Aspect Ratios</label>
            {["1:1", "9:16", "16:9", "4:5"].map((r) => (
              <label key={r} className="flex items-center gap-2 py-1">
                <input type="checkbox" value={r} {...register("aspect_ratios")} defaultChecked={["1:1", "9:16", "16:9"].includes(r)} className="rounded" />
                <span className="text-gray-700">{r}</span>
              </label>
            ))}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-gray-900">Review</h3>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-500">Campaign</dt><dd className="font-medium">{values.campaign_name}</dd>
              <dt className="text-gray-500">Brand</dt><dd className="font-medium">{values.brand_name}</dd>
              <dt className="text-gray-500">Backend</dt><dd className="font-medium">{values.image_backend}</dd>
              <dt className="text-gray-500">Headline</dt><dd className="font-medium">{values.headline}</dd>
              <dt className="text-gray-500">Ratios</dt><dd className="font-medium">{values.aspect_ratios?.join(", ")}</dd>
            </dl>
          </div>
        )}

        <div className="flex justify-between pt-4">
          <button type="button" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0} className="flex items-center gap-1 px-4 py-2 text-gray-600 disabled:opacity-30">
            <ChevronLeft size={18} /> Back
          </button>
          {step < STEPS.length - 1 ? (
            <button type="button" onClick={() => setStep(step + 1)} className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Next <ChevronRight size={18} />
            </button>
          ) : (
            <button type="submit" disabled={createCampaign.isPending} className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
              <Send size={18} /> {createCampaign.isPending ? "Creating..." : "Create Campaign"}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
