import { redirect } from "next/navigation";

import { getServerAuthProvider, getServerUser } from "@/lib/auth/server";
import { getRedirectUrl } from "@/lib/utils";

export default async function AfterSignInPage() {
    const authProvider = getServerAuthProvider();
    const user = await getServerUser();

    if (authProvider === 'stack' && user && 'getAuthJson' in user) {
        const token = await user.getAuthJson();
        const permissions = 'listPermissions' in user && 'selectedTeam' in user
            ? await user.listPermissions(user.selectedTeam!) ?? []
            : [];
        const redirectUrl = await getRedirectUrl(token?.accessToken ?? "", permissions);
        redirect(redirectUrl);
    }
    // For local provider or if user is not available, redirect to create-workflow
    redirect('/create-workflow');
}
