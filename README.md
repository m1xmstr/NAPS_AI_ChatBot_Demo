# EDU AI Demo

`EDU_AI_DEMO` is an Ansible Automation Platform demo kit for building a temporary, customer-branded AI assistant from public university web content.

The intended flow:

1. Run the AAP job one or two days before a customer meeting.
2. Provide the customer name, website, optional logo URL or private logo file, and target runtime.
3. Let the playbook crawl a small set of public pages, build a branded mini chatbot, deploy it to the selected Red Hat runtime, and run a smoke test with education-focused questions.
4. Demo the result, then clean it up or re-run for the next school.

The default assistant is deliberately evidence-based. It answers from crawled public pages and cites source links. If it cannot verify an answer, it says that instead of inventing a response. Optional RHEL AI or OpenShift AI endpoints can be wired in later for model-backed generation while keeping the same retrieval context.

## Red Hat Story

This kit is designed to show a simple end-to-end Red Hat platform story:

- **Ansible Automation Platform** drives the repeatable customer-specific build.
- **RHEL** is the base operating system target for Podman-hosted demos.
- **Podman** can run the chatbot directly on a RHEL host.
- **OpenShift** can host the generated app as a temporary Route-backed deployment.
- **OpenShift AI** can be shown as the model serving and governance layer when an inference endpoint is supplied.
- **RHEL AI** can be shown as a portable model endpoint for the same chatbot runtime.

## Quick Start

Install required collections:

```bash
ansible-galaxy collection install -r requirements.yml
```

Build a local demo artifact and run an offline smoke test:

```bash
ansible-playbook playbooks/EDU_AI_DEMO.yml \
  -e customer_name="University of North Carolina" \
  -e customer_website="https://www.unc.edu/" \
  -e demo_runtime="artifact"
```

Deploy to OpenShift if your kubeconfig is available:

```bash
ansible-playbook playbooks/EDU_AI_DEMO.yml \
  -e customer_name="Wake Forest University" \
  -e customer_website="https://www.wfu.edu/" \
  -e demo_runtime="openshift"
```

The OpenShift path uses the `oc` CLI from the execution environment by default. In AAP, attach an OpenShift credential that injects `OCP_API_URL`, `OCP_API_TOKEN`, and optionally `OCP_SKIP_TLS_VERIFY`; the playbook logs in with those values before applying or removing OpenShift resources.

Clean up an OpenShift demo namespace:

```bash
ansible-playbook playbooks/EDU_AI_DEMO_CLEANUP.yml \
  -e customer_name="Wake Forest University" \
  -e demo_runtime="openshift"
```

## AAP Survey Variables

The main playbook is named `EDU_AI_DEMO.yml`. Suggested survey questions are in [examples/surveys/EDU_AI_DEMO_survey.json](examples/surveys/EDU_AI_DEMO_survey.json).

Required variables:

- `customer_name`
- `customer_website`
- `demo_runtime`: `artifact`, `podman`, `openshift`, `openshift_ai`, `rhel_ai`, or `all`

Optional variables:

- `demo_logo_url`: direct image URL to use instead of auto-discovery
- `demo_logo_file`: private repo path to a logo file, useful when AAP survey upload is not practical
- `demo_max_pages`: crawl limit, default `24`
- `demo_question_set`: custom smoke-test questions
- `demo_llm_endpoint_url`: OpenAI-compatible endpoint for RHEL AI/OpenShift AI demos
- `demo_llm_api_key_env`: environment variable name that contains the endpoint API key

## Safety

This repo is public-facing. Do not commit customer secrets, private API endpoints, AAP credentials, kubeconfigs, or private IPs here. Put environment-specific values in the private repo or in AAP credentials.
