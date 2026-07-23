"""
RentMasseur.com Bio Watcher and Collector
Automates collection of user bios, view tracking, and views per day analysis
"""

import asyncio
import json
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from playwright.async_api import async_playwright, Browser, Page


@dataclass
class MasseurProfile:
    """Data model for masseur profile"""
    username: str
    profile_url: str
    location: str
    registration_date: Optional[str] = None
    total_views: Optional[int] = None
    bio: Optional[str] = None
    massage_types: List[str] = None
    travel_schedule: List[str] = None
    last_updated: str = None
    views_per_day: Optional[float] = None
    
    def __post_init__(self):
        if self.massage_types is None:
            self.massage_types = []
        if self.travel_schedule is None:
            self.travel_schedule = []
        self.last_updated = datetime.now().isoformat()


class RentMasseurScraper:
    """Main scraper class for RentMasseur.com"""
    
    BASE_URL = "https://rentmasseur.com"
    CITY_URL_PATTERN = f"{BASE_URL}/gay-massage/{{city}}"
    PROFILE_URL_PATTERN = f"{BASE_URL}/{{username}}"
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.ua = UserAgent()
        self.profiles: Dict[str, MasseurProfile] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_cities(self) -> List[str]:
        """List of cities to scrape"""
        return [
            "newyork", "losangeles", "manhattan-ny", "atlanta", "miami",
            "london", "west-hollywood-ca", "palmsprings", "chicago", "dallas",
            "sanfrancisco", "ftlauderdale", "sandiego", "houston", "lasvegas-nv",
            "toronto", "washingtondc", "orangecounty-ca", "orlando", "philadelphia"
        ]
    
    async def get_profile_links_from_city(self, browser: Browser, city: str) -> List[str]:
        """Extract profile links from a city page"""
        url = self.CITY_URL_PATTERN.format(city=city)
        print(f"Scraping city: {city}")
        
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)  # Wait for dynamic content
            
            # Extract all profile links
            profile_links = await page.eval_on_selector_all(
                'a[href^="/"]',
                'els => els.map(el => el.href).filter(href => href.match(/rentmasseur\\.com\\/[^\\/]+$/))'
            )
            
            # Clean and deduplicate links
            unique_links = list(set([
                link for link in profile_links 
                if link and not link.endswith('/') and len(link.split('/')[-1]) > 2
            ]))
            
            print(f"Found {len(unique_links)} profiles in {city}")
            return unique_links
            
        except Exception as e:
            print(f"Error scraping {city}: {e}")
            return []
        finally:
            await page.close()
    
    async def scrape_profile(self, browser: Browser, profile_url: str) -> Optional[MasseurProfile]:
        """Scrape individual profile data"""
        username = profile_url.rstrip('/').split('/')[-1]
        print(f"Scraping profile: {username}")
        
        page = await browser.new_page()
        try:
            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Extract profile data
            profile = MasseurProfile(
                username=username,
                profile_url=profile_url
            )
            
            # Location
            try:
                location = await page.text_content('a[href*="gay-massage"]')
                if location:
                    profile.location = location.strip()
            except:
                pass
            
            # Bio/description
            try:
                bio = await page.text_content('.bio, .description, [class*="bio"], [class*="about"]')
                if bio:
                    profile.bio = bio.strip()
            except:
                pass
            
            # Massage types
            try:
                massage_types = await page.eval_on_selector_all(
                    'a[href*="massages/"]',
                    'els => els.map(el => el.textContent.trim())'
                )
                if massage_types:
                    profile.massage_types = massage_types
            except:
                pass
            
            # Travel schedule
            try:
                travel = await page.eval_on_selector_all(
                    '[class*="travel"], [class*="schedule"] a',
                    'els => els.map(el => el.textContent.trim())'
                )
                if travel:
                    profile.travel_schedule = travel
            except:
                pass
            
            # Views (this may require login or be in a specific element)
            try:
                views_text = await page.text_content('[class*="view"], [class*="View"]')
                if views_text:
                    views_match = re.search(r'(\d+[,\d]*)', views_text)
                    if views_match:
                        profile.total_views = int(views_match.group(1).replace(',', ''))
            except:
                pass
            
            # Registration date
            try:
                reg_text = await page.text_content('[class*="member"], [class*="since"], [class*="joined"]')
                if reg_text:
                    date_match = re.search(r'(?:since|joined|member)\s*(.+)', reg_text, re.IGNORECASE)
                    if date_match:
                        profile.registration_date = date_match.group(1).strip()
            except:
                pass
            
            # Calculate views per day if we have both views and registration date
            if profile.total_views and profile.registration_date:
                profile.views_per_day = self.calculate_views_per_day(
                    profile.total_views, 
                    profile.registration_date
                )
            
            return profile
            
        except Exception as e:
            print(f"Error scraping profile {username}: {e}")
            return None
        finally:
            await page.close()
    
    def calculate_views_per_day(self, total_views: int, registration_date: str) -> float:
        """Calculate views per day based on registration date"""
        try:
            # Parse various date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%B %Y', '%b %Y', '%Y']:
                try:
                    reg_date = datetime.strptime(registration_date.split()[0], fmt)
                    days_active = (datetime.now() - reg_date).days
                    if days_active > 0:
                        return round(total_views / days_active, 2)
                except:
                    continue
            return None
        except:
            return None
    
    async def scrape_all_profiles(self, headless: bool = True):
        """Main method to scrape all profiles from all cities"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            
            all_profile_urls = set()
            
            # Collect all profile URLs from all cities
            for city in self.get_cities():
                try:
                    profile_links = await self.get_profile_links_from_city(browser, city)
                    all_profile_urls.update(profile_links)
                except Exception as e:
                    print(f"Error processing city {city}: {e}")
                    continue
            
            print(f"Total unique profiles found: {len(all_profile_urls)}")
            
            # Scrape each profile
            for url in all_profile_urls:
                try:
                    profile = await self.scrape_profile(browser, url)
                    if profile:
                        self.profiles[profile.username] = profile
                except Exception as e:
                    print(f"Error processing profile {url}: {e}")
                    continue
            
            await browser.close()
    
    def save_to_json(self, filename: str = "masseur_profiles.json"):
        """Save profiles to JSON file"""
        filepath = self.data_dir / filename
        data = {
            username: asdict(profile) 
            for username, profile in self.profiles.items()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(self.profiles)} profiles to {filepath}")
    
    def save_to_csv(self, filename: str = "masseur_profiles.csv"):
        """Save profiles to CSV file"""
        filepath = self.data_dir / filename
        rows = []
        for profile in self.profiles.values():
            row = asdict(profile)
            row['massage_types'] = ', '.join(profile.massage_types)
            row['travel_schedule'] = ', '.join(profile.travel_schedule)
            rows.append(row)
        
        if rows:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(rows[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Saved {len(rows)} profiles to {filepath}")
    
    def generate_report(self, filename: str = "views_report.md"):
        """Generate views per day analysis report"""
        filepath = self.data_dir / filename
        
        # Sort by views per day
        sorted_profiles = sorted(
            self.profiles.values(),
            key=lambda x: x.views_per_day or 0,
            reverse=True
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# RentMasseur Views Analysis Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total Profiles: {len(self.profiles)}\n\n")
            
            f.write("## Top Profiles by Views Per Day\n\n")
            f.write("| Username | Location | Total Views | Views/Day | Registered |\n")
            f.write("|----------|----------|-------------|-----------|------------|\n")
            
            for profile in sorted_profiles[:50]:  # Top 50
                f.write(
                    f"| {profile.username} | {profile.location} | "
                    f"{profile.total_views or 'N/A'} | "
                    f"{profile.views_per_day or 'N/A'} | "
                    f"{profile.registration_date or 'N/A'} |\n"
                )
            
            f.write("\n## All Profiles\n\n")
            for profile in sorted_profiles:
                f.write(f"### {profile.username}\n")
                f.write(f"- **Location**: {profile.location}\n")
                f.write(f"- **Total Views**: {profile.total_views or 'N/A'}\n")
                f.write(f"- **Views/Day**: {profile.views_per_day or 'N/A'}\n")
                f.write(f"- **Registered**: {profile.registration_date or 'N/A'}\n")
                f.write(f"- **Massage Types**: {', '.join(profile.massage_types)}\n")
                f.write(f"- **URL**: {profile.profile_url}\n\n")
        
        print(f"Generated report: {filepath}")


async def main():
    """Main entry point"""
    scraper = RentMasseurScraper()
    
    print("Starting RentMasseur scraper...")
    await scraper.scrape_all_profiles(headless=False)  # Set to True for production
    
    print("\nSaving data...")
    scraper.save_to_json()
    scraper.save_to_csv()
    scraper.generate_report()
    
    print(f"\nScraping complete! Total profiles collected: {len(scraper.profiles)}")


if __name__ == "__main__":
    asyncio.run(main())
