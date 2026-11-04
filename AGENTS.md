# GitHub account for this project

- Use the GitHub account `visiondesignlab` for this project and its repositories.
- Use the local `gh` command on PATH for GitHub operations. This Mac's project-aware wrapper selects `visiondesignlab` without changing the account used by other projects.
- Before a GitHub write, verify `gh api user --jq .login` returns `visiondesignlab`.
- Do not substitute a GitHub plugin connection authenticated as a different account. If authentication is missing, complete login for `visiondesignlab` rather than falling back to `neoedon`.
- This Mac has a conditional Git configuration for this directory and its child repositories: author `vision design lab`, email `352353897+visiondesignlab@users.noreply.github.com`, and HTTPS authentication as `visiondesignlab`.
- For new repositories, use HTTPS GitHub remotes so the configured credential helper is used. Do not change existing remotes or create remote repositories unless the task requires it.
