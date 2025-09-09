// This file configures the initialization of Sentry on the client.
// The added config here will be used whenever a users loads a page in their browser.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from "@sentry/nextjs";
import posthog from "posthog-js";

// Only initialize Sentry if explicitly enabled and DSN is provided
const enableSentry = process.env.NEXT_PUBLIC_ENABLE_SENTRY === 'true' &&
                     process.env.NEXT_PUBLIC_SENTRY_DSN;

if (enableSentry) {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

    // Add optional integrations for additional features
    integrations: [
      Sentry.replayIntegration(),
    ],

    // Define how likely Replay events are sampled.
    // This sets the sample rate to be 10%. You may want this to be 100% while
    // in development and sample at a lower rate in production
    replaysSessionSampleRate: 0.1,

    // Define how likely Replay events are sampled when an error occurs.
    replaysOnErrorSampleRate: 1.0,

    // Setting this option to true will print useful information to the console while you're setting up Sentry.
    debug: false,
    enabled: process.env.NEXT_PUBLIC_NODE_ENV === 'production'
  });
  console.log('Sentry initialized for client-side error tracking');
} else {
  console.log('Sentry disabled (NEXT_PUBLIC_ENABLE_SENTRY=false or DSN not configured)');
}

// Only initialize PostHog if explicitly enabled and key is provided
const shouldEnablePostHog = process.env.NEXT_PUBLIC_ENABLE_POSTHOG === 'true' &&
                           process.env.NEXT_PUBLIC_POSTHOG_KEY;

if (shouldEnablePostHog) {//FIXME: remove default empty value
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY||'', {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "/ingest",//https://us.i.posthog.com
    ui_host: process.env.NEXT_PUBLIC_POSTHOG_UI_HOST || "https://us.posthog.com",
    capture_pageview: 'history_change',
    capture_pageleave: true,    // Enable pageleave capture
    capture_exceptions: true,   // Capture exceptions via Error Tracking
    debug: process.env.NEXT_PUBLIC_NODE_ENV === 'development',  // Enable debug in development
  });
  console.log('PostHog analytics initialized');
} else {
  console.log('PostHog disabled (NEXT_PUBLIC_ENABLE_POSTHOG=false or key not configured)');
}


export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
