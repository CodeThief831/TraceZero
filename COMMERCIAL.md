# TraceZero Commercial Licensing, Pro Packs & Sponsorship

TraceZero's core engine (`src/tracezero`) is proudly **MIT Open-Source** so developers, students, researchers, and auditors can run private **Plagiarism Checking, AI Detection, and Humanization** locally at zero cost.

For organizations, SaaS builders, universities, and high-volume teams who want turnkey infrastructure, custom domain models, SLAs, or white-label APIs, TraceZero follows an **Open-Core + Sponsorship** monetization model.

---

## Plans & Monetization Tiers

| Tier | Price | Best For | Included Value |
| :--- | :---: | :--- | :--- |
| **Community (MIT)** | **\$0** | Individuals, students, OSS builders | Full offline CLI, FastAPI Workbench, Docker setup, N-gram + TF-IDF plagiarism checker, RoBERTa + DistilGPT2 support |
| **Supporter** | **\$5 / mo** | Grateful daily users | Name/logo credit in `SPONSORS.md`, priority voting on detector & language roadmap |
| **Pro Sponsor** | **\$19 / mo** | Researchers, writers, agencies | Pre-tuned multilingual & DeBERTa-v3 YAML model packs, batch folder CSV/JSON audit templates, priority GitHub support |
| **Team / University On-Prem** | **\$199 / mo** | Labs, edtech, compliance teams | Air-gapped container setup guidance, high-concurrency FastAPI worker templates, institutional PDF corpus indexing architecture |
| **Enterprise White-Label / Consulting** | **Custom** | SaaS founders & platforms | Turnkey API monetization setup (Stripe/usage metering wrapper), custom domain fine-tuning, dedicated installation & SLA |

---

## Ways to Sponsor or Purchase

1. **Monthly or One-Time Sponsorship:**
   [https://github.com/sponsors/CodeThief831](https://github.com/sponsors/CodeThief831)
2. **Enterprise License / SaaS Deployment Inquiry:**
   Open a structured [Enterprise / Pro License Inquiry](https://github.com/CodeThief831/TraceZero/issues/new?template=enterprise_inquiry.md).

---

## Hosted SaaS Blueprint (Build & Monetize Your Own API)

Want to deploy TraceZero as a paid cloud API (for example on AWS, GCP, Azure, or Fly.io)?
- Put NGINX / Kong / Stripe API key gateway in front of `docker compose up -d` (`POST /api/scan`, `POST /api/scan-file`, `POST /api/plagiarism`, `POST /api/plagiarism-files`, `POST /api/humanize`).
- Keep transformer weights mounted on fast SSD NVMe (`./models:/app/models`) with worker replicas enabled (`uvicorn tracezero.web.app:app --workers 4`).
- Meter requests per 1,000 words or per PDF audit—Zero third-party API pass-through costs mean ~85%+ gross software margin on your own hardware.
