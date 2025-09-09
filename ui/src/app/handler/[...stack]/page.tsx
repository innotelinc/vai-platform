import { StackHandler } from "@stackframe/stack";

import { stackServerApp } from "../../../stack";

const authProvider = process.env.NEXT_PUBLIC_AUTH_PROVIDER;

export default function Handler(props: unknown) {
  if (authProvider === "local") {
    // Return a simple message when using local auth
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h1>Local Auth Mode</h1>
        <p>Stack Auth handler is disabled when using local authentication.</p>
      </div>
    );
  }
  return <StackHandler
    fullPage
    app={stackServerApp}
    routeProps={props}
  />;
}
