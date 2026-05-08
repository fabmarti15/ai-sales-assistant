"""
SalesAssistant - AI-powered message generation and lead enrichment.
Uses OpenAI GPT to craft personalised outreach based on lead profile.
"""
import os
import json
import logging
import openai
from typing import Optional

logger = logging.getLogger(__name__)

OUTREACH_SYSTEM_PROMPT = """You are an expert B2B sales assistant.
Your goal is to craft concise, personalised outreach messages that:
- Reference the prospect's company and role specifically
- Highlight a concrete pain point relevant to their industry
- Propose a clear, low-commitment next step
- Sound human, not automated
Keep messages under 120 words."""

ENRICHMENT_PROMPT = """Given the following lead data, infer and return as JSON:
- likely_pain_points (list of 3)
- best_channel (email | linkedin | phone)
- urgency_score (1-10)
- recommended_tone (formal | casual | technical)
Lead data: {lead_data}"""


class SalesAssistant:
    def __init__(self, config):
        self.config = config
        self.client = openai.OpenAI(api_key=config.openai_api_key)
        self.model = config.openai_model or "gpt-4o"
        logger.info(f"SalesAssistant initialised with model={self.model}")

    def generate_outreach(self, lead: dict, tone: Optional[str] = None) -> str:
        tone = tone or lead.get("recommended_tone", "professional")
        user_prompt = (
            f"Write an outreach message for {lead.get('first_name', 'there')} "
            f"at {lead.get('company', 'their company')} ({lead.get('industry', 'tech')} industry). "
            f"Role: {lead.get('title', 'decision maker')}. "
            f"Pain points: {', '.join(lead.get('pain_points', ['efficiency', 'growth']))}. "
            f"Tone: {tone}."
        )
        logger.debug(f"Generating outreach for lead {lead.get('id')}")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": OUTREACH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            message = response.choices[0].message.content.strip()
            logger.info(f"Outreach generated for {lead.get('email', 'unknown')}")
            return message
        except openai.RateLimitError:
            logger.error("OpenAI rate limit hit — backing off")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def enrich_lead(self, lead: dict) -> dict:
        prompt = ENRICHMENT_PROMPT.format(lead_data=json.dumps(lead, indent=2))
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            enrichment = json.loads(response.choices[0].message.content)
            logger.info(f"Lead {lead.get('id')} enriched successfully")
            return {**lead, **enrichment}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse enrichment JSON: {e}")
            return lead

    def batch_enrich(self, leads: list) -> list:
        enriched = []
        for i, lead in enumerate(leads):
            try:
                enriched.append(self.enrich_lead(lead))
                logger.info(f"Enriched {i+1}/{len(leads)} leads")
            except Exception as e:
                logger.warning(f"Skipping lead {lead.get('id')}: {e}")
                enriched.append(lead)
        return enriched

    def summarise_pipeline(self, leads: list) -> str:
        tiers = {"hot": 0, "warm": 0, "cold": 0}
        for lead in leads:
            tier = lead.get("tier", "cold")
            tiers[tier] = tiers.get(tier, 0) + 1
        return f"Pipeline: {tiers['hot']} hot | {tiers['warm']} warm | {tiers['cold']} cold ({len(leads)} total)"
