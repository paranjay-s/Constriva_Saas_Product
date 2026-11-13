import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { AuthCinematic } from './AuthCinematic';
import { BrandMark, CtaArrow, LinkArrow } from '../../components/ui/Icons';

export const AuthPage: React.FC = () => {
  const [mode, setMode] = useState<'signin' | 'signup' | 'forgot'>('signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string; general?: string }>({});
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { signIn, signUp, loginAsDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/home';

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (mode === 'signup' && !name.trim()) {
      errs.name = 'Full name is required';
    }
    if (!email.trim()) {
      errs.email = 'Email address is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errs.email = 'Please enter a valid email address';
    }
    if (mode !== 'forgot') {
      if (!password) {
        errs.password = 'Password is required';
      } else if (password.length < 6) {
        errs.password = 'Password must be at least 6 characters';
      }
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMessage(null);
    if (!validate()) return;

    setIsLoading(true);
    setErrors({});

    try {
      if (mode === 'signin') {
        await signIn(email, password);
        navigate(from, { replace: true });
      } else if (mode === 'signup') {
        await signUp(name, email, password);
        navigate(from, { replace: true });
      } else {
        await new Promise((r) => setTimeout(r, 600));
        setSuccessMessage('Password reset instructions sent to your email.');
        setIsLoading(false);
      }
    } catch (err: unknown) {
      setErrors({ general: err instanceof Error ? err.message : 'Authentication failed. Please try again.' });
      setIsLoading(false);
    }
  };

  const handleDemoAccess = () => {
    loginAsDemo();
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen w-full bg-[#0d0f12] text-white flex flex-col lg:flex-row overflow-hidden">
      {/* Left Column: Architectural Form */}
      <div className="w-full lg:w-1/2 flex flex-col justify-between px-6 sm:px-12 lg:px-16 py-10 z-10">
        {/* Brand Header */}
        <div className="flex items-center justify-between">
          <a href="/" className="inline-flex items-center gap-3 group">
            <BrandMark className="w-7 h-7 text-[#C5A77B] group-hover:scale-105 transition-transform" />
            <span className="font-display font-medium text-2xl tracking-tight text-white">
              Constriva
            </span>
          </a>
          <a
            href="/"
            className="text-xs font-mono uppercase tracking-wider text-white/60 hover:text-white transition-colors inline-flex items-center gap-1.5"
          >
            <span>Back to site</span>
            <LinkArrow className="w-3.5 h-3.5" />
          </a>
        </div>

        {/* Center Card Content */}
        <div className="max-w-md w-full mx-auto my-10">
          <div className="mb-8">
            <span className="text-[11px] font-mono uppercase tracking-widest text-[#C5A77B] block mb-2">
              Architectural Intelligence Platform // Atelier
            </span>
            <h1 className="font-display font-medium text-3xl sm:text-4xl text-white tracking-tight">
              {mode === 'signin'
                ? 'Welcome back'
                : mode === 'signup'
                ? 'Create studio account'
                : 'Reset your password'}
            </h1>
            <p className="text-sm text-white/70 mt-2 font-normal">
              {mode === 'signin'
                ? 'Sign in to access your interactive 3D floor plans and BOQ sheets.'
                : mode === 'signup'
                ? 'Synthesize 2D architectural drawings into walkthroughs and bills of quantities.'
                : 'Enter your email to receive a password reset link.'}
            </p>
          </div>

          {/* Mode Switcher Pills */}
          {mode !== 'forgot' && (
            <div className="grid grid-cols-2 p-1.5 bg-white/[0.04] border border-white/10 rounded-full mb-6">
              <button
                type="button"
                onClick={() => {
                  setMode('signin');
                  setErrors({});
                  setSuccessMessage(null);
                }}
                className={`text-xs font-medium py-2 rounded-full transition-all cursor-pointer ${
                  mode === 'signin'
                    ? 'bg-[#000000] text-white shadow-md'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('signup');
                  setErrors({});
                  setSuccessMessage(null);
                }}
                className={`text-xs font-medium py-2 rounded-full transition-all cursor-pointer ${
                  mode === 'signup'
                    ? 'bg-[#000000] text-white shadow-md'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Create Account
              </button>
            </div>
          )}

          {errors.general && (
            <div className="mb-5 p-3.5 rounded-xl bg-[#351010]/80 border border-[#FFB4AB]/40 text-[#FFB4AB] text-xs flex items-center gap-2.5 backdrop-blur-md">
              <span className="w-2 h-2 rounded-full bg-[#FFB4AB]" />
              <span>{errors.general}</span>
            </div>
          )}

          {successMessage && (
            <div className="mb-5 p-3.5 rounded-xl bg-[#102A1A]/80 border border-[#10B981]/40 text-[#A7F3D0] text-xs flex items-center gap-2.5 backdrop-blur-md">
              <span className="w-2 h-2 rounded-full bg-[#10B981]" />
              <span>{successMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {mode === 'signup' && (
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-white/70 mb-1.5">
                  Full Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. David Miller"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                  className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/15 text-white placeholder-white/30 text-sm focus:outline-none focus:border-[#C5A77B] focus:ring-1 focus:ring-[#C5A77B] transition-all"
                />
                {errors.name && <p className="text-xs text-[#FFB4AB] mt-1">{errors.name}</p>}
              </div>
            )}

            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-white/70 mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                placeholder="architect@domain.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/15 text-white placeholder-white/30 text-sm focus:outline-none focus:border-[#C5A77B] focus:ring-1 focus:ring-[#C5A77B] transition-all"
              />
              {errors.email && <p className="text-xs text-[#FFB4AB] mt-1">{errors.email}</p>}
            </div>

            {mode !== 'forgot' && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-mono uppercase tracking-wider text-white/70">
                    Password
                  </label>
                  {mode === 'signin' && (
                    <button
                      type="button"
                      onClick={() => {
                        setMode('forgot');
                        setErrors({});
                      }}
                      className="text-[11px] font-mono text-[#C5A77B] hover:text-[#fff1e2] transition-colors cursor-pointer"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                  className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/15 text-white placeholder-white/30 text-sm focus:outline-none focus:border-[#C5A77B] focus:ring-1 focus:ring-[#C5A77B] transition-all"
                />
                {errors.password && <p className="text-xs text-[#FFB4AB] mt-1">{errors.password}</p>}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="group w-full mt-2 inline-flex items-center justify-center gap-3 py-3.5 px-6 rounded-full bg-white text-[#101418] font-semibold text-sm hover:bg-[#f0f4f8] transition-all duration-200 shadow-lg hover:shadow-xl hover:-translate-y-0.5 cursor-pointer disabled:opacity-50"
            >
              <span>
                {isLoading
                  ? 'Authenticating...'
                  : mode === 'signin'
                  ? 'Sign In to Workspace'
                  : mode === 'signup'
                  ? 'Create Studio Account'
                  : 'Send Reset Link'}
              </span>
              <span className="w-7 h-7 rounded-full bg-[#101418] text-white flex items-center justify-center group-hover:rotate-45 transition-transform duration-300">
                <CtaArrow className="w-3.5 h-3.5" />
              </span>
            </button>

            {mode === 'forgot' && (
              <button
                type="button"
                onClick={() => {
                  setMode('signin');
                  setSuccessMessage(null);
                }}
                className="text-xs font-mono text-white/60 hover:text-white text-center mt-2 cursor-pointer transition-colors"
              >
                ← Back to Sign In
              </button>
            )}
          </form>

          {/* Quick Demo Access */}
          <div className="relative my-7 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10" />
            </div>
            <span className="relative bg-[#0d0f12] px-3 text-[10px] uppercase font-mono tracking-widest text-white/50">
              Instant Evaluation
            </span>
          </div>

          <button
            type="button"
            onClick={handleDemoAccess}
            className="w-full inline-flex items-center justify-between px-5 py-3 rounded-full arch-glass-pill text-xs font-medium text-white hover:text-[#fff1e2] cursor-pointer group"
          >
            <span className="inline-flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-[#ffbf7a] animate-pulse-glow" />
              <span>Instant Architect Demo Access</span>
            </span>
            <span className="text-[11px] font-mono text-[#C5A77B] group-hover:translate-x-1 transition-transform">
              Explore Now →
            </span>
          </button>
        </div>

        {/* Footer info */}
        <p className="text-[11px] font-mono text-white/40 text-center">
          Constriva Architecture Engine // End-to-end 3D & BOQ Synthesizer
        </p>
      </div>

      {/* Right Column: High-Impact Video Walkthrough */}
      <div className="w-full lg:w-1/2 min-h-[500px] lg:min-h-screen relative">
        <AuthCinematic />
      </div>
    </div>
  );
};
