import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User } from '../types';

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
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setUser(JSON.parse(stored));
      } else {
        // Provide demo user initially so pages are easily testable
        const demoUser: User = {
          id: 'usr_demo_101',
          email: 'architect@construtiva.ai',
          name: 'Elena Rostova',
        };
        setUser(demoUser);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(demoUser));
      }
    } catch {
      // ignore JSON parse error
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signIn = async (email: string, _password: string): Promise<void> => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 600)); // simulate auth latency
    const loggedUser: User = {
      id: 'usr_' + Math.random().toString(36).substring(2, 9),
      email,
      name: email.split('@')[0],
    };
    setUser(loggedUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(loggedUser));
    setIsLoading(false);
  };

  const signUp = async (name: string, email: string, _password: string): Promise<void> => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    const newUser: User = {
      id: 'usr_' + Math.random().toString(36).substring(2, 9),
      email,
      name,
    };
    setUser(newUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser));
    setIsLoading(false);
  };

  const signOut = () => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  const loginAsDemo = () => {
    const demoUser: User = {
      id: 'usr_demo_101',
      email: 'architect@construtiva.ai',
      name: 'Elena Rostova',
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
