#!/usr/bin/env python3
"""
Extract full profile data including contact information
"""

import json
import re
import requests

def extract_profile_data(username):
    """Extract all data from a profile"""
    
    url = f"https://rentmasseur.com/{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        html = response.text
        
        # Extract JSON data from the page
        json_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>'
        json_match = re.search(json_pattern, html, re.DOTALL)
        
        if json_match:
            json_data = json.loads(json_match.group(1))
            
            # Save full JSON for inspection
            with open(f"debug_{username}_json.json", "w") as f:
                json.dump(json_data, f, indent=2)
            
            print(f"Full JSON saved to debug_{username}_json.json")
            
            # Try different paths to find profile data
            try:
                # Try different possible structures
                if 'props' in json_data and 'pageProps' in json_data['props']:
                    page_props = json_data['props']['pageProps']
                    
                    if 'profile' in page_props:
                        profile_data = page_props['profile']
                    elif 'user' in page_props:
                        profile_data = page_props['user']
                    elif 'data' in page_props:
                        profile_data = page_props['data']
                    else:
                        # Print available keys
                        print(f"Available keys in pageProps: {list(page_props.keys())}")
                        profile_data = page_props
                else:
                    # Print available keys at root
                    print(f"Available keys at root: {list(json_data.keys())}")
                    profile_data = json_data
                
                print(f"Profile: {username}")
                print("="*60)
                
                # Print structure
                def print_structure(data, indent=0):
                    if isinstance(data, dict):
                        for key, value in data.items():
                            print("  " * indent + f"{key}: {type(value).__name__}")
                            if indent < 3 and isinstance(value, (dict, list)):
                                print_structure(value, indent + 1)
                    elif isinstance(data, list) and data:
                        print("  " * indent + f"List with {len(data)} items")
                        if indent < 2:
                            print_structure(data[0], indent + 1)
                
                print_structure(profile_data)
                
                return profile_data
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print("No JSON data found in page")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    # Test with karpathianwolf
    extract_profile_data("Karpathianwolf")
