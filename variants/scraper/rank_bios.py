#!/usr/bin/env python3
"""
RentMasseur Bio Ranking by Views
Ranks masseur bios based on view data
"""

import json
from datetime import datetime
from typing import List, Dict, Any


class BioRanker:
    """Ranks masseur bios by views"""
    
    def __init__(self):
        self.profiles = []
        
    def load_profiles(self, filepath: str = "data/masseur_profiles.json"):
        """Load profiles from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.profiles = [
            {**profile_data, 'username': username}
            for username, profile_data in data.items()
        ]
        print(f"Loaded {len(self.profiles)} profiles")
        
    def rank_by_views(self) -> List[Dict[str, Any]]:
        """Simple ranking by total views"""
        ranked = sorted(
            self.profiles,
            key=lambda x: x.get('total_views', 0),
            reverse=True
        )
        return ranked
    
    def generate_report(self, ranked_profiles: List[Dict[str, Any]], output_file: str = "data/ranked_bios.md"):
        """Generate markdown report"""
        with open(output_file, 'w') as f:
            f.write("# RentMasseur Bio Ranking Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total Profiles Analyzed: {len(ranked_profiles)}\n\n")
            
            f.write("## Rankings by Views\n\n")
            f.write("| Rank | Username | Total Views | Views/Day | Location | Bio Preview |\n")
            f.write("|------|----------|-------------|-----------|----------|-------------|\n")
            
            for idx, profile in enumerate(ranked_profiles, 1):
                bio_preview = profile.get('bio', 'N/A')[:50] + "..." if profile.get('bio') else "No bio"
                f.write(
                    f"| {idx} | {profile['username']} | "
                    f"{profile.get('total_views', 'N/A')} | "
                    f"{profile.get('views_per_day', 'N/A')} | "
                    f"{profile.get('location', 'N/A')} | "
                    f"{bio_preview} |\n"
                )
            
            f.write("\n## Detailed Profiles\n\n")
            for idx, profile in enumerate(ranked_profiles, 1):
                f.write(f"### {idx}. {profile['username']}\n\n")
                f.write(f"- **Profile URL**: {profile['profile_url']}\n")
                f.write(f"- **Total Views**: {profile.get('total_views', 'N/A')}\n")
                f.write(f"- **Views Per Day**: {profile.get('views_per_day', 'N/A')}\n")
                f.write(f"- **Location**: {profile.get('location', 'N/A')}\n")
                f.write(f"- **Registration Date**: {profile.get('registration_date', 'N/A')}\n")
                f.write(f"- **Bio**: {profile.get('bio', 'No bio available')}\n")
                f.write(f"- **Last Updated**: {profile.get('last_updated', 'N/A')}\n\n")
        
        print(f"Report generated: {output_file}")


def main():
    """Main entry point"""
    ranker = BioRanker()
    
    # Load profiles
    ranker.load_profiles()
    
    # Rank by views
    print("\n=== Ranking by Views ===")
    ranked = ranker.rank_by_views()
    
    # Print rankings to console
    print("\nTop Profiles by Views:")
    print("-" * 80)
    for idx, profile in enumerate(ranked, 1):
        print(f"{idx}. {profile['username']}")
        print(f"   Views: {profile.get('total_views', 'N/A')}")
        print(f"   Views/Day: {profile.get('views_per_day', 'N/A')}")
        print(f"   Location: {profile.get('location', 'N/A')}")
        print(f"   Bio: {profile.get('bio', 'No bio')[:100]}")
        print()
    
    # Generate report
    ranker.generate_report(ranked)
    
    print("\nRanking complete!")


if __name__ == "__main__":
    main()
