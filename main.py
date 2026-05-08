#!/usr/bin/env python3
"""AI Sales Assistant - Main Entry Point
Orchestrates lead scoring, CRM sync, and AI-powered outreach.
"""
import argparse
import logging
from assistant import SalesAssistant
from lead_scorer import LeadScorer
from crm_integration import CRMClient
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="AI Sales Assistant CLI")
    parser.add_argument("--mode", choices=["score", "outreach", "sync"], required=True)
    parser.add_argument("--lead-id", type=str, help="Target lead ID")
    parser.add_argument("--batch", action="store_true", help="Run in batch mode")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return parser.parse_args()

def run_lead_scoring(config, dry_run=False):
    logger.info("Starting lead scoring pipeline...")
    crm = CRMClient(config)
    scorer = LeadScorer(config)
    leads = crm.fetch_unscored_leads()
    logger.info(f"Found {len(leads)} unscored leads")
    results = []
    for lead in leads:
        score = scorer.score(lead)
        tier = scorer.tier(score)
        results.append({"lead_id": lead["id"], "score": score, "tier": tier})
        if not dry_run:
            crm.update_lead_score(lead["id"], score)
            logger.info(f"  Lead {lead['id']} -> {score:.2f} ({tier})")
    return results

def run_outreach(config, lead_id=None, batch=False, dry_run=False):
    logger.info("Initialising outreach engine...")
    assistant = SalesAssistant(config)
    crm = CRMClient(config)
    if lead_id:
        lead = crm.get_lead(lead_id)
        message = assistant.generate_outreach(lead)
        if not dry_run:
            crm.log_activity(lead_id, "outreach_sent", message)
            logger.info(f"Outreach sent to {lead['email']}")
        return [{"lead_id": lead_id, "message": message}]
    if batch:
        hot_leads = crm.fetch_leads_by_tier("hot")
        logger.info(f"Batch outreach for {len(hot_leads)} hot leads")
        results = []
        for lead in hot_leads:
            msg = assistant.generate_outreach(lead)
            if not dry_run:
                crm.log_activity(lead["id"], "outreach_sent", msg)
            results.append({"lead_id": lead["id"], "message": msg})
        return results
    logger.warning("No --lead-id or --batch specified")
    return []

def run_sync(config):
    logger.info("Syncing CRM data...")
    crm = CRMClient(config)
    stats = crm.full_sync()
    logger.info(f"Sync: {stats['created']} created, {stats['updated']} updated, {stats['errors']} errors")
    return stats

def main():
    args = parse_args()
    config = Config.load()
    logger.info(f"Mode: {args.mode} | dry_run={args.dry_run}")
    if args.mode == "score":
        results = run_lead_scoring(config, dry_run=args.dry_run)
        print(f"Scored {len(results)} leads")
    elif args.mode == "outreach":
        results = run_outreach(config, lead_id=args.lead_id, batch=args.batch, dry_run=args.dry_run)
        print(f"Processed {len(results)} outreach messages")
    elif args.mode == "sync":
        stats = run_sync(config)
        print(f"Sync complete: {stats}")

if __name__ == "__main__":
    main()
