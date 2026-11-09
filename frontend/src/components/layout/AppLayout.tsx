import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '../ui/Navbar';

export const AppLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col font-sans">
      <Navbar />
      <div className="flex-1 flex flex-col">
        <Outlet />
      </div>
    </div>
  );
};

