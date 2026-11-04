# CMS implementation

The review entry opens a password-protected view inside the shared site shell. Content entities retain the existing public types and JSON store. Workflow: draft → pending → published; rejection requires a reason; published items can be taken offline. Edits to published content use a separate revision until approved, keeping the last approved version live.

Controls: dashboard counts; status/type/search filters; content table with automatic incremental loading on scroll; new/edit form (metadata, source, cover/video/image uploads, prompt, steps, tags, assets); private preview; submit/approve/reject/unpublish actions; review history; password settings and logout.

UI must strictly match the existing site: load `static/style.css` directly and reuse its tokens, logo/sidebar structure, typography, pills and dropdown interaction. No separate dashboard visual identity.

Implementation: `cms_auth.py`, `cms_content.py`, `server.py`, `store.py`, `static/cms.{html,css,js}` and public entry links. Authentication uses a password hash, expiring HttpOnly sessions, CSRF checks and rate limits. Public APIs and local media delivery exclude unpublished revisions. No database replacement or external deployment required.

Validation: isolated temporary JSON/media stores for HTTP authentication, workflow, revision isolation, validation, media access and concurrency tests; existing handoff regressions; Playwright walkthrough on a temporary fixture server; read-only smoke check of the running platform after restart. Do not run the old destructive E2E against real cases.

## Verified implementation

- 13 HTTP/unit regressions pass, including valid video upload/transcode and public byte-range playback. All CMS mutations in tests use temporary storage.
- Browser walkthrough: password login; create brand Skill; upload cover and Markdown attachment; save draft; confirm anonymous content/media return 404; submit and approve; anonymous gallery and detail become visible; edit published title and verify original stays live.
- Desktop and 390px editor checked; no horizontal page overflow. CMS loads the same public stylesheet, sidebar markup and menu behavior.
- Local server at `http://127.0.0.1:8787` restarted and checked with real data. Admin API rejects anonymous reads, login/logout works, public manual remains accessible, and no fixture content exists in the real store.

- Scroll-loading update: removed page numbers and navigation buttons. Rows append in batches of 15; status/type/search changes reset the list and release the previous observer. Verified 159 unique rows load to completion, search and empty results reset correctly, status filters reset correctly, and appended rows still open previews. No content mutations were performed.

- Control alignment: status text is centered without the decorative dot; fixed-height CMS controls use one line-height and optical padding rule. Browser measurements show zero horizontal/vertical text-box offset for 71 list badges/buttons, preview controls, and the editor save/submit/upload controls. Existing font, colors, heights and pill style are retained.

- Primary navigation is owned by the shared `index.html` shell. CMS login and authenticated screens mount inside `#app` through the same router as public tabs; the sidebar is never fetched, copied, replaced, or reloaded. CMS-only destinations and logout live in the content area’s secondary navigation. `cms.html` is a compatibility symlink to the same entry document. CMS styles are scoped to its view, pending renders are invalidated on exit, and the router protects unsaved edits for links and browser history.

- Shared-router verification: 14 isolated regression tests pass. Live CMS/public routes return the same entry document. Browser checks confirm one unchanged document loader and sidebar DOM node across six CMS/public tab switches; CMS filters and preview work, canceling a primary-link or browser-back navigation retains unsaved edits, and ordinary back/forward restores the intended view. No content was saved or published during these navigation checks.
