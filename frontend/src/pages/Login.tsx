import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authApi } from "../api/auth";
import { useAuthStore } from "../store/authStore";

const schema = z.object({ email: z.string().email(), password: z.string().min(8) });
type FormData = z.infer<typeof schema>;

export default function Login() {
  const [error, setError] = useState("");
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError("");
    try {
      const res = await authApi.login(data);
      const me = await authApi.me();
      setAuth(me.data, res.data.access_token);
      navigate("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed");
    }
  };

  const inputClass = "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none";

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border p-8">
        <h1 className="text-2xl font-bold text-center mb-6">Sign In</h1>
        {error && <p className="text-red-600 text-sm mb-4 text-center" role="alert">{error}</p>}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" aria-label="Sign in form">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input {...register("email")} id="email" type="email" className={inputClass} aria-invalid={!!errors.email} aria-describedby={errors.email ? "email-error" : undefined} />
            {errors.email && <p id="email-error" className="text-red-500 text-sm mt-1" role="alert">{errors.email.message}</p>}
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input {...register("password")} id="password" type="password" className={inputClass} aria-invalid={!!errors.password} aria-describedby={errors.password ? "password-error" : undefined} />
            {errors.password && <p id="password-error" className="text-red-500 text-sm mt-1" role="alert">{errors.password.message}</p>}
          </div>
          <button type="submit" disabled={isSubmitting} className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {isSubmitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
        <p className="text-sm text-center mt-4 text-gray-500">No account? <Link to="/register" className="text-blue-600 hover:underline">Register</Link></p>
      </div>
    </div>
  );
}
