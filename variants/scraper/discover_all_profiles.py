#!/usr/bin/env python3
"""
Discover all RentMasseur profiles by scraping city pages
"""

import json
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def get_locations():
    """Get all locations from API"""
    url = "https://rentmasseur.com/api/locations"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Found {len(data)} locations")
            return data
        else:
            print(f"Failed with status {response.status_code}")
            # Try alternative approach - use hardcoded major cities
            print("Using hardcoded major cities as fallback...")
            return [
                {'searchCity': 'newyork', 'label': 'New York City', 'country': 'USA'},
                {'searchCity': 'manhattan-ny', 'label': 'Manhattan', 'country': 'USA'},
                {'searchCity': 'losangeles', 'label': 'Los Angeles', 'country': 'USA'},
                {'searchCity': 'chicago', 'label': 'Chicago', 'country': 'USA'},
                {'searchCity': 'saopaulo', 'label': 'Sao Paulo', 'country': 'Brazil'},
                {'searchCity': 'london', 'label': 'London', 'country': 'UK'},
                {'searchCity': 'paris', 'label': 'Paris', 'country': 'France'},
                {'searchCity': 'toronto', 'label': 'Toronto', 'country': 'Canada'},
                {'searchCity': 'sydney', 'label': 'Sydney', 'country': 'Australia'},
                {'searchCity': 'miami', 'label': 'Miami', 'country': 'USA'},
            ]
    except Exception as e:
        print(f"Error: {e}")
        return []

def extract_usernames_from_city(location):
    """Extract usernames from a city page"""
    search_city = location.get('searchCity', '')
    city_name = location.get('label', search_city)
    url = f"https://rentmasseur.com/gay-massage/{search_city}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            html = response.text
            username_pattern = r'"username":"([^"]+)"'
            usernames = re.findall(username_pattern, html)
            return {
                'city': city_name,
                'search_city': search_city,
                'usernames': usernames,
                'count': len(usernames)
            }
    except Exception as e:
        print(f"Error processing {city_name}: {e}")
    
    return {
        'city': city_name,
        'search_city': search_city,
        'usernames': [],
        'count': 0
    }

def main():
    print("Fetching locations...")
    locations = get_locations()
    print(f"Found {len(locations)} locations")
    
    all_usernames = set()
    city_results = []
    
    # Process cities with threading for speed
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(extract_usernames_from_city, loc): loc for loc in locations}
        
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            city_results.append(result)
            all_usernames.update(result['usernames'])
            
            print(f"[{i+1}/{len(locations)}] {result['city']}: {result['count']} usernames")
            
            # Small delay to be respectful
            time.sleep(0.1)
    
    # Save results
    output = {
        'total_unique_usernames': len(all_usernames),
        'total_cities_processed': len(city_results),
        'cities': city_results,
        'all_usernames': sorted(list(all_usernames))
    }
    
    with open('all_discovered_profiles.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Discovery complete!")
    print(f"Total unique usernames: {len(all_usernames)}")
    print(f"Total cities processed: {len(city_results)}")
    print(f"Output saved to: all_discovered_profiles.json")
    
    # Also save just the usernames for easy processing
    with open('all_usernames_list.txt', 'w') as f:
        for username in sorted(all_usernames):
            f.write(f"{username}\n")
    
    print(f"Username list saved to: all_usernames_list.txt")

if __name__ == "__main__":
    main()
