# Security Policy

Chess Analyzer Pro is a local-first desktop application designed with privacy and security as core principles. We take security vulnerabilities seriously and appreciate the efforts of security researchers and community contributors who responsibly report issues.

---

## Supported Versions

Only the latest major/minor release receives active security patches.

| Version | Supported |
| :--- | :--- |
| **2.3.x** | :white_check_mark: Yes |
| < 2.3.0 | :x: No |

We recommend always running the latest version available from the [Official Releases](https://github.com/imutkarsht/Chess_analyzer/releases) page or official website at [chessanalyzer.xyz](https://chessanalyzer.xyz/).

---

### Reporting Method
Please submit security vulnerabilities privately using GitHub Security Advisories:
1. Go to the repository's **Security** tab: [Security Advisories](https://github.com/imutkarsht/Chess_analyzer/security/advisories).
2. Click **"Report a vulnerability"** to submit a private report directly to the maintainers.

If you have questions regarding security or need direct coordination, you can reach the maintainer directly via GitHub profile: [@imutkarsht](https://github.com/imutkarsht).

### What to Include in Your Report
To help us triage and resolve the issue quickly, please provide:
- A clear description of the vulnerability and its potential impact.
- Step-by-step instructions or a minimal reproducible proof-of-concept (PoC) (e.g., malformed PGN, SVG theme, or API payload).
- The operating system (macOS, Windows, Linux) and architecture where the issue was reproduced.
- Any suggested remediations or patches if you have one.

---

## Response Timeline & Process

- **Acknowledgment:** Within **48 hours** of receiving your report.
- **Triage & Assessment:** We will verify the finding and determine its severity within **5 business days**.
- **Fix & Patch:** Once confirmed, we will work on a fix in a private branch, prepare release assets, and publish a security advisory and patched version.
- **Public Disclosure:** Coordinated disclosure will occur after a patched release is published and available to users.
- **Credit:** We will gladly credit you in our [CHANGELOG.md](CHANGELOG.md) and release notes (unless you prefer to remain anonymous).

---

## Scope & Architectural Principles

Chess Analyzer Pro is designed as a **local-first** application:
- User PGNs, game history, and analysis remain stored exclusively on the user's machine in local SQLite databases.
- Network activity is strictly optional (API game fetchers, auto-updater, and user-configured LLM endpoints).
- Credentials (API tokens) are stored locally in user configuration and are automatically scrubbed from application logs.

