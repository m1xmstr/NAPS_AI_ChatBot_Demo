# Safety And Sanitization

Public repo rules:

- No credentials.
- No private hostnames, private IPs, kubeconfigs, tokens, or passwords.
- No customer-private documents.
- No scraped content bundles committed by default.

Private repo rules:

- Private endpoint names and private inventory can live there.
- Prefer AAP credentials or Kubernetes secrets for actual secrets.
- If a credential must be represented in Git, use an encrypted Ansible Vault file and document the vault-id flow.

Answering rules:

- Cite official source URLs.
- Do not fabricate enrollment, tuition, financial aid, or job placement facts.
- Treat "not found in the crawled pages" as a valid demo outcome.
- Re-run the crawl before a customer-facing demo because EDU web content changes frequently.

