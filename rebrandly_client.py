#!/usr/bin/env python3
"""
Rebrandly API Client — creates, updates, and tracks branded short links.

Used by the bio pipeline to create per-variant booking links and pull click analytics.

Requires:
  REBRANDLY_API_KEY  — API key from Rebrandly dashboard
  REBRANDLY_WORKSPACE — Workspace ID (optional, defaults to Main Workspace)
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.rebrandly.com/v1"
DEFAULT_DOMAIN_ID = "8f104cc5b6ee4a4ba7897b06ac2ddcfb"  # rebrand.ly
DEFAULT_WORKSPACE = "712ed957af0d472aa2fad2038bf81138"  # Main Workspace
EXISTING_LINK_ID = "1b69ae57bbf54d15b3fedd7a2ca8ec23"  # rebrand.ly/carpathianwolf


class RebrandlyClient:
    """Thin wrapper around the Rebrandly v1 API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace: Optional[str] = None,
        domain_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("REBRANDLY_API_KEY", "")
        self.workspace = workspace or os.environ.get("REBRANDLY_WORKSPACE", DEFAULT_WORKSPACE)
        self.domain_id = domain_id or DEFAULT_DOMAIN_ID
        if not self.api_key:
            raise ValueError("REBRANDLY_API_KEY not set")
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": self.api_key,
            "Workspace": self.workspace,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{API_BASE}/{path}"
        resp = self.session.request(method, url, timeout=15, **kwargs)
        if resp.status_code >= 400:
            logger.error("Rebrandly API error %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        return resp

    # ── Links ──────────────────────────────────────────────────

    def create_link(
        self,
        destination: str,
        slashtag: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        domain_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new branded short link."""
        payload: Dict[str, Any] = {
            "destination": destination,
            "domainId": domain_id or self.domain_id,
        }
        if slashtag:
            payload["slashtag"] = slashtag
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description

        resp = self._request("POST", "links", json=payload)
        return resp.json()

    def get_link(self, link_id: str) -> Dict[str, Any]:
        """Get a single link by ID."""
        resp = self._request("GET", f"links/{link_id}")
        return resp.json()

    def get_link_by_slashtag(self, slashtag: str) -> Optional[Dict[str, Any]]:
        """Find a link by its exact slashtag."""
        resp = self._request("GET", "links", params={"slashtag": slashtag, "limit": 50})
        links = resp.json()
        for link in links:
            if link.get("slashtag") == slashtag:
                return link
        return None

    def list_links(self, limit: int = 50, order_by: str = "createdAt", order_dir: str = "desc") -> List[Dict[str, Any]]:
        """List links in the workspace."""
        resp = self._request("GET", "links", params={
            "limit": limit,
            "orderBy": order_by,
            "orderDir": order_dir,
        })
        return resp.json()

    def update_link(self, link_id: str, destination: Optional[str] = None,
                     title: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing link's destination or metadata."""
        payload: Dict[str, Any] = {}
        if destination:
            payload["destination"] = destination
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description
        resp = self._request("POST", f"links/{link_id}", json=payload)
        return resp.json()

    def delete_link(self, link_id: str) -> bool:
        """Delete a link."""
        resp = self._request("DELETE", f"links/{link_id}")
        return resp.status_code == 204

    # ── Analytics ───────────────────────────────────────────────

    def get_link_analytics(self, link_id: str) -> Dict[str, Any]:
        """Get click analytics for a link."""
        resp = self._request("GET", f"links/{link_id}/analytics")
        return resp.json()

    def get_link_clicks(self, link_id: str, period: str = "all") -> Dict[str, Any]:
        """Get click count and sessions for a link.
        period: 'day', 'week', 'month', 'all'
        """
        resp = self._request("GET", f"links/{link_id}", params={
            "period": period,
        })
        data = resp.json()
        return {
            "link_id": data.get("id"),
            "short_url": data.get("shortUrl"),
            "destination": data.get("destination"),
            "clicks": data.get("clicks", 0),
            "sessions": data.get("sessions", 0),
            "last_click": data.get("lastClickAt"),
            "status": data.get("status"),
        }

    # ── Bio Pipeline Helpers ────────────────────────────────────

    def create_bio_link(self, variant_key: str, destination: str) -> Dict[str, Any]:
        """Create a bio-variant-specific short link for A/B tracking.
        
        Args:
            variant_key: 'A', 'B', 'C', or 'D'
            destination: The booking page URL
            
        Returns:
            Link dict with shortUrl, id, etc.
        """
        slashtag = f"rm-bio-{variant_key.lower()}"
        title = f"RentMasseur Bio Variant {variant_key} — Booking"
        description = f"Booking link for bio A/B test variant {variant_key}. Created {datetime.now(timezone.utc).isoformat()[:10]}"

        existing = self.get_link_by_slashtag(slashtag)
        if existing:
            logger.info("Link %s already exists, updating destination", slashtag)
            return self.update_link(existing["id"], destination=destination, title=title)
        
        return self.create_link(
            destination=destination,
            slashtag=slashtag,
            title=title,
        )

    def get_all_bio_clicks(self) -> List[Dict[str, Any]]:
        """Get click analytics for all bio-variant links."""
        links = self.list_links(limit=100)
        bio_links = [l for l in links if l.get("slashtag", "").startswith("rm-bio-")]
        results = []
        for link in bio_links:
            results.append({
                "variant": link["slashtag"].replace("rm-bio-", "").upper(),
                "short_url": link["shortUrl"],
                "destination": link["destination"],
                "clicks": link.get("clicks", 0),
                "sessions": link.get("sessions", 0),
                "last_click": link.get("lastClickAt"),
                "status": link.get("status"),
                "link_id": link["id"],
            })
        return results

    def get_carpathianwolf_stats(self) -> Dict[str, Any]:
        """Get stats for the main carpathianwolf link."""
        return self.get_link_clicks(EXISTING_LINK_ID)


# ── CLI ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rebrandly link management")
    parser.add_argument("command", choices=["list", "create", "update", "stats", "bio-links", "carpathianwolf"])
    parser.add_argument("--destination", "-d", help="Destination URL")
    parser.add_argument("--slashtag", "-s", help="Custom slashtag")
    parser.add_argument("--title", "-t", help="Link title")
    parser.add_argument("--variant", "-v", help="Bio variant key (A/B/C/D)")
    parser.add_argument("--link-id", help="Link ID for update/stats")
    args = parser.parse_args()

    client = RebrandlyClient()

    if args.command == "list":
        links = client.list_links(limit=50)
        for l in links:
            print(f"  {l['shortUrl']:30s} → {l['destination'][:60]}")
            print(f"    clicks={l.get('clicks',0)} sessions={l.get('sessions',0)} status={l.get('status','?')}")
            print(f"    id={l['id']}")

    elif args.command == "create":
        if not args.destination:
            print("ERROR: --destination required")
            return
        link = client.create_link(
            destination=args.destination,
            slashtag=args.slashtag,
            title=args.title,
        )
        print(f"Created: {link['shortUrl']} → {link['destination']}")
        print(f"  ID: {link['id']}")
        print(f"  Clicks: {link.get('clicks', 0)}")

    elif args.command == "update":
        if not args.link_id:
            print("ERROR: --link-id required")
            return
        link = client.update_link(args.link_id, destination=args.destination, title=args.title)
        print(f"Updated: {link['shortUrl']} → {link.get('destination', '')}")

    elif args.command == "stats":
        if not args.link_id:
            print("ERROR: --link-id required")
            return
        stats = client.get_link_clicks(args.link_id)
        print(json.dumps(stats, indent=2))

    elif args.command == "bio-links":
        results = client.get_all_bio_clicks()
        if not results:
            print("No bio-variant links found. Create them with: rebrandly_client.py create-bio -v A -d <url>")
        for r in results:
            print(f"  Variant {r['variant']}: {r['short_url']}")
            print(f"    clicks={r['clicks']} sessions={r['sessions']} last_click={r['last_click']}")

    elif args.command == "carpathianwolf":
        stats = client.get_carpathianwolf_stats()
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
