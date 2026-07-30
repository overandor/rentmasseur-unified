FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ chromium chromium-driver fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy all Python modules and data directories
COPY hf_space_app.py .
COPY dashboard.html .
COPY rm_traffic/ ./rm_traffic/
COPY rm_revenue_engine/ ./rm_revenue_engine/
COPY content/ ./content/
COPY bios/ ./bios/
COPY data/ ./data/
COPY providers.json .
COPY rentmasseur_availability.py .
COPY rentmasseur_core.py .
COPY rentmasseur_coordinator.py .
COPY rentmasseur_optimizer.py .
COPY auto_bio_updater.py .
COPY bio_ab_tester.py .
COPY content_generator.py .
COPY photo_rotator.py .
COPY price_rotator.py .
COPY blog_rotator.py .
COPY interview_rotator.py .
COPY competitor_scraper.py .
COPY seo_keywords.py .
COPY social_media_generator.py .
COPY push_bio.py .
COPY run_bio_pipeline.py .
COPY orchestrator.py .
COPY production_pipeline.py .
COPY metrics_collector.py .
COPY ga_rl_optimizer.py .
COPY rl_feedback.py .
COPY daily_evidence.py .
COPY daily_promotion.py .
COPY weekly_report.py .
COPY email_templates.py .
COPY dashboard.py .
COPY checker.py .
COPY browser_visit_back.py .

RUN mkdir -p /tmp/systemlake_v4b

ENV PORT=7860
ENV SYSTEMLAKE_DATA_DIR=/tmp/systemlake_v4b
ENV CHROME_BIN=/usr/bin/chromium
EXPOSE 7860

CMD ["python", "hf_space_app.py"]
