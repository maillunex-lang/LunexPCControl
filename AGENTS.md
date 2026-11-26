# Mandatory development rules

GitHub main is the canonical source of LunexPCControl. Every development milestone must preserve reproducible deployment on a fresh supported Ubuntu VPS, independent of the original VPS and Termalin.

- Commit all first-party source, build scripts, dependency manifests and pinned versions, deployment templates, migrations, tests and documentation. Include redistributable third-party source or reproducible pinned retrieval instructions and licenses.
- Never commit secrets, private keys, live databases, screenshots, tokens or personal configuration. Provide templates, secret generation and encrypted backup/restore instructions instead.
- Every new feature must update the fresh installer, upgrade/rollback path, backup/restore coverage, configuration examples and deployment documentation as applicable. Do not leave production-only manual changes undocumented or untracked.
- Keep a deployment inventory and compare installed code/configuration templates with the repository. Run tests, clean-install smoke tests and CI; push the completed milestone to GitHub and verify the remote commit and CI. Report any failed or unverified gate explicitly.
- A milestone is not fully portable until a fresh supported VPS deployment and functional smoke test succeed. Test Windows/Linux enrollment, portal, video and MCP functions actually shipped; do not claim unimplemented functionality.
- Current portability debt: installer directory creation for installer/ files, optional connector service provisioning, public HTTPS/domain configuration, complete encrypted state migration, automated restore and transactional upgrades, and independent clean VPS validation. Audit these against current code before closing them.
- Preserve unrelated services; never expose credentials or weaken authentication for portability. No paid API dependency.
