# Playground

Entry: `/tools/playground`, under 工具. This is a native Vision Lab UI using the shared shell, typography, neutral tokens, selection menus and Hugeicons. It imports the full OpenHiggsfield catalog (38 models at commit `b16a0efe4d7e2707b56f8ccb02387fd2a9d2eddf`). Upstream attribution and licensing status are in `static/playground/NOTICE.md`.

## Generation service

The static site calls the dedicated Cloudflare Worker configured in `static/playground/config.json`. Local Python serves the same frontend; generation does not require restarting it. The service forwards only catalog-derived generation requests, status/cancel for session-owned jobs, and signed media-upload requests to `https://api.higgsfield.ai`. It does not use the visitor's GitHub account or the CMS identity.

Each visitor enters their own complete Higgsfield API key. The Worker stores it in a separate Durable Object session for 12 hours and deletes it on expiry or disconnect. The browser receives an opaque random bearer token and keeps that token in sessionStorage; it never writes the API key into localStorage, IndexedDB, public files or logs. Saving a key is not a validation of provider access. Real generation requires a valid key, model access and sufficient credits.

Provider uploads use `POST /files/generate-upload-url` and a browser PUT to the returned signed URL, followed by saving `public_url`. An unsuccessful upload is never attached. No Vercel Blob token or GitHub media storage is needed. Images are capped at 20 MB, video/audio at 100 MB in this UI.

History, draft and uploaded URL metadata live in IndexedDB in the current browser. Sixty non-favorite completed records are kept; favorites and active jobs are retained. Media itself remains on provider storage and may expire. Leaving the route stops status polling; returning resumes it. A ten-minute polling deadline pauses querying, not the provider job. Cancellation calls the provider cancellation endpoint. Reconnecting creates a new session and cannot claim another session's pending jobs.

Generation submissions have an idempotency key and are not automatically retried after ambiguous network failures. The history record explains that the provider must be checked before submitting again.

## Update and deploy

```sh
node scripts/sync_playground.mjs /path/to/reviewed/open-higgsfield-checkout
node --test tests/playground_contract.mjs
BROWSER_CHANNEL=chrome python3 tests/browser_playground.py
npx --yes wrangler@4.50.0 deploy --config playground-service/wrangler.jsonc
```

Review changes to the catalog and mapper; UI controls are derived from the catalog. Model paths/settings reflect the upstream snapshot, not a claim that every model was tested against a paid account.

The Worker uses the existing Cloudflare account, a new `vision-lab-playground` service and its own session namespace. It does not modify the submissions Worker. Allowed origins are the public Pages origin and local preview ports 8787, 8792 and 8794. Keep secrets out of the Worker vars and website config.

Before a site release, follow the project chat-coordination rule, run the full shell regression and export the verified current public data. GitHub Pages includes a direct `/tools/playground` route; the Worker runs separately from Pages.
