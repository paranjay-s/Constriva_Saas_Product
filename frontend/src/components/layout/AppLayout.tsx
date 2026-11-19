import React from 'react';
import { Outlet } from 'react-router-dom';
import { DashHeader } from '../../features/dashboard';

/** Signed-in pages: the dashboard header on top, the page below it. */
export const AppLayout: React.FC = () => {
  return (
    <div className="cv">
      <DashHeader />
      <Outlet />
    </div>
  );
};
