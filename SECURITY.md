# Security Policy

## Supported Versions

SoloCrawl is a small local tool. Security fixes are provided for the latest released version on the
default branch.

## Reporting a Vulnerability

Please report security issues privately to the maintainer instead of opening a public issue. If no
dedicated security contact is listed on GitHub, use the repository owner's public contact channel.

Include:

- affected SoloCrawl version or commit
- operating system and Python version
- steps to reproduce
- expected and actual impact

## Local Fetching Model

SoloCrawl fetches remote URLs from the machine where it runs. This matters for local MCP clients:
prompts and model tool calls can influence which URLs are requested.

By default SoloCrawl blocks localhost, private, link-local, reserved, multicast, unspecified, and
cloud-metadata targets. Hostnames are checked both syntactically and by DNS resolution before fetches
and redirects are followed. Set `SOLOCRAWL_ALLOW_INTERNAL_URLS=true` only for trusted local
development.

Do not put secrets in prompts, command arguments, logs, or `.env` files committed to git.
