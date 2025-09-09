'use client';

import { StackClientApp,StackProvider, StackTheme, useUser as useStackUser } from '@stackframe/stack';
import React, { useEffect, useState } from 'react';

import logger from '@/lib/logger';

import { StackAuthService } from '../services';
import type { AuthUser } from '../types';
import { AuthContext } from './AuthProvider';

// Create a singleton StackClientApp instance to prevent multiple initializations
let stackClientAppInstance: StackClientApp<true, string> | null = null;

function getStackClientApp(): StackClientApp<true, string> {
  if (!stackClientAppInstance) {
    logger.debug('[StackProviderWrapper] Creating singleton StackClientApp instance');
    stackClientAppInstance = new StackClientApp({
      tokenStore: "nextjs-cookie",
      urls: {
        afterSignIn: "/after-sign-in"
      }
    });
  }
  return stackClientAppInstance;
}

interface StackProviderWrapperProps {
  service: StackAuthService;
  children: React.ReactNode;
}

// Stack-specific context provider that uses the useUser hook
function StackAuthContextProvider({ service, children }: { service: StackAuthService; children: React.ReactNode }) {
  const renderCount = React.useRef(0);
  const lastUserId = React.useRef<string | undefined>(undefined);
  renderCount.current++;

  logger.debug(`[StackAuthContextProvider] Render #${renderCount.current} - Starting`);

  const stackUser = useStackUser(); // Always call the hook
  const [isInitialized, setIsInitialized] = useState(false);

  // Track if user actually changed
  const userChanged = lastUserId.current !== stackUser?.id;
  if (userChanged) {
    lastUserId.current = stackUser?.id;
  }

  logger.debug(`[StackAuthContextProvider] Render #${renderCount.current} - stackUser:`, {
    hasUser: !!stackUser,
    userId: stackUser?.id,
    isInitialized,
    userChanged
  });

  useEffect(() => {
    // Only log and update if user actually changed
    if (!userChanged && isInitialized) {
      return;
    }

    logger.debug('[StackAuthContextProvider] useEffect triggered (user changed)', {
      hasUser: !!stackUser,
      userId: stackUser?.id,
      isInitialized,
      isStackAuthService: service instanceof StackAuthService
    });

    // Only update the service once when user becomes available
    if (!isInitialized && service instanceof StackAuthService && stackUser) {
      logger.debug('[StackAuthContextProvider] Setting user instance in service', {
        userId: stackUser.id
      });
      service.setUserInstance(stackUser);
      setIsInitialized(true);
    }
  }, [service, stackUser, isInitialized, userChanged]);

  const getAccessToken = React.useCallback(() => {
    logger.debug('[StackAuthContextProvider] getAccessToken called');
    return service.getAccessToken();
  }, [service]);

  // Stabilize the context value to prevent unnecessary re-renders
  const contextValue = React.useMemo(() => {
    const isAuth = service.isAuthenticated();
    // IMPORTANT: Stay in loading state until service is initialized (has user set)
    // Even if stackUser exists, we're still loading until setUserInstance is called
    const loadingState = !isInitialized;

    const value = {
      service,
      user: stackUser as AuthUser,  // Pass the actual Stack CurrentUser
      isAuthenticated: isAuth,
      loading: loadingState,  // Loading until service is initialized
      getAccessToken,
      provider: service.getProviderName(),
    };

    logger.debug('[StackAuthContextProvider] Context value created', {
      isAuthenticated: isAuth,
      loading: loadingState,
      hasUser: !!value.user,
      userId: stackUser?.id,
      isInitialized,
      provider: value.provider,
      serviceHasUser: isAuth
    });

    return value;
  }, [service, stackUser, isInitialized, getAccessToken]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

export function StackProviderWrapper({ service, children }: StackProviderWrapperProps) {
  logger.debug('[StackProviderWrapper] Rendering wrapper');

  // Use the singleton instance
  const stackClientApp = getStackClientApp();

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
