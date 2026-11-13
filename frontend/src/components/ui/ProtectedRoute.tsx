import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#101010] flex items-center justify-center text-[#A6A6A6]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-[#C5A77B] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs uppercase tracking-widest font-mono">Loading Constriva...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

