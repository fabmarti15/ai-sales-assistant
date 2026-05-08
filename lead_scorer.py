"""
LeadScorer - Multi-factor lead scoring engine.
Combines firmographic, behavioural, and intent signals
to produce a 0-100 score and Hot/Warm/Cold tier.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)

TIER_THRESHOLDS = {"hot": 70, "warm": 40, "cold": 0}

INDUSTRY_WEIGHTS = {
    "technology": 1.3, "fintech": 1.25, "healthtech": 1.2,
    "ecommerce": 1.1, "retail": 0.9, "education": 0.85,
}

COMPANY_SIZE_SCORES = {
    "1-10": 20, "11-50": 35, "51-200": 55,
    "201-500": 70, "501-1000": 80, "1000+": 90,
}

TITLE_SCORES = {
    "ceo": 95, "cto": 90, "coo": 88, "vp": 80,
    "director": 70, "manager": 55, "analyst": 35, "intern": 10,
}


@dataclass
class ScoringWeights:
    company_size: float = 0.25
    title_seniority: float = 0.30
    industry_fit: float = 0.20
    engagement: float = 0.15
    intent_signals: float = 0.10


class LeadScorer:
    def __init__(self, config, weights: ScoringWeights = None):
        self.config = config
        self.weights = weights or ScoringWeights()
        logger.info("LeadScorer initialised")

    def _score_company_size(self, lead: dict) -> float:
        size = lead.get("company_size", "1-10")
        return COMPANY_SIZE_SCORES.get(size, 20)

    def _score_title(self, lead: dict) -> float:
        title = lead.get("title", "").lower()
        for keyword, score in TITLE_SCORES.items():
            if keyword in title:
                return score
        return 30

    def _score_industry(self, lead: dict) -> float:
        industry = lead.get("industry", "").lower()
        base = 50
        multiplier = INDUSTRY_WEIGHTS.get(industry, 1.0)
        return min(base * multiplier, 100)

    def _score_engagement(self, lead: dict) -> float:
        events = lead.get("engagement_events", [])
        score = 0
        for event in events:
            if event.get("type") == "demo_request":
                score += 40
            elif event.get("type") == "pricing_page":
                score += 25
            elif event.get("type") == "webinar":
                score += 15
            elif event.get("type") == "blog_read":
                score += 5
        return min(score, 100)

    def _score_intent(self, lead: dict) -> float:
        signals = lead.get("intent_signals", [])
        signal_scores = {"high": 90, "medium": 55, "low": 20}
        if not signals:
            return 10
        top = max(signals, key=lambda s: signal_scores.get(s.get("strength", "low"), 0))
        return signal_scores.get(top.get("strength", "low"), 10)

    def score(self, lead: dict) -> float:
        w = self.weights
        components = {
            "company_size": self._score_company_size(lead) * w.company_size,
            "title":        self._score_title(lead) * w.title_seniority,
            "industry":     self._score_industry(lead) * w.industry_fit,
            "engagement":   self._score_engagement(lead) * w.engagement,
            "intent":       self._score_intent(lead) * w.intent_signals,
        }
        total = sum(components.values())
        logger.debug(f"Lead {lead.get('id')} components: {components} -> {total:.2f}")
        return round(min(total, 100), 2)

    def tier(self, score: float) -> str:
        if score >= TIER_THRESHOLDS["hot"]:
            return "hot"
        if score >= TIER_THRESHOLDS["warm"]:
            return "warm"
        return "cold"

    def explain(self, lead: dict) -> Dict[str, float]:
        return {
            "company_size_score": self._score_company_size(lead),
            "title_score":        self._score_title(lead),
            "industry_score":     self._score_industry(lead),
            "engagement_score":   self._score_engagement(lead),
            "intent_score":       self._score_intent(lead),
            "final_score":        self.score(lead),
            "tier":               self.tier(self.score(lead)),
        }
