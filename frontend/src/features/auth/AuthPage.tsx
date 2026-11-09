import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { AlertCircleIcon, ArrowRightIcon, CheckIcon, LogoIcon } from '../../components/ui/Icons';
import { Input } from '../../components/ui/Input';
import { useAuth } from '../../context/AuthContext';

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
        // Forgot password simulation
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
    <div className="min-h-screen bg-[#101010] flex flex-col justify-center items-center px-4 py-12">
      {/* Brand Header */}
      <div className="flex flex-col items-center mb-8 text-center">
        <div className="w-12 h-12 rounded bg-[#181818] border border-[#303030] flex items-center justify-center text-[#C5A77B] mb-3">
          <LogoIcon size={26} />
        </div>
        <h1 className="font-display font-semibold text-2xl lg:text-3xl tracking-tight text-[#FFFFFF]">
          Construtiva
        </h1>
        <p className="text-xs font-mono uppercase tracking-widest text-[#A6A6A6] mt-1">
          Architectural Intelligence Platform
        </p>
      </div>

      {/* Main Card */}
      <Card className="w-full max-w-md bg-[#181818] border-[#303030] p-8 shadow-2xl">
        {/* Toggle Mode */}
        {mode !== 'forgot' && (
          <div className="grid grid-cols-2 p-1 bg-[#101010] border border-[#303030] rounded mb-6">
            <button
              type="button"
              onClick={() => {
                setMode('signin');
                setErrors({});
                setSuccessMessage(null);
              }}
              className={`text-xs uppercase tracking-wider py-2 font-medium rounded transition-all cursor-pointer ${
                mode === 'signin' ? 'bg-[#202020] text-[#FFFFFF] font-semibold' : 'text-[#737373] hover:text-[#A6A6A6]'
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
              className={`text-xs uppercase tracking-wider py-2 font-medium rounded transition-all cursor-pointer ${
                mode === 'signup' ? 'bg-[#202020] text-[#FFFFFF] font-semibold' : 'text-[#737373] hover:text-[#A6A6A6]'
              }`}
            >
              Create Account
            </button>
          </div>
        )}

        {errors.general && (
          <div className="mb-4 p-3 rounded bg-[#351010] border border-[#FFB4AB]/40 text-[#FFB4AB] text-xs flex items-center gap-2">
            <AlertCircleIcon size={16} />
            <span>{errors.general}</span>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-3 rounded bg-[#102A1A] border border-[#10B981]/40 text-[#A7F3D0] text-xs flex items-center gap-2">
            <CheckIcon size={16} />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === 'signup' && (
            <Input
              label="Full Name"
              type="text"
              placeholder="e.g. David Miller"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={errors.name}
              autoComplete="name"
            />
          )}

          <Input
            label="Email Address"
            type="email"
            placeholder="architect@domain.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
            autoComplete="email"
          />

          {mode !== 'forgot' && (
            <div className="flex flex-col gap-1">
              <Input
                label="Password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={errors.password}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              />
              {mode === 'signin' && (
                <button
                  type="button"
                  onClick={() => {
                    setMode('forgot');
                    setErrors({});
                  }}
                  className="self-end text-[11px] text-[#A6A6A6] hover:text-[#C5A77B] transition-colors mt-1 cursor-pointer"
                >
                  Forgot password?
                </button>
              )}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            isLoading={isLoading}
            className="w-full mt-2"
            rightIcon={<ArrowRightIcon size={16} />}
          >
            {mode === 'signin' ? 'Sign In to Workspace' : mode === 'signup' ? 'Create Studio Account' : 'Send Reset Link'}
          </Button>

          {mode === 'forgot' && (
            <button
              type="button"
              onClick={() => {
                setMode('signin');
                setSuccessMessage(null);
              }}
              className="text-xs text-[#A6A6A6] hover:text-[#FFFFFF] text-center mt-2 cursor-pointer"
            >
              Back to Sign In
            </button>
          )}
        </form>

        {/* Demo Fast Access Divider */}
        <div className="relative my-6 text-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-[#303030]" />
          </div>
          <span className="relative bg-[#181818] px-3 text-[10px] uppercase font-mono tracking-widest text-[#737373]">
            Evaluation Preview
          </span>
        </div>

        <Button
          type="button"
          variant="secondary"
          size="md"
          onClick={handleDemoAccess}
          className="w-full text-xs text-[#C5A77B] border-[#C5A77B]/40 hover:border-[#C5A77B]"
        >
          Instant Architect Demo Access →
        </Button>
      </Card>

      <p className="text-xs text-[#737373] text-center mt-6">
        Protected by Construtiva Authentication and Supabase Security.
      </p>
    </div>
  );
};

