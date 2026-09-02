"use client";

import { useAuth, RoleEnum } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        window.location.href = '/login';
      } else {
        const dashboardRoutes: Record<RoleEnum, string> = {
          'Wildlife Researcher': '/dashboards/researcher',
          'Conservation Officer': '/dashboards/conservation-officer',
          'Forest Department Officer': '/dashboards/forest-officer',
          'Administrator': '/dashboards/admin',
        };
        window.location.href = dashboardRoutes[user.role];
      }
    }
  }, [user, loading, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-600"></div>
    </div>
  );
}
