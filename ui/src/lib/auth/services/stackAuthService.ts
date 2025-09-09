'use client';

import type { CurrentUser } from '@stackframe/stack';

import logger from '@/lib/logger';

import type { IAuthService } from './interface';

export class StackAuthService implements IAuthService {
  private userInstance: CurrentUser | null = null;

  // Set the user instance from the Stack useUser hook
  setUserInstance(user: CurrentUser) {
    this.userInstance = user;
  }

  async getAccessToken(): Promise<string> {
    if (!this.userInstance) {
      throw new Error('User not initialized');
    }
    const authJson = await this.userInstance.getAuthJson();
    if (!authJson.accessToken) {
      throw new Error('No access token available');
    }
    return authJson.accessToken;
  }

  async refreshToken(): Promise<string> {
    if (!this.userInstance) {
      throw new Error('User not initialized');
    }
    // Stack handles token refresh internally
    const authJson = await this.userInstance.getAuthJson();
    if (!authJson.accessToken) {
      throw new Error('No access token available');
    }
    return authJson.accessToken;
  }

  async getCurrentUser(): Promise<CurrentUser | null> {
    // Return the actual Stack user instance
    return this.userInstance;
  }

  isAuthenticated(): boolean {
    return !!this.userInstance;
  }

  redirectToLogin(): void {
    if (typeof window !== 'undefined') {
      window.location.href = '/handler/sign-in';
    }
  }

  async logout(): Promise<void> {
    if (this.userInstance && this.userInstance.signOut) {
      await this.userInstance.signOut();
    }
  }

  getSelectedTeam(): unknown {
    return this.userInstance?.selectedTeam;
  }

  async listPermissions(team?: unknown): Promise<Array<{ id: string }>> {
    if (!this.userInstance || !this.userInstance.listPermissions) {
      return [];
    }
    const targetTeam = team || this.userInstance.selectedTeam;
    if (!targetTeam) {
      return [];
    }
    try {
      const perms = await this.userInstance.listPermissions(targetTeam);
      return Array.isArray(perms) ? perms : [];
    } catch (error) {
      logger.error('Error listing permissions:', error);
      return [];
    }
  }

  getProviderName(): string {
    return 'stack';
  }
}

