# Demo Runbook

## Two Days Before The Meeting

1. Run `EDU_AI_DEMO` with `demo_runtime=artifact`.
2. Review `demo-output/<customer-slug>/report.md`.
3. Check the generated source links for the six smoke-test questions.
4. If the logo is wrong, provide `demo_logo_url` or `demo_logo_file`.
5. If answers are thin, provide `demo_seed_urls` with admissions, registrar, tuition, financial aid, bookstore, and career outcome pages.

## One Day Before The Meeting

1. Run the selected runtime: `openshift`, `openshift_ai`, `podman`, or `rhel_ai`.
2. Open the generated route or Podman URL.
3. Ask the smoke-test questions manually.
4. Keep a short list of questions that show citations clearly.
5. Keep one question that intentionally cannot be answered to show the assistant does not hallucinate.

## After The Meeting

1. Run `EDU_AI_DEMO_CLEANUP` for temporary OpenShift namespaces or Podman containers.
2. Archive the smoke report privately if useful.
3. Re-run for the next school.

## Customer-Safe Talk Track

- "AAP takes a small set of customer inputs and builds the demo repeatably."
- "The assistant starts with verified public content and shows citations."
- "OpenShift gives us a consistent app platform for the demo."
- "OpenShift AI or RHEL AI can provide the model endpoint when we want generated answers over the retrieved official content."
- "Podman on RHEL gives us a portable edge or server-side runtime for the same app."

