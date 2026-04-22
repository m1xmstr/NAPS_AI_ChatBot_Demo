# AAP Survey

AAP surveys do not provide a clean binary upload workflow for logos. The recommended approach is:

1. Use `demo_logo_url` when the logo is publicly available.
2. Use `demo_logo_file` when the logo must be kept private. Store the file in the private repo under `private_assets/logos/`.
3. Leave both blank to let the crawler discover a logo candidate from the school website.

Suggested survey fields are provided in JSON form at:

```text
examples/surveys/EDU_AI_DEMO_survey.json
```

Recommended AAP Job Template:

- Name: `EDU_AI_DEMO`
- Project: private repo project
- Playbook: `playbooks/EDU_AI_DEMO.yml`
- Inventory: private home lab or demo inventory
- Credentials:
  - OpenShift API credential for OpenShift runtimes. The included role expects injected environment variables named `OCP_API_URL`, `OCP_API_TOKEN`, and optionally `OCP_SKIP_TLS_VERIFY`.
  - Machine credential for Podman/RHEL runtimes
  - Optional SCM credential if the private repo is not public to the AAP controller
  - Optional model endpoint credential for RHEL AI/OpenShift AI

## Default Demo Questions

The smoke test asks:

- When is open enrollment?
- When can I register for classes?
- How much is tuition going up?
- How do I apply for financial assistance?
- Where are the closest bookstores to campus?
- How many students find job placement after graduation?

The app should not be expected to answer every question from a shallow crawl. A high-quality demo answer can also be: "I could not verify this in the crawled pages, but here are the most relevant official links."
