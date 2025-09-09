import type { AuthProvider } from '../types';
import type { IAuthService } from './interface';
import { LocalAuthService } from './localAuthService';
import { StackAuthService } from './stackAuthService';

export function createAuthService(provider?: AuthProvider | string): IAuthService {
  const authProvider = provider || process.env.NEXT_PUBLIC_AUTH_PROVIDER || 'stack';

  switch (authProvider) {
    case 'stack':
      return new StackAuthService();
    case 'local':
      return new LocalAuthService();
    // Future providers can be added here
    // case 'auth0':
    //   return new Auth0Service();
    // case 'supabase':
    //   return new SupabaseService();
    default:
      console.warn(`Unknown auth provider: ${authProvider}, falling back to local`);
      return new LocalAuthService();
  }
}

export type { IAuthService } from './interface';
export { LocalAuthService } from './localAuthService';
export { StackAuthService } from './stackAuthService';

