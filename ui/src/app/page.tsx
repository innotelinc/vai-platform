import { redirect } from "next/navigation";

import SignInClient from "@/components/SignInClient";
import { getServerAuthProvider,getServerUser } from "@/lib/auth/server";
import logger from '@/lib/logger';
import { getRedirectUrl } from "@/lib/utils";

export const dynamic = 'force-dynamic';

export default async function Home() {
  logger.debug('[HomePage] Starting Home page render');
  const authProvider = getServerAuthProvider();
  logger.debug('[HomePage] Auth provider:', authProvider);

  // For local/OSS provider, always redirect to workflow page
  if (authProvider === 'local') {
    logger.debug('[HomePage] Redirecting to workflow page for local provider');
    redirect('/create-workflow');
  }

  logger.debug('[HomePage] Getting server user...');
  const user = await getServerUser();

  logger.debug('[HomePage] Server user result:', {
    hasUser: !!user,
    userId: user?.id,
    authProvider
  });

  if (user) {
    try {
      // For Stack provider, get the token and permissions
      if (authProvider === 'stack' && 'getAuthJson' in user) {
        logger.debug('[HomePage] Getting auth token from Stack user...');
        const token = await user.getAuthJson();
        logger.debug('[HomePage] Got auth token:', { hasToken: !!token?.accessToken });
        const permissions = 'listPermissions' in user && 'selectedTeam' in user
          ? await user.listPermissions(user.selectedTeam!) ?? []
          : [];
        logger.debug('[HomePage] Got permissions:', { count: permissions.length });
        logger.debug('[HomePage] Getting redirect URL...');
        const redirectUrl = await getRedirectUrl(token?.accessToken ?? "", permissions);
        logger.debug('[HomePage] Redirecting to:', redirectUrl);
        redirect(redirectUrl);
      }
    } catch (error) {
      // If it's a Next.js redirect, let it through
      if (error instanceof Error && 'digest' in error &&
          typeof error.digest === 'string' && error.digest.startsWith('NEXT_REDIRECT')) {
        throw error;
      }
      // Only catch actual API errors
      console.error("API unavailable, showing sign-in:", error);
      // Show sign-in page if API is unavailable
    }
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
      }}
    >
      <SignInClient />
    </div>
  );
}
