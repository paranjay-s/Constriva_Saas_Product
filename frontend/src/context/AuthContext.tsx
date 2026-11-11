import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User } from '../types';
import { authApi, TOKEN_STORAGE_KEY } from '../lib/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => void;
  loginAsDemo: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = 'construtiva_auth_user';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
        const storedUser = localStorage.getItem(STORAGE_KEY);

        if (storedToken) {
          try {
            // Verify token with backend /api/v1/auth/me
            const profile = await authApi.getProfile();
            const liveUser: User = {
              id: profile.id,
              email: profile.email,
              name: profile.full_name || profile.email.split('@')[0],
            };
            setUser(liveUser);
            localStorage.setItem(STORAGE_KEY, JSON.stringify(liveUser));
            return;
          } catch (profileErr) {
            console.warn('Could not validate session with backend:', profileErr);
            // If offline, use cached user if available
            if (storedUser) {
              setUser(JSON.parse(storedUser));
              return;
            }
          }
        }

        if (storedUser) {
          setUser(JSON.parse(storedUser));
        } else {
          // Provide demo user initially so pages are easily testable
          const demoUser: User = {
            id: '00000000-0000-0000-0000-000000000001',
            email: 'demo@construtiva.ai',
            name: 'Demo Architect',
          };
          setUser(demoUser);
          localStorage.setItem(STORAGE_KEY, JSON.stringify(demoUser));
        }
      } catch {
        // ignore JSON parse error
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const signIn = async (email: string, password: string): Promise<void> => {
    setIsLoading(true);
    try {
      const res = await authApi.login({ email, password });
      const loggedUser: User = {
        id: res.user.id,
        email: res.user.email,
        name: res.user.full_name || email.split('@')[0],
      };
      setUser(loggedUser);
      localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(loggedUser));
    } catch (err) {
      console.error('Sign in error:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const signUp = async (name: string, email: string, password: string): Promise<void> => {
    setIsLoading(true);
    try {
      const res = await authApi.signup({ full_name: name, email, password });
      const newUser: User = {
        id: res.user.id,
        email: res.user.email,
        name: res.user.full_name || name,
      };
      setUser(newUser);
      localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser));
    } catch (err) {
      console.error('Sign up error:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const signOut = () => {
    setUser(null);
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(STORAGE_KEY);
  };

  const loginAsDemo = () => {
    const demoUser: User = {
      id: '00000000-0000-0000-0000-000000000001',
      email: 'demo@construtiva.ai',
      name: 'Demo Architect',
    };
    setUser(demoUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(demoUser));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        signIn,
        signUp,
        signOut,
        loginAsDemo,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
