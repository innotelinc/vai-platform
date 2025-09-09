'use client';

import posthog from 'posthog-js';
import { useEffect } from 'react';

import { useAuth } from '@/lib/auth';

/**
 * PostHogIdentify
 * ---------------
 * A tiny client-side component that calls `posthog.identify` once the
 * authenticated user object is available.  It also resets PostHog when the
 * user logs out or switches accounts.
 *
 * This component is intended to be rendered high in the React tree (e.g. in
 * `app/layout.tsx`) so that PostHog always knows which user is active for the
 * current browser session.
 */
export default function PostHogIdentify() {
    const { user } = useAuth();

    useEffect(() => {
        // Only run if PostHog is enabled
        if (process.env.NEXT_PUBLIC_ENABLE_POSTHOG !== 'true') {
            return;
        }

        if (user) {
            try {
                // Identify the user in PostHog with their unique id and useful traits
                posthog.identify(String(user.id ?? ''));
            } catch (err) {
                // Silently ignore identification errors so they don't break the app

                console.warn('Failed to identify user in PostHog', err);
            }
        } else {
            // If the user logs out, clear the PostHog identity so future anonymous
            // interactions aren't associated with the previous account.
            posthog.reset();
        }
    }, [user]);

    // This component does not render anything
    return null;
}
