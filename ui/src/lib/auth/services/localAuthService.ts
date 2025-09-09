'use client';

import logger from '@/lib/logger';

import type { LocalUser } from '../types';
import type { IAuthService } from './interface';

export class LocalAuthService implements IAuthService {
  private currentUser: LocalUser | null = null;
  private currentToken: string | null = null;
  private authPromise: Promise<void> | null = null;
  private static instance: LocalAuthService | null = null;

  constructor() {
    // Singleton pattern to ensure single initialization
    if (LocalAuthService.instance) {
      return LocalAuthService.instance;
    }
    LocalAuthService.instance = this;

    // Initialize auth on creation
    if (typeof window !== 'undefined') {
      this.authPromise = this.initializeAuth();
    }
  }

  private async initializeAuth(): Promise<void> {
    try {
      const response = await fetch('/api/auth/oss');
      if (response.ok) {
        const data = await response.json();
        this.currentToken = data.token;
        this.currentUser = data.user;
        logger.info('OSS auth initialized', { user: data.user });
      } else {
        logger.error('Failed to initialize OSS auth');
      }
    } catch (error) {
      logger.error('Error initializing OSS auth', error);
    }
  }

  private async ensureAuth(): Promise<void> {
    if (this.authPromise) {
      await this.authPromise;
    } else if (!this.currentToken && typeof window !== 'undefined') {
      this.authPromise = this.initializeAuth();
      await this.authPromise;
    }
  }

  async getAccessToken(): Promise<string> {
    if (typeof window === 'undefined') {
      // SSR: Server will handle this
      return 'ssr-placeholder-token';
    }

    await this.ensureAuth();

    if (!this.currentToken) {
      logger.warn('No OSS token available after initialization');
      return '';
    }
    return this.currentToken;
  }

  async refreshToken(): Promise<string> {
    // For local mode, just return the same token
    return this.getAccessToken();
  }

  async getCurrentUser(): Promise<LocalUser | null> {
    if (typeof window === 'undefined') {
      // SSR: Server will handle this
      return null;
    }

    await this.ensureAuth();

    if (!this.currentUser) {
      logger.warn('No OSS user available after initialization');
      return null;
    }

    return this.currentUser;
  }

  isAuthenticated(): boolean {
    // In local mode, always authenticated
    return true;
  }

  redirectToLogin(): void {
    // No-op for local mode
    logger.info('Login redirect not needed in local mode');
  }

  async logout(): Promise<void> {
    // In OSS mode, logout would require server-side cookie clearing
    // For now, just clear the cached user
    this.currentUser = null;
    logger.info('Logout requested in OSS mode - server cookies need to be cleared');
  }

  getProviderName(): string {
    return 'local';
  }
}

