/**
 * Route /auth: sign in or create an account (POST /api/v1/auth/login and /signup), or enter
 * the demo workspace.
 */
import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { DEMO_ALLOWED, useAuth } from '../../context/AuthContext';
import { SESSION_NOTICE_KEY } from '../../lib/api';
import '../dashboard/dashboard.css';
import { ArchMark, ArrowRight } from '../dashboard/icons';

const HERO = '/assets/dash/villa-marble.webp';

type Mode = 'signin' | 'signup';
type Errors = { name?: string; email?: string; password?: string; general?: string };

export const AuthPage: React.FC = () => {
  const [mode, setMode] = useState<Mode>('signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(() => {
    // "Your session has expired. Please sign in again." after an automatic sign-out
    try {
      const saved = sessionStorage.getItem(SESSION_NOTICE_KEY);
      if (saved) sessionStorage.removeItem(SESSION_NOTICE_KEY);
      return saved;
    } catch {
      return null;
    }
  });

  const { signIn, signUp, loginAsDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/home';

  const validate = (): boolean => {
    const errs: Errors = {};
    if (mode === 'signup' && !name.trim()) errs.name = 'Full name is required';
    if (!email.trim()) errs.email = 'Email address is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = 'Please enter a valid email address';
    if (!password) errs.password = 'Password is required';
    else if (password.length < 6) errs.password = 'Password must be at least 6 characters';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice(null);
    if (!validate()) return;

    setIsLoading(true);
    setErrors({});
    try {
      if (mode === 'signin') await signIn(email, password);
      else await signUp(name, email, password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      setErrors({ general: err instanceof Error ? err.message : 'Authentication failed. Please try again.' });
      setIsLoading(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setErrors({});
    setNotice(null);
  };

  const handleDemoAccess = () => {
    loginAsDemo();
    navigate(from, { replace: true });
  };

  return (
    <div className="cv" data-page="auth">
      <header className="cv-header cv-auth-head">
        <a href="/" className="cv-auth-brand">
          <span className="cv-chip">
            <ArchMark />
          </span>
          Constriva
        </a>
        <a href="/" className="cv-auth-back">
          Back to site
        </a>
      </header>

      <main className="cv-main cv-auth">
        <section className="cv-auth-art cv-fade">
          <div className="cv-zoom">
            <img src={HERO} alt="A symmetrical white marble villa at dusk with columns, tall windows and a polished marble forecourt" />
            <svg aria-hidden="true" viewBox="0 0 736 736" preserveAspectRatio="xMidYMid slice">
              <defs>
                <linearGradient id="cvAuthScan" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#7ce8f2" stopOpacity="0" />
                  <stop offset=".85" stopColor="#bff6fb" stopOpacity=".2" />
                  <stop offset="1" stopColor="#ffffff" stopOpacity=".65" />
                </linearGradient>
              </defs>
              <rect className="cv-scan" x="0" y="0" width="736" height="34" fill="url(#cvAuthScan)" style={{ mixBlendMode: 'screen', animationDuration: '8s' }} />
            </svg>
          </div>
          <div className="cv-auth-copy cv-rise">
            <p className="cv-eyebrow">Architectural intelligence platform</p>
            <h1>{mode === 'signin' ? 'Welcome back' : 'Create studio account'}</h1>
            <p>
              {mode === 'signin'
                ? 'Sign in to access your interactive 3D floor plans and BOQ sheets.'
                : 'Turn 2D architectural drawings into 3D walkthroughs and bills of quantities.'}
            </p>
          </div>
        </section>

        <section className="cv-auth-side">
          <form className="cv-card cv-card-glow cv-auth-form cv-rise" style={{ ['--d' as string]: '.25s' }} onSubmit={handleSubmit} noValidate>
            <div className="cv-toggle" role="group" aria-label="Account">
              <button type="button" aria-pressed={mode === 'signin'} onClick={() => switchMode('signin')}>
                Sign in
              </button>
              <button type="button" aria-pressed={mode === 'signup'} onClick={() => switchMode('signup')}>
                Create account
              </button>
            </div>

            {errors.general && (
              <p className="cv-error" role="alert">
                {errors.general}
              </p>
            )}
            {notice && (
              <p className="cv-notice" role="status">
                {notice}
              </p>
            )}

            {mode === 'signup' && (
              <label className="cv-label">
                Full name
                <input
                  className="cv-input"
                  type="text"
                  autoComplete="name"
                  placeholder="e.g. David Miller"
                  value={name}
                  aria-invalid={errors.name ? true : undefined}
                  onChange={(e) => setName(e.target.value)}
                />
                {errors.name && <span className="cv-field-error">{errors.name}</span>}
              </label>
            )}

            <label className="cv-label">
              Email
              <input
                className="cv-input"
                type="email"
                autoComplete="email"
                placeholder="architect@domain.com"
                value={email}
                aria-invalid={errors.email ? true : undefined}
                onChange={(e) => setEmail(e.target.value)}
              />
              {errors.email && <span className="cv-field-error">{errors.email}</span>}
            </label>

            <label className="cv-label">
              Password
              <input
                className="cv-input"
                type="password"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                placeholder="Your password"
                value={password}
                aria-invalid={errors.password ? true : undefined}
                onChange={(e) => setPassword(e.target.value)}
              />
              {errors.password && <span className="cv-field-error">{errors.password}</span>}
            </label>

            <button type="submit" className="cv-btn cv-btn-primary" style={{ minHeight: 52 }} disabled={isLoading}>
              {isLoading ? 'Authenticating…' : mode === 'signin' ? 'Sign in to workspace' : 'Create studio account'}
              <ArrowRight />
            </button>

            {DEMO_ALLOWED && (
              <>
                <div className="cv-or" aria-hidden="true">
                  or
                </div>

                <button type="button" className="cv-btn" style={{ minHeight: 52 }} onClick={handleDemoAccess}>
                  <span className="cv-dot cv-pulse" style={{ width: 8, height: 8 }} aria-hidden="true" />
                  Instant architect demo access
                </button>
              </>
            )}
          </form>
        </section>
      </main>
    </div>
  );
};
