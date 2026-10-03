# Releasing

Releases are cut by [release-please](https://github.com/googleapis/release-please),
not by hand. Every push to `main` runs `.github/workflows/release-automation.yml`,
which maintains a single release PR (`chore(main): release dograh X.Y.Z`) whose
version bump and changelog are derived from the conventional-commit subjects
merged since the last release. **Merging that PR is what cuts the release** — it
tags `dograh-vX.Y.Z` and publishes the GitHub release.

Merging the release PR is also what triggers
`.github/workflows/release-deployment.yml`, which builds the UI and deploys it
to Vercel production.

That deploy is triggered by the Release Please run itself
(`on.workflow_run`), not by `on: release: published`. The distinction matters:
GitHub **suppresses** runs caused by events a `GITHUB_TOKEN` creates, so a
release cut with the built-in token emits no `release` event and a workflow
listening for one never runs — a failure mode that looks like "the deploy just
quietly stopped". `workflow_run` events are emitted by Actions itself rather
than by a token, so they are not suppressed, and this repo no longer needs a
PAT to ship a release.

## The version baseline

`release-please-config.json` sets `package-name: dograh`, so release-please
looks for a tag named `dograh-v<version>` — **not** `v<version>`. The version in
`.release-please-manifest.json` must have a matching tag on `main`, or
release-please cannot build release notes against a previous release and fails
with:

```
release-please failed: Invalid previous_tag parameter
```

`.release-please-manifest.json` is the source of truth for the *next* release's
starting point, and release-please bumps it as part of the release PR. If it
ever names a version that has **no** tag (the state a fresh repo or a
hand-edited manifest starts in), tag the commit the manifest names:

```bash
git tag dograh-v1.45.0 && git push origin dograh-v1.45.0
```

The tag must point at the commit the manifest's version describes — usually
`main`'s HEAD at the time the manifest was written.

## What actually deploys to Vercel

Only `ui` does. The Vercel project's Root Directory is `ui`, so `vercel build`
at the repo root builds `ui` alone, and `ui/vercel.json` is the config Vercel
reads — a root `vercel.json` sitting beside it is **not** opened, so don't add
one expecting services mode to take effect.

`evals/visualizer` is not on Vercel either. It serves no traffic, and
`vercel build` has no per-service flag, so anything declared in a `services`
map would be built on every release and could fail the dashboard deploy.

**The `api` is deliberately not on Vercel.** It is a long-running server, not a
request handler: six WebSocket endpoints (`/ws/ari`, the WebRTC signaling
channels, agent streams) plus a `coturn` UDP dependency for TURN. Vercel's
WebSocket support is beta and limited to single-instance, session-scoped
connections, and UDP cannot go there at all. It keeps running as
`dograhai/dograh-api` on the container host beside Postgres, Redis and MinIO,
per `docker-compose.yaml`.

The `ui` reaches the API over the public internet via
`NEXT_PUBLIC_BACKEND_URL`. That is not a limitation to route around — the
browser opens the RTC WebSocket itself
(`useWebSocketRTC.tsx`), so the API has to be on a reachable URL regardless of
where it runs. That is also why there are no Vercel *service bindings* here: a
binding injects a URL for server-side code only, and the one caller is a
browser.

## Required repository secrets

Without these the workflows still run, but fail in ways that look like
something else — a release that never deploys, or an image push that 403s.
Set them under **Settings → Secrets and variables → Actions**.

| Secret | Used by | Why it is required |
|--------|---------|--------------------|
| `VERCEL_TOKEN` | `release-deployment.yml` | Vercel CLI auth for `vercel pull` / `build` / `deploy --prod`. |
| `VERCEL_ORG_ID` | `release-deployment.yml` | Which Vercel team owns the project. Use the **team id** (`team_…`) — `vercel pull` writes exactly that value into `.vercel/project.json` as `orgId`. |
| `VERCEL_PROJECT_ID` | `release-deployment.yml` | Which Vercel project to deploy (`prj_…`). |
| `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` | `docker-image.yml` | Pushes `dograh-api` / `dograh-ui` to Docker Hub. |
| `GHCR_USERNAME` / `GHCR_TOKEN` | `docker-image.yml` | Pushes the same images to GitHub Container Registry. |
| `SLACK_WEBHOOK_URL` | `api-tests.yml`, `release-deployment.yml` | Failure/success notifications. Optional: the notify steps skip when it is unset. |

`release-automation.yml` also needs **Settings → Actions → General → "Allow
GitHub Actions to create and approve pull requests"** enabled, or the release PR
cannot be opened at all:

```
release-please failed: GitHub Actions is not permitted to create or approve pull requests.
```

## Cutting a release, end to end

1. Merge your change to `main` with a conventional-commit subject
   (`feat:`, `fix:`, `perf:`, `docs:`, `refactor:`; `chore:` is hidden from the
   changelog).
2. Release Please opens or updates the release PR with the bumped version and
   changelog.
3. Review and merge the release PR. The tag `dograh-vX.Y.Z` and the GitHub
   release are created.
4. `release-deployment.yml` runs the Vercel production deploy and appends the
   deployment URL to the release notes.

If you merge the release PR and no deploy starts, check the Release Please run
rather than the deployment: on a run that only refreshed the release PR, the
deploy's `resolve` job reports "published no release" and stops there, which is
correct — there was nothing to ship.

## Local pre-flight

The config and manifest are ordinary JSON and can be checked before pushing:

```bash
python3 -m json.tool release-please-config.json >/dev/null && echo "config OK"
python3 -m json.tool .release-please-manifest.json >/dev/null && echo "manifest OK"
```

To confirm the tag the manifest names actually exists on the remote:

```bash
v=$(python3 -c "import json;print(json.load(open('.release-please-manifest.json'))['.'])")
git ls-remote --tags origin "dograh-v$v"
```

An empty result means the next run will fail with `Invalid previous_tag
parameter` — create the tag as shown above before pushing.