'use client';

import { StackClientApp,StackProvider, StackTheme, useUser as useStackUser } from '@stackframe/stack';
import React, { useEffect, useState } from 'react';

import { StackAuthService } from '../services';
import type { AuthUser } from '../types';
import { AuthContext } from './AuthProvider';

interface StackProviderWrapperProps {
  service: StackAuthService;
  children: React.ReactNode;
}

// Stack-specific context provider that uses the useUser hook
function StackAuthContextProvider({ service, children }: { service: StackAuthService; children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const stackUser = useStackUser(); // Always call the hook

  useEffect(() => {
    // Set the user instance in the service
    if (service instanceof StackAuthService && stackUser) {
      service.setUserInstance(stackUser);
      setLoading(false);
    } else if (!stackUser) {
      setLoading(false);
    }
  }, [service, stackUser]);

  const getAccessToken = React.useCallback(() => service.getAccessToken(), [service]);

  const contextValue = React.useMemo(() => ({
    service,
    user: stackUser as AuthUser,  // Pass the actual Stack CurrentUser
    isAuthenticated: service.isAuthenticated(),
    loading,
    getAccessToken,
    provider: service.getProviderName(),
  }), [service, stackUser, loading, getAccessToken]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

export function StackProviderWrapper({ service, children }: StackProviderWrapperProps) {
  // Create the Stack client app here, only when actually needed
  const stackClientApp = new StackClientApp({
    tokenStore: "nextjs-cookie",
    urls: {
      afterSignIn: "/after-sign-in"
    }
  });

  return (
    <StackProvider app={stackClientApp}>
      <StackTheme>
        <StackAuthContextProvider service={service}>
          {children}
        </StackAuthContextProvider>
      </StackTheme>
    </StackProvider>
  );
}
