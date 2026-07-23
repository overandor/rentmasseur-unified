#!/usr/bin/env python3
"""
Test if individual profile pages are still accessible without captcha
"""

import requests

def test_profile_access():
    """Test if profile pages are accessible"""
    
    test_usernames = [
        "Karpathianwolf",
        "Leo_NYCBest",
        "Will_Xavier",
        "SportsMassageNYC",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    for username in test_usernames:
        url = f"https://rentmasseur.com/{username}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"{username}: Status {response.status_code}, Length {len(response.text)}")
            
            if "CrowdSec" in response.text:
                print(f"  -> BLOCKED by CrowdSec captcha")
            elif "username" in response.text.lower() or "bio" in response.text.lower():
                print(f"  -> Profile page accessible")
            else:
                print(f"  -> Unknown response")
        except Exception as e:
            print(f"{username}: Error - {e}")

if __name__ == "__main__":
    test_profile_access()
