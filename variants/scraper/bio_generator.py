#!/usr/bin/env python3
"""
Dynamic Bio Generator for karpathianwolf
Generates bio content based on view metrics with 24/7 availability
"""

import json
from datetime import datetime
from typing import Dict, Any


class BioGenerator:
    """Generates dynamic bios based on view metrics"""
    
    def __init__(self, username: str = "karpathianwolf"):
        self.username = username
        self.base_bio = self.get_base_bio()
        
    def get_base_bio(self) -> str:
        """Base bio template"""
        return """Professional male masseur specializing in therapeutic and relaxation massage. 
With extensive training in multiple modalities, I provide customized sessions tailored to your specific needs.
My approach combines deep tissue techniques with soothing Swedish massage to release tension and promote overall wellness.
Clean, safe, and professional environment guaranteed."""
    
    def generate_bio_by_views(self, total_views: int, views_per_day: float = 0) -> str:
        """Generate bio content based on view metrics"""
        
        # Determine performance tier
        if total_views > 10000:
            tier = "elite"
            experience = "highly sought-after"
            availability = "Limited availability - book in advance"
        elif total_views > 5000:
            tier = "established"
            experience = "well-regarded"
            availability = "Weekend and evening availability"
        elif total_views > 1000:
            tier = "growing"
            experience = "dedicated"
            availability = "Flexible scheduling"
        else:
            tier = "new"
            experience = "passionate"
            availability = "Building my client base - great introductory rates"
        
        # Generate dynamic bio
        bio = f"""{self.base_bio}

**My Stats:**
- Total Profile Views: {total_views:,}
- Daily Engagement: {views_per_day:.1f} views/day
- Experience Level: {tier}
- Client Satisfaction: {experience}

**Availability:**
✅ Available 24/7 for your convenience
✅ Same-day appointments often available
✅ Late night and early morning sessions
✅ Weekend and holiday availability

**Why Choose Me:**
- {self.get_tier_benefit(tier)}
- Consistently rated {self.get_rating(tier)} by clients
- {self.get_specialty(tier)}

**Contact me to schedule your session today!**
I'm committed to providing exceptional service around the clock to accommodate your busy schedule."""
        
        return bio
    
    def get_tier_benefit(self, tier: str) -> str:
        """Get benefit based on performance tier"""
        benefits = {
            "elite": "Proven track record with hundreds of satisfied clients",
            "established": "Experienced practitioner with loyal client base",
            "growing": "Fresh energy and dedication to each session",
            "new": "Enthusiastic and eager to exceed expectations"
        }
        return benefits.get(tier, benefits["new"])
    
    def get_rating(self, tier: str) -> str:
        """Get rating based on performance tier"""
        ratings = {
            "elite": "5 stars",
            "established": "4.8 stars",
            "growing": "4.5 stars",
            "new": "building 5-star reputation"
        }
        return ratings.get(tier, ratings["new"])
    
    def get_specialty(self, tier: str) -> str:
        """Get specialty based on performance tier"""
        specialties = {
            "elite": "Advanced techniques for chronic pain and stress relief",
            "established": "Specialized in deep tissue and sports massage",
            "growing": "Skilled in Swedish and therapeutic massage",
            "new": "Training in multiple massage modalities"
        }
        return specialties.get(tier, specialties["new"])
    
    def update_profile_data(self, filepath: str = "data/masseur_profiles.json"):
        """Update profile with new bio"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if self.username in data:
                total_views = data[self.username].get('total_views', 0)
                views_per_day = data[self.username].get('views_per_day', 0)
                
                # Generate new bio
                new_bio = self.generate_bio_by_views(total_views, views_per_day)
                
                # Update profile
                data[self.username]['bio'] = new_bio
                data[self.username]['last_updated'] = datetime.now().isoformat()
                
                # Save back
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"Updated bio for {self.username}")
                print(f"Total views: {total_views}")
                print(f"Views per day: {views_per_day}")
                return True
            else:
                print(f"Profile {self.username} not found")
                return False
                
        except Exception as e:
            print(f"Error updating profile: {e}")
            return False
    
    def generate_all_tiers(self):
        """Generate bios for all performance tiers"""
        print("=== Bio Templates by Performance Tier ===\n")
        
        tiers = [
            (50000, 150, "Elite - High Volume"),
            (10000, 30, "Elite"),
            (5000, 15, "Established"),
            (1000, 5, "Growing"),
            (500, 2, "New")
        ]
        
        for views, vpd, label in tiers:
            print(f"\n{'='*60}")
            print(f"{label} ({views:,} views, {vpd} views/day)")
            print('='*60)
            bio = self.generate_bio_by_views(views, vpd)
            print(bio)
            print()


def main():
    """Main entry point"""
    generator = BioGenerator("karpathianwolf")
    
    # Update actual profile
    print("Updating karpathianwolf profile...")
    generator.update_profile_data()
    
    # Show all tier options
    print("\n" + "="*60)
    print("Generating bio templates for different performance levels...")
    print("="*60)
    generator.generate_all_tiers()
    
    print("\nBio generation complete!")
    print("To manually update your profile on RentMasseur:")
    print("1. Visit https://rentmasseur.com/karpathianwolf")
    print("2. Login with your credentials")
    print("3. Copy the appropriate bio from above")
    print("4. Update your profile bio section")


if __name__ == "__main__":
    main()
