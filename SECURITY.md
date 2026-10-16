# Security and private data

Never post API keys, passwords, Ring tokens, private logs, or personal network
details in a public issue. If you suspect that a credential has been exposed,
revoke or rotate it with the relevant provider and follow that provider's recovery
guidance. Never send credentials to the maintainer.

This project has no support service and promises no individual response, security
maintenance or updates. See [project status and support](hardware/SAFETY.md#project-status-and-support).

Keep credentials in ignored local files or protected Pi configuration. SSH
commands preserve normal host-key verification. The application has no local
brain/device network listener. OpenAI and optional integrations use their own
network connections. The application runs as root for the existing GPIO/LED
drivers; its AI and hardware modules share access to runtime credentials.

Before publication, rotate any credentials confirmed exposed, audit the tree,
intended Git refs and packaged downloads, and decide how to publish sanitized contents. Removing
a file from the latest commit does not remove it from Git history.
A fresh public history also leaves private information inside exported files
unchanged. Review the exact publication contents, including packaged downloads and file
metadata, using the [release checklist](docs/release/checklist.md).
