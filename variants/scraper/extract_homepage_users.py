#!/usr/bin/env python3
"""
Extract usernames from RentMasseur homepage
"""

import json
import re
import requests

def extract_homepage_usernames():
    """Extract usernames from homepage HTML"""
    
    url = "https://rentmasseur.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        html = response.text
        
        # Extract usernames from the embedded JSON data
        username_pattern = r'"username":"([^"]+)"'
        usernames = re.findall(username_pattern, html)
        
        # Remove duplicates while preserving order
        unique_usernames = list(dict.fromkeys(usernames))
        
        print(f"Found {len(unique_usernames)} unique usernames on homepage")
        print()
        print("Homepage Usernames:")
        for i, username in enumerate(unique_usernames, 1):
            print(f"{i}. {username}")
        
        return unique_usernames
        
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    extract_homepage_usernames()
