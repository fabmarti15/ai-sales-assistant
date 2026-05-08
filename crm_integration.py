"""
CRMClient - HubSpot/Salesforce abstraction layer.
Handles lead fetching, scoring updates, activity logging, and full sync.
"""
import logging
import time
import requests
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

HUBSPOT_BASE_URL = "https://api.hubapi.com"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2


class CRMError(Exception):
    pass


class CRMClient:
    def __init__(self, config):
        self.config = config
        self.api_key = config.crm_api_key
        self.provider = config.crm_provider or "hubspot"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        logger.info(f"CRMClient initialised — provider={self.provider}")

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{HUBSPOT_BASE_URL}{endpoint}"
        for attempt in range(RETRY_ATTEMPTS):
            try:
                resp = self.session.request(method, url, timeout=15, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError as e:
                if resp.status_code == 429:
                    wait = RETRY_BACKOFF ** attempt
                    logger.warning(f"Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise CRMError(f"HTTP {resp.status_code}: {e}") from e
            except requests.RequestException as e:
                raise CRMError(f"Request failed: {e}") from e
        raise CRMError("Max retries exceeded")

    def fetch_unscored_leads(self) -> List[Dict]:
        logger.info("Fetching unscored leads...")
        data = self._request("GET", "/crm/v3/objects/contacts", params={
            "limit": 100,
            "properties": "email,firstname,lastname,company,jobtitle,industry,hs_lead_status",
            "filterGroups": [{"filters": [{"propertyName": "ai_score", "operator": "NOT_HAS_PROPERTY"}]}],
        })
        leads = self._normalise_contacts(data.get("results", []))
        logger.info(f"Fetched {len(leads)} unscored leads")
        return leads

    def fetch_leads_by_tier(self, tier: str) -> List[Dict]:
        data = self._request("GET", "/crm/v3/objects/contacts", params={
            "limit": 50,
            "properties": "email,firstname,lastname,company,jobtitle,ai_score,ai_tier",
            "filterGroups": [{"filters": [{"propertyName": "ai_tier", "operator": "EQ", "value": tier}]}],
        })
        return self._normalise_contacts(data.get("results", []))

    def get_lead(self, lead_id: str) -> Dict:
        data = self._request("GET", f"/crm/v3/objects/contacts/{lead_id}", params={
            "properties": "email,firstname,lastname,company,jobtitle,industry,phone,ai_score,ai_tier",
        })
        return self._normalise_contact(data)

    def update_lead_score(self, lead_id: str, score: float) -> None:
        from lead_scorer import LeadScorer, ScoringWeights
        tier = LeadScorer(self.config).tier(score)
        self._request("PATCH", f"/crm/v3/objects/contacts/{lead_id}", json={
            "properties": {"ai_score": str(score), "ai_tier": tier, "ai_scored_at": str(int(time.time()))},
        })
        logger.debug(f"Updated lead {lead_id}: score={score}, tier={tier}")

    def log_activity(self, lead_id: str, activity_type: str, note: str) -> None:
        self._request("POST", "/crm/v3/objects/notes", json={
            "properties": {
                "hs_note_body": f"[AI Assistant] {activity_type}: {note}",
                "hs_timestamp": str(int(time.time() * 1000)),
            },
            "associations": [{"to": {"id": lead_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}],
        })
        logger.info(f"Activity logged for lead {lead_id}: {activity_type}")

    def full_sync(self) -> Dict[str, int]:
        stats = {"created": 0, "updated": 0, "errors": 0}
        after = None
        while True:
            params = {"limit": 100, "properties": "email,firstname,lastname,company,jobtitle"}
            if after:
                params["after"] = after
            data = self._request("GET", "/crm/v3/objects/contacts", params=params)
            for contact in data.get("results", []):
                try:
                    existing = self._check_existing(contact["id"])
                    if existing:
                        stats["updated"] += 1
                    else:
                        stats["created"] += 1
                except Exception as e:
                    logger.error(f"Sync error for {contact['id']}: {e}")
                    stats["errors"] += 1
            paging = data.get("paging", {})
            after = paging.get("next", {}).get("after")
            if not after:
                break
        logger.info(f"Full sync complete: {stats}")
        return stats

    def _normalise_contact(self, raw: Dict) -> Dict:
        props = raw.get("properties", {})
        return {
            "id": raw.get("id"),
            "email": props.get("email"),
            "first_name": props.get("firstname"),
            "last_name": props.get("lastname"),
            "company": props.get("company"),
            "title": props.get("jobtitle"),
            "industry": props.get("industry"),
            "phone": props.get("phone"),
            "ai_score": props.get("ai_score"),
            "tier": props.get("ai_tier", "cold"),
        }

    def _normalise_contacts(self, raw_list: List[Dict]) -> List[Dict]:
        return [self._normalise_contact(r) for r in raw_list]

    def _check_existing(self, contact_id: str) -> bool:
        try:
            self.get_lead(contact_id)
            return True
        except CRMError:
            return False
