import { redirect } from "next/navigation";

import SignInClient from "@/components/SignInClient";
import { getServerAuthProvider,getServerUser } from "@/lib/auth/server";
import logger from '@/lib/logger';
import { getRedirectUrl } from "@/lib/utils";

export default async function Home() {
  const authProvider = getServerAuthProvider();

  // For local/OSS provider, always redirect to workflow page
  if (authProvider === 'local') {
    logger.debug('Redirecting to workflow page for local provider');
    redirect('/create-workflow');
  }

  const user = await getServerUser();

  logger.debug(`authProvider: ${authProvider}, user: ${JSON.stringify(user)}`);

  if (user) {
    try {
      // For Stack provider, get the token and permissions
      if (authProvider === 'stack' && 'getAuthJson' in user) {
        const token = await user.getAuthJson();
        const permissions = 'listPermissions' in user && 'selectedTeam' in user
          ? await user.listPermissions(user.selectedTeam!) ?? []
          : [];
        const redirectUrl = await getRedirectUrl(token?.accessToken ?? "", permissions);
        logger.debug(`redirectUrl: ${redirectUrl}`);
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
