# Security Policy

Replenix takes the security of our platform and our users' data seriously. We appreciate the work of security researchers who responsibly disclose vulnerabilities.

---

## Supported Versions

Replenix is a continuously deployed web application — there are no versioned releases. Security fixes are applied directly to the production environment. Only the **live production deployment** at `replenix.ai` is actively maintained and receives security updates.

| Environment | Status                |
|-------------|----------------------|
| Production  | ✅ Actively supported |
| Preprod     | ✅ Receives fixes     |
| Dev         | ⚠️ Best effort        |

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities directly to:

**📧 [sujaynsv@gmail.com](mailto:sujaynsv@gmail.com)**

Include the following in your report:
- A clear description of the vulnerability and its potential impact
- Steps to reproduce the issue (proof-of-concept, screenshots, or request/response logs)
- The environment where you observed it (production, preprod, etc.)
- Any suggestions for remediation, if you have them

### What to expect after reporting

| Milestone | Timeframe |
|---|---|
| Initial acknowledgement | Within **48 hours** |
| Severity assessment & triage | Within **7 days** |
| Fix deployed to production | Depends on severity (see below) |
| Notification to reporter | After fix is deployed |

### Severity & response timelines

| Severity | Description | Target fix time |
|---|---|---|
| **Critical** | Active data breach, authentication bypass, full account takeover | 24–48 hours |
| **High** | Unauthorized access to other users' data, privilege escalation | 7 days |
| **Medium** | XSS, CSRF, limited information disclosure | 14 days |
| **Low** | Minor issues, best-practice deviations | 30 days |

---

## Scope

The following are **in scope** for vulnerability reports:

- **Authentication & authorization** — login flows, JWT token handling, session management, access control
- **Data exposure** — unauthorized access to another user's inventory data, forecasting models, or financial information
- **API security** — SQL/NoSQL injection, privilege escalation, rate-limiting bypass, IDOR vulnerabilities
- **Frontend security** — Cross-Site Scripting (XSS), Cross-Site Request Forgery (CSRF)
- **Infrastructure** — Kubernetes misconfigurations, exposed internal services, container escape risks
- **Supply chain** — Third-party dependency vulnerabilities that directly affect the Replenix platform

The following are **out of scope**:

- Vulnerabilities in services we do not control (GitHub, cloud provider infrastructure)
- Social engineering attacks against Replenix team members
- Denial of service (DoS/DDoS) attacks
- Issues already publicly disclosed with no patch available upstream
- Automated scanner results without a working proof-of-concept
- Issues requiring physical access to a device

---

## Disclosure Policy

We follow a **coordinated disclosure** model:

1. You report the vulnerability privately to us.
2. We acknowledge and begin investigation within 48 hours.
3. We work with you to understand and reproduce the issue.
4. We develop and deploy a fix.
5. We notify you when the fix is live.
6. You may publicly disclose the vulnerability **90 days** after your initial report, or sooner with our agreement.

We will not take legal action against researchers who follow this policy in good faith.

---

## Recognition

We genuinely appreciate responsible disclosure. Researchers who report valid, in-scope vulnerabilities will be:

- Acknowledged by name (or anonymously, if preferred) in our security acknowledgements
- Kept informed throughout the remediation process
- Notified when the fix is shipped

We are a small team and do not currently operate a paid bug bounty program, but we are grateful for the community's contribution to keeping Replenix secure.

---

## Contact

Security reports: **[sujaynsv@gmail.com](mailto:sujaynsv@gmail.com)**  
General enquiries: **[hello@replenix.ai](mailto:hello@replenix.ai)**
