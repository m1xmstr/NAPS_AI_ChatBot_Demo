# Initial Smoke Test Summary

The scaffold was tested in `artifact` mode against the requested public websites with `demo_max_pages=8` or `10`.

| Customer | Website | Verified Questions | Notes |
| --- | --- | ---: | --- |
| University of North Carolina at Chapel Hill | https://www.unc.edu/ | 4 / 6 | Registrar, tuition, and financial aid content surfaced; bookstore and job-placement were correctly marked not verified from the shallow crawl. |
| RENCI | https://renci.org/ | 2 / 6 | RENCI is not a university enrollment site, so EDU-specific questions are intentionally sparse. |
| Wake Forest University | https://www.wfu.edu/ | 4 / 6 | Admissions, registrar, and financial aid style content surfaced. |
| Liberty University | https://www.liberty.edu/ | 4 / 6 | Admissions, registrar, and financial aid style content surfaced. |

Generated crawl bundles are not committed. Re-run the playbook before a customer demo to produce current reports under `demo-output/`.

