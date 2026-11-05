# GitHub account for this project

- Use the GitHub account `visiondesignlab` for this project and its repositories.
- Use the local `gh` command on PATH for GitHub operations. This Mac's project-aware wrapper selects `visiondesignlab` without changing the account used by other projects.
- Before a GitHub write, verify `gh api user --jq .login` returns `visiondesignlab`.
- Do not substitute a GitHub plugin connection authenticated as a different account. If authentication is missing, complete login for `visiondesignlab` rather than falling back to `neoedon`.
- This Mac has a conditional Git configuration for this directory and its child repositories: author `vision design lab`, email `352353897+visiondesignlab@users.noreply.github.com`, and HTTPS authentication as `visiondesignlab`.
- For new repositories, use HTTPS GitHub remotes so the configured credential helper is used. Do not change existing remotes or create remote repositories unless the task requires it.

# Keep the in-app usage guide current

- User-facing help lives at `/guide` in the shared site shell. Do not restore a separate README page or a new-tab link.
- Navigation groups, labels, links, content counts, AI targets and brand-resource facts are read from their owning runtime sources. Do not duplicate those lists or freeze their counts in help text.
- When changing a user workflow (including CMS actions), update the corresponding steps in `static/guide-content.json` in the same change. New or retired navigation entries must pass `tests/test_guide.py` coverage checks.
- Keep operational/deployment details in the developer README, not in the user guide. Validate local and GitHub Pages routes when changing guide navigation.

# Typography

- Separate Chinese and English with one ASCII space in user-facing copy (e.g. “AI 导航”, “Agent 智能体”, “UI 设计”). Preserve URLs, IDs and code verbatim.

# Preserve the working application

- Merge selected source changes. Do not replace this working tree or its private CMS data with an older project copy, Pages build, seed or export.
- For changes to the shared shell, test the password gate at /review, the three custom sorting options at /?tab=skill_repo, /guide, and /tools/ai-nav in a browser. Run tests/browser_routes.py with its disposable store before publishing; never test mutation or deletion on the real catalog.
