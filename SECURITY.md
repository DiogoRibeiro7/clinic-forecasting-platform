# Security Policy

This repository is a public, portfolio-grade proof of concept for clinic
forecasting and staffing decision support. It is not a clinically governed
production deployment and does not claim production-grade security controls.

## Supported versions

The current development line is the only supported line for security fixes.

| Version | Supported |
| --- | --- |
| 0.3.x | Yes |
| < 0.3 | No |

Security fixes are applied to the current branch first. Older snapshots are not
maintained as separate supported release lines.

## Reporting a vulnerability

Please do not disclose exploitable security details in a public issue.

Preferred reporting path:

1. Use GitHub's private vulnerability reporting / repository security-advisory
   flow when it is available for this repository.
2. If that private channel is not available, contact the maintainer privately
   using the contact details exposed on the maintainer's GitHub profile.
3. Include enough information to reproduce and assess the issue, but do not post
   credentials, patient data, real healthcare data, or third-party secrets.

A useful report should include:

- affected commit/version;
- affected file, endpoint, workflow or dependency;
- reproduction steps or proof of concept;
- expected and observed behaviour;
- impact assessment;
- any proposed mitigation.

Please allow reasonable time for triage and remediation before public
disclosure.

## What counts as a security issue here

Examples include:

- accidental exposure of API keys or other credentials;
- path traversal or unsafe file resolution around serving artefacts;
- bypass of serving-manifest integrity or fingerprint checks;
- unsafe deserialisation or code execution;
- dependency or container vulnerabilities with a credible impact path;
- code-level security findings identified by static analysis, including CodeQL;
- privilege or trust-boundary bypass in repository automation;
- unexpected disclosure of local files through the API;
- insecure handling of optional external-provider credentials.

Ordinary forecast-quality bugs, model-performance questions, documentation
errors and scientific-methodology disagreements belong in normal public issues.

## Known deployment-integration gaps are not hidden vulnerabilities

The repository deliberately does not implement several organisation-specific
production controls, including:

- SSO / production authentication and authorisation;
- managed secret storage and rotation;
- TLS termination, WAF, production rate limiting and network policy;
- central audit-log retention;
- production SLOs and on-call incident response;
- managed deployment, rollback and infrastructure controls.

These are documented in
[`docs/production_readiness.md`](docs/production_readiness.md) as
**requires deployment integration**. Their absence in this PoC should not be
misrepresented as evidence that they are implemented.

A concrete vulnerability in the code that exists in this repository should
still be reported privately.

## Secrets

Do not commit secrets.

The repository's example environment file contains placeholders only.
Optional external providers such as TimeGPT are key-gated; any real provider
credential must be supplied outside version control.

If a secret is accidentally committed:

1. revoke or rotate it immediately;
2. treat repository history as exposed;
3. remove the secret from active configuration;
4. then clean repository history if appropriate.

Deleting a secret from the latest commit is not sufficient remediation.

## Data boundary

Do not use this repository to report or attach:

- patient-level data;
- protected health information;
- confidential operational healthcare data;
- real credentials or access tokens.

The committed datasets are synthetic or public aggregate sources used within the
documented evidence boundary.

## Dependency security

The repository uses:

- a committed Poetry lock file;
- Dependabot for Python, GitHub Actions and Docker;
- the shared `DiogoRibeiro7/safe-dependabot@v1` policy workflow.

Dependency-update automation reduces routine maintenance risk but is not a
substitute for production vulnerability-management ownership or an
organisation-level remediation SLA.

## Scope boundary

A successful security review of this repository would show that the PoC code,
workflows and local serving artefacts are reasonably hardened for their stated
scope.

It would not establish:

- lawful processing of real healthcare data;
- deployment security of a future production environment;
- clinical safety;
- operational availability;
- staffing-policy effectiveness.

Those boundaries remain governed by
[`docs/production_readiness.md`](docs/production_readiness.md) and
[`reports/model_card.md`](reports/model_card.md).

## Automated code scanning

The repository runs GitHub CodeQL static analysis for Python on pull requests,
pushes to `main`, a weekly schedule and manual dispatch. CodeQL complements
dependency scanning; a clean scan is not proof of production or clinical
security readiness.

## Software bill of materials

The repository can generate a reproducible CycloneDX 1.6 SBOM from
`pyproject.toml` and `poetry.lock`. The workflow validates the generated BOM,
records its SHA-256 digest, and uploads both as CI artifacts when dependency
metadata changes. This complements Dependabot and CodeQL but does not replace
vulnerability management or signed release provenance.

## Container vulnerability scanning

The repository builds and scans its Docker image with Trivy 0.76.0. CI reports
HIGH and CRITICAL findings and fails on fixable CRITICAL vulnerabilities. This
complements CodeQL, Dependabot and the CycloneDX SBOM, but does not establish
production or clinical security certification.


## Third-party license inventory

The repository can generate JSON and Markdown inventories of licenses associated
with the installed main Python dependency environment. The report is intended for
transparency and review only; it is not an automated legal-compatibility decision.
