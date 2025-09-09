import "server-only";

import { StackServerApp } from "@stackframe/stack";

const authProvider = process.env.NEXT_PUBLIC_AUTH_PROVIDER;

function createStackApp() {
  if (authProvider === "local") {
    // Return a dummy object when using local auth to prevent build errors
    return {} as StackServerApp;
  }
  // Only initialize Stack Auth when actually using it
  return new StackServerApp({
    tokenStore: "nextjs-cookie",
    urls: {
      afterSignIn: "/after-sign-in"
    }
  });
}

export const stackServerApp = createStackApp();
