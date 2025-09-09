'use client';

import React from 'react';

import logger from '@/lib/logger';

import { useAuthContext } from '../providers/AuthProvider';

export function useAuth() {
  const renderCount = React.useRef(0);
  renderCount.current++;

  const context = useAuthContext();

  logger.debug('[useAuth] Hook called', {
    renderCount: renderCount.current,
    hasUser: !!context.user,
    userId: context.user?.id,
    isAuthenticated: context.isAuthenticated,
    loading: context.loading,
    provider: context.provider
  });

  // Memoize functions that are recreated on every render
  const logout = React.useCallback(() => context.service.logout(), [context.service]);
  const redirectToLogin = React.useCallback(() => context.service.redirectToLogin(), [context.service]);
  const getSelectedTeam = React.useCallback(() => context.service.getSelectedTeam?.(), [context.service]);
  const listPermissions = React.useCallback(
    (team?: unknown) => context.service.listPermissions?.(team) || Promise.resolve([]),
    [context.service]
  );

  return React.useMemo(() => ({
    // Core functionality
    getAccessToken: context.getAccessToken,
    user: context.user,  // This is now AuthUser (CurrentUser | LocalUser)
    isAuthenticated: context.isAuthenticated,
    loading: context.loading,

    // Service methods
    logout,
    redirectToLogin,

    // Provider info
    provider: context.provider,

    // Stack-specific methods (optional)
    getSelectedTeam,
    listPermissions,
  }), [
    context.getAccessToken,
    context.user,
    context.isAuthenticated,
    context.loading,
    context.provider,
    logout,
    redirectToLogin,
    getSelectedTeam,
    listPermissions,
  ]);
}

// Compatibility wrapper for gradual migration from useUser
export function useUser(options?: { or?: 'redirect' }) {
  const auth = useAuth();

  // Handle redirect option
  if (options?.or === 'redirect' && !auth.isAuthenticated && !auth.loading) {
    auth.redirectToLogin();
  }

  // Return Stack-compatible interface
  return {
    ...auth.user,
    getAuthJson: async () => ({
      accessToken: await auth.getAccessToken(),
    }),
    selectedTeam: auth.getSelectedTeam(),
    listPermissions: auth.listPermissions,
    signOut: auth.logout,
  };
}

