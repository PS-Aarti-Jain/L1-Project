# Security Guidelines for DevAssist

This document outlines the security controls and requirements for deploying and using the DevAssist orchestrator and MCP server.

## API Key Security

All secrets must be managed securely:
- Never commit `.env` files or raw API keys to Git repositories.
- Use a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault) in production environments.
- In development, store credentials locally in a `.env` file at the root of the backend folder.
- Ensure that the `.gitignore` file includes `.env` and all files ending in `.local`.

## GitHub Personal Access Token (PAT) Least Privilege

When configuring the `GITHUB_PAT` for the GitHub MCP server, adhere to the principle of least privilege:
1. Do not use your primary personal access token with broad org-level permissions.
2. Generate a fine-grained token scoped specifically to your target repository.
3. Grant only `Contents: Read` (for searching code) and `Issues: Read & Write` (for creating issues and commenting on PRs).
4. Revoke or rotate the token regularly.

## Human-in-the-loop Guardrail

All write operations (such as creating issues and commenting on PRs) must be approved by the user via the orchestrator's confirmation flow. The orchestrator must not execute these tools automatically.
If an LLM requests a write tool, the orchestrator returns a proposed state payload. The execution is blocked until the user submits a confirmation payload containing the signed hash.
