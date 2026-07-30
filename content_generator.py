#!/usr/bin/env python3
"""Content generator — orchestrates daily bio, blog, and interview generation.

Calls rentmasseur_core for bio generation, blog_rotator for blog posts,
and interview_rotator for interview Q&A. Used by orchestrator and hf_app.

Usage:
    python3 content_generator.py              # generate all content
    python3 content_generator.py --bios-only  # generate bios only
    python3 content_generator.py --blogs-only # generate blog posts only
    python3 content_generator.py --interviews-only
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
CONTENT_DIR = SCRIPT_DIR / "content"
BIOS_DIR = CONTENT_DIR / "bios"
BLOG_DIR = CONTENT_DIR / "blog_posts"
INTERVIEW_DIR = CONTENT_DIR / "interview_questions"

for d in (BIOS_DIR, BLOG_DIR, INTERVIEW_DIR):
    d.mkdir(parents=True, exist_ok=True)

BIO_STRATEGIES = [
    ("sensory_luxury", "Write a bio that evokes sensory luxury — warmth, pressure, aroma, ambiance. Appeal to clients seeking escape and pampering."),
    ("clinical_recovery", "Write a bio focused on clinical recovery — sports massage, injury rehab, deep tissue expertise. Appeal to athletes and professionals with tension pain."),
    ("wolf_charisma", "Write a bio with magnetic charisma and quiet confidence. Short punchy sentences. A wolf who knows his craft. Appeal to clients who want a premium, no-nonsense experience."),
    ("midnight_stories", "Write a bio with late-night energy — mysterious, intimate, available after hours. Appeal to clients with unconventional schedules."),
    ("manhattan_elite", "Write a bio positioned as Manhattan's elite massage therapist. Mention neighborhood expertise, premium clientele, and discreet service."),
]


def generate_bios() -> int:
    from rentmasseur_core import groq_generate_bio

    current_bio = None
    count = 0
    for strategy_name, strategy_prompt in BIO_STRATEGIES:
        bio = groq_generate_bio(strategy_name, strategy_prompt, current_bio)
        if bio:
            count += 1
            logger.info("Generated bio: %s (%d chars)", strategy_name, len(bio))
        else:
            logger.warning("Failed to generate bio for strategy: %s", strategy_name)
    logger.info("Generated %d/%d bios", count, len(BIO_STRATEGIES))
    return count


def generate_blogs() -> int:
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "blog_rotator.py"],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Blog generation complete")
            return 1
        else:
            logger.warning("Blog rotator failed: %s", result.stderr[:200])
            return 0
    except Exception as e:
        logger.error("Blog generation error: %s", e)
        return 0


def generate_interviews() -> int:
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "interview_rotator.py"],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Interview generation complete")
            return 1
        else:
            logger.warning("Interview rotator failed: %s", result.stderr[:200])
            return 0
    except Exception as e:
        logger.error("Interview generation error: %s", e)
        return 0


def main():
    parser = argparse.ArgumentParser(description="RentMasseur content generator")
    parser.add_argument("--bios-only", action="store_true", help="Generate bios only")
    parser.add_argument("--blogs-only", action="store_true", help="Generate blog posts only")
    parser.add_argument("--interviews-only", action="store_true", help="Generate interview Q&A only")
    args = parser.parse_args()

    all_mode = not (args.bios_only or args.blogs_only or args.interviews_only)

    total = 0
    if all_mode or args.bios_only:
        total += generate_bios()
    if all_mode or args.blogs_only:
        total += generate_blogs()
    if all_mode or args.interviews_only:
        total += generate_interviews()

    logger.info("Content generation complete: %d items", total)


if __name__ == "__main__":
    main()
