#!/usr/bin/env python3
"""
Extract location data from RentMasseur sitemap
"""

import json
import re
import requests

def extract_locations():
    """Extract all locations from sitemap"""
    
    url = "https://rentmasseur.com/sitemap"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        html = response.text
        
        # Try to find the locations API call
        # Look for the API endpoint pattern
        api_pattern = r'["\'](/api/[^"\']+)["\']'
        api_matches = re.findall(api_pattern, html)
        
        print("Found API endpoints:")
        for match in set(api_matches):
            print(f"  - {match}")
        
        # Try to access the locations API
        print("\nTrying to access locations API...")
        
        # Common API patterns
        api_endpoints = [
            "https://rentmasseur.com/api/locations",
            "https://rentmasseur.com/api/v1/locations",
            "https://rentmasseur.com/api/locations/all",
            "https://rentmasseur.com/api/cities",
        ]
        
        for api_url in api_endpoints:
            try:
                api_response = requests.get(api_url, headers=headers, timeout=10)
                print(f"\nTrying: {api_url}")
                print(f"Status: {api_response.status_code}")
                
                if api_response.status_code == 200:
                    data = api_response.json()
                    print(f"Success! Found {len(data)} locations")
                    print(f"Sample: {json.dumps(data[:3], indent=2) if isinstance(data, list) else data}")
                    return data
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    extract_locations()
