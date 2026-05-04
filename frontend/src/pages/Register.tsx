import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authApi } from "../api/auth";
import { useAuthStore } from "../store/authStore";

const schema = z.object({
  display_name: z.string().min(2).max(100),
  email: z.string().email(),
  password: z.string().min(8),
  confirm_password: z.string().min(8),
}).refine((d) => d.password === d.confirm_password, { message: "Passwords must match", path: ["confirm_password"] });

type FormData = z.infer<typeof schema>;

export default function Register() {
  const [error, setError] = useState("");
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError("");
    try {
      await authApi.register({ email: data.email, password: data.password, display_name: data.display_name });
      const res = await authApi.login({ email: data.email, password: data.password });
      const me = await authApi.me();
      setAuth(me.data, res.data.access_token);
      navigate("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
    }
  };

  const inputClass = "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none";

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border p-8">
        <h1 className="text-2xl font-bold text-center mb-6">Create Account</h1>
        {error && <p className="text-red-600 text-sm mb-4 text-center" role="alert">{error}</p>}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" aria-label="Registration form">
          <div>
            <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
            <input {...register("display_name")} id="display_name" className={inputClass} aria-invalid={!!errors.display_name} aria-describedby={errors.display_name ? "display-name-error" : undefined} />
            {errors.display_name && <p id="display-name-error" className="text-red-500 text-sm mt-1" role="alert">{errors.display_name.message}</p>}
          </div>
          <div>
            <label htmlFor="reg-email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input {...register("email")} id="reg-email" type="email" className={inputClass} aria-invalid={!!errors.email} aria-describedby={errors.email ? "reg-email-error" : undefined} />
            {errors.email && <p id="reg-email-error" className="text-red-500 text-sm mt-1" role="alert">{errors.email.message}</p>}
          </div>
          <div>
            <label htmlFor="reg-password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input {...register("password")} id="reg-password" type="password" className={inputClass} aria-invalid={!!errors.password} aria-describedby={errors.password ? "reg-password-error" : undefined} />
            {errors.password && <p id="reg-password-error" className="text-red-500 text-sm mt-1" role="alert">{errors.password.message}</p>}
          </div>
          <div>
            <label htmlFor="confirm_password" className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
            <input {...register("confirm_password")} id="confirm_password" type="password" className={inputClass} aria-invalid={!!errors.confirm_password} aria-describedby={errors.confirm_password ? "confirm-password-error" : undefined} />
            {errors.confirm_password && <p id="confirm-password-error" className="text-red-500 text-sm mt-1" role="alert">{errors.confirm_password.message}</p>}
          </div>
          <button type="submit" disabled={isSubmitting} className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {isSubmitting ? "Creating account..." : "Register"}
          </button>
        </form>
        <p className="text-sm text-center mt-4 text-gray-500">Already have an account? <Link to="/login" className="text-blue-600 hover:underline">Sign in</Link></p>
      </div>
    </div>
  );
}
