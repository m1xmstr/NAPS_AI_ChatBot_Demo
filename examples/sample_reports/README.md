# Sample Reports

Generated crawl bundles and smoke-test reports are intentionally ignored by Git under `demo-output/`.

Use the example extra-vars files to generate fresh reports:

```bash
ansible-playbook playbooks/EDU_AI_DEMO.yml -e @examples/extra_vars/unc.yml
ansible-playbook playbooks/EDU_AI_DEMO.yml -e @examples/extra_vars/renci.yml
ansible-playbook playbooks/EDU_AI_DEMO.yml -e @examples/extra_vars/wfu.yml
ansible-playbook playbooks/EDU_AI_DEMO.yml -e @examples/extra_vars/liberty.yml
```

