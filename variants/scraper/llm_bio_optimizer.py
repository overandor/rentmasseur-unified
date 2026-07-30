#!/usr/bin/env python3
"""
LLM Bio Optimizer
Reads bios, checks stats, writes optimized bios, checks views, adjusts based on top performer
"""

import json
import random
from datetime import datetime
from typing import Dict, List, Any
import re


class LLMBioOptimizer:
    """LLM-driven bio optimization system"""
    
    def __init__(self, filepath: str = "data/masseur_profiles.json"):
        self.filepath = filepath
        self.data = self.load_data()
        self.optimization_history = []
        
    def load_data(self) -> Dict:
        """Load profile data"""
        with open(self.filepath, 'r') as f:
            return json.load(f)
    
    def save_data(self):
        """Save updated profile data"""
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def analyze_bio_characteristics(self, bio: str) -> Dict[str, Any]:
        """Analyze bio characteristics for LLM pattern matching"""
        if not bio:
            return {
                'length': 0,
                'words': 0,
                'sentences': 0,
                'availability_mentions': 0,
                'experience_mentions': 0,
                'benefit_mentions': 0,
                'urgency_mentions': 0,
                'specialty_mentions': 0,
                'keywords': []
            }
        
        characteristics = {
            'length': len(bio),
            'words': len(bio.split()),
            'sentences': len(re.split(r'[.!?]+', bio)),
            'availability_mentions': 0,
            'experience_mentions': 0,
            'benefit_mentions': 0,
            'urgency_mentions': 0,
            'specialty_mentions': 0,
            'keywords': []
        }
        
        # Count keyword mentions
        availability_keywords = ['24/7', 'available', 'anytime', 'flexible', 'schedule', 'same day']
        experience_keywords = ['experienced', 'trained', 'certified', 'professional', 'years', 'expert']
        benefit_keywords = ['relax', 'stress', 'pain', 'wellness', 'relief', 'healing', 'therapy']
        urgency_keywords = ['book now', 'today', 'contact', 'call', 'schedule', 'appointment']
        specialty_keywords = ['deep tissue', 'swedish', 'therapeutic', 'sports', 'sensual', 'massage']
        
        bio_lower = bio.lower()
        
        for keyword in availability_keywords:
            if keyword in bio_lower:
                characteristics['availability_mentions'] += 1
                characteristics['keywords'].append(keyword)
        
        for keyword in experience_keywords:
            if keyword in bio_lower:
                characteristics['experience_mentions'] += 1
                characteristics['keywords'].append(keyword)
        
        for keyword in benefit_keywords:
            if keyword in bio_lower:
                characteristics['benefit_mentions'] += 1
                characteristics['keywords'].append(keyword)
        
        for keyword in urgency_keywords:
            if keyword in bio_lower:
                characteristics['urgency_mentions'] += 1
                characteristics['keywords'].append(keyword)
        
        for keyword in specialty_keywords:
            if keyword in bio_lower:
                characteristics['specialty_mentions'] += 1
                characteristics['keywords'].append(keyword)
        
        return characteristics
    
    def identify_top_performer(self) -> Dict[str, Any]:
        """Identify the top-performing bio by views"""
        profiles_with_bios = {
            username: profile 
            for username, profile in self.data.items() 
            if len(profile.get('bio', '')) > 10
        }
        
        if not profiles_with_bios:
            # If no real bios, use karpathianwolf as top performer
            if 'karpathianwolf' in self.data:
                return {
                    'username': 'karpathianwolf',
                    'profile': self.data['karpathianwolf'],
                    'characteristics': self.analyze_bio_characteristics(self.data['karpathianwolf'].get('bio', ''))
                }
            return None
        
        # Sort by views (using placeholder data for now)
        sorted_profiles = sorted(
            profiles_with_bios.items(),
            key=lambda x: x[1].get('total_views', 0),
            reverse=True
        )
        
        top_username, top_profile = sorted_profiles[0]
        
        return {
            'username': top_username,
            'profile': top_profile,
            'characteristics': self.analyze_bio_characteristics(top_profile.get('bio', ''))
        }
    
    def extract_llm_patterns(self, top_performer: Dict[str, Any]) -> Dict[str, Any]:
        """Extract patterns from top performer for LLM to learn"""
        characteristics = top_performer['characteristics']
        
        patterns = {
            'optimal_length_range': (max(100, characteristics['length'] - 100), characteristics['length'] + 100),
            'optimal_word_count': characteristics['words'],
            'optimal_sentence_count': characteristics['sentences'],
            'keyword_density': {
                'availability': characteristics['availability_mentions'],
                'experience': characteristics['experience_mentions'],
                'benefits': characteristics['benefit_mentions'],
                'urgency': characteristics['urgency_mentions'],
                'specialties': characteristics['specialty_mentions']
            },
            'successful_keywords': characteristics['keywords'],
            'structure_hints': self.analyze_structure(top_performer['profile'].get('bio', ''))
        }
        
        return patterns
    
    def analyze_structure(self, bio: str) -> List[str]:
        """Analyze bio structure for patterns"""
        structure = []
        
        if '24/7' in bio or 'available' in bio.lower():
            structure.append('availability_statement')
        
        if 'experience' in bio.lower() or 'trained' in bio.lower():
            structure.append('experience_section')
        
        if any(word in bio.lower() for word in ['relax', 'stress', 'pain']):
            structure.append('benefits_section')
        
        if any(word in bio.lower() for word in ['book', 'contact', 'call', 'schedule']):
            structure.append('call_to_action')
        
        return structure
    
    def generate_optimized_bio(self, username: str, patterns: Dict[str, Any]) -> str:
        """Generate optimized bio using LLM-learned patterns"""
        profile = self.data.get(username, {})
        
        # Base bio template
        bio_templates = {
            'short': """Professional masseur available 24/7. Specializing in therapeutic massage for stress relief and pain management. Book today for your customized session.""",
            
            'medium': """Professional male masseur with extensive training in multiple modalities. 
Available 24/7 for your convenience with flexible scheduling.
Specializing in deep tissue and Swedish massage for stress relief and pain management.
Clean, safe, and professional environment guaranteed.
Contact me to schedule your session today!""",
            
            'long': """Professional male masseur specializing in therapeutic and relaxation massage. 
With extensive training in multiple modalities, I provide customized sessions tailored to your specific needs.
My approach combines deep tissue techniques with soothing Swedish massage to release tension and promote overall wellness.
Clean, safe, and professional environment guaranteed.

**My Stats:**
- Available 24/7 for your convenience
- Same-day appointments often available
- Late night and early morning sessions
- Weekend and holiday availability

**Why Choose Me:**
- Experienced practitioner with dedicated client service
- Specialized in deep tissue and therapeutic massage
- Consistently rated for exceptional service

**Contact me to schedule your session today!**
I'm committed to providing exceptional service around the clock to accommodate your busy schedule."""
        }
        
        # Select template based on patterns
        optimal_length = patterns['optimal_length_range'][0]
        
        if optimal_length < 200:
            template = bio_templates['short']
        elif optimal_length < 500:
            template = bio_templates['medium']
        else:
            template = bio_templates['long']
        
        # Customize with username-specific elements
        optimized_bio = template
        
        # Add keyword density adjustments
        keyword_density = patterns['keyword_density']
        
        # Ensure availability mentions match top performer
        if keyword_density['availability'] > 2:
            if '24/7' not in optimized_bio:
                optimized_bio = optimized_bio.replace('Available', 'Available 24/7')
        
        # Add experience mentions if needed
        if keyword_density['experience'] > 1 and 'experienced' not in optimized_bio.lower():
            optimized_bio = optimized_bio.replace('Professional', 'Professional and experienced')
        
        return optimized_bio
    
    def optimize_all_bios(self):
        """Optimize all bios based on top performer patterns"""
        print("="*80)
        print("LLM Bio Optimization System")
        print("="*80)
        print(f"Started: {datetime.now().isoformat()}")
        print()
        
        # Step 1: Identify top performer
        print("Step 1: Identifying top-performing bio...")
        top_performer = self.identify_top_performer()
        
        if not top_performer:
            print("No top performer found. Using default patterns.")
            return
        
        print(f"Top performer: {top_performer['username']}")
        print(f"Views: {top_performer['profile'].get('total_views', 0)}")
        print()
        
        # Step 2: Extract patterns
        print("Step 2: Extracting LLM patterns from top performer...")
        patterns = self.extract_llm_patterns(top_performer)
        
        print("Patterns identified:")
        print(f"  Optimal length: {patterns['optimal_length_range']}")
        print(f"  Optimal words: {patterns['optimal_word_count']}")
        print(f"  Optimal sentences: {patterns['optimal_sentence_count']}")
        print(f"  Keyword density: {patterns['keyword_density']}")
        print(f"  Successful keywords: {patterns['successful_keywords']}")
        print(f"  Structure: {patterns['structure_hints']}")
        print()
        
        # Step 3: Optimize each bio
        print("Step 3: Optimizing bios based on patterns...")
        
        optimization_results = []
        
        for username, profile in self.data.items():
            current_bio = profile.get('bio', '')
            current_views = profile.get('total_views', 0)
            
            # Skip if already the top performer
            if username == top_performer['username']:
                print(f"  Skipping {username} (top performer)")
                continue
            
            # Generate optimized bio
            optimized_bio = self.generate_optimized_bio(username, patterns)
            
            # Calculate expected improvement (simulation)
            current_characteristics = self.analyze_bio_characteristics(current_bio)
            optimized_characteristics = self.analyze_bio_characteristics(optimized_bio)
            
            improvement_score = self.calculate_improvement_score(
                current_characteristics, 
                optimized_characteristics, 
                patterns
            )
            
            # Update profile
            old_bio = current_bio
            self.data[username]['bio'] = optimized_bio
            self.data[username]['last_updated'] = datetime.now().isoformat()
            
            # Record optimization
            optimization_results.append({
                'username': username,
                'old_bio_length': len(old_bio),
                'new_bio_length': len(optimized_bio),
                'improvement_score': improvement_score,
                'expected_view_increase': int(current_views * (improvement_score / 100))
            })
            
            print(f"  Optimized {username}: {len(old_bio)} -> {len(optimized_bio)} chars (score: {improvement_score:.1f})")
        
        # Save updated data
        self.save_data()
        
        print()
        print("Step 4: Optimization complete!")
        print()
        
        # Step 5: Generate report
        self.generate_optimization_report(optimization_results, top_performer, patterns)
    
    def calculate_improvement_score(self, current: Dict, optimized: Dict, patterns: Dict) -> float:
        """Calculate improvement score based on pattern matching"""
        score = 0.0
        
        # Length optimization
        optimal_min, optimal_max = patterns['optimal_length_range']
        if optimal_min <= optimized['length'] <= optimal_max:
            score += 20
        elif current['length'] == 0 and optimized['length'] > 0:
            score += 30
        
        # Keyword density matching
        keyword_density = patterns['keyword_density']
        
        if optimized['availability_mentions'] >= keyword_density['availability']:
            score += 15
        if optimized['experience_mentions'] >= keyword_density['experience']:
            score += 10
        if optimized['benefit_mentions'] >= keyword_density['benefits']:
            score += 10
        if optimized['urgency_mentions'] >= keyword_density['urgency']:
            score += 10
        if optimized['specialty_mentions'] >= keyword_density['specialties']:
            score += 10
        
        # Structure matching
        structure_hints = patterns['structure_hints']
        if len(optimized['keywords']) >= len(patterns['successful_keywords']):
            score += 15
        
        return min(score, 100)
    
    def generate_optimization_report(self, results: List[Dict], top_performer: Dict, patterns: Dict):
        """Generate optimization report"""
        print("="*80)
        print("OPTIMIZATION REPORT")
        print("="*80)
        print()
        
        print("Top Performer Analysis:")
        print(f"  Username: {top_performer['username']}")
        print(f"  Views: {top_performer['profile'].get('total_views', 0)}")
        print(f"  Bio length: {top_performer['characteristics']['length']} characters")
        print()
        
        print("Patterns Applied:")
        print(f"  Optimal length range: {patterns['optimal_length_range']}")
        print(f"  Keyword density targets: {patterns['keyword_density']}")
        print()
        
        print("Optimization Results:")
        print("-" * 80)
        
        total_improvement = 0
        total_expected_increase = 0
        
        for result in sorted(results, key=lambda x: x['improvement_score'], reverse=True):
            print(f"{result['username']}:")
            print(f"  Bio length: {result['old_bio_length']} -> {result['new_bio_length']}")
            print(f"  Improvement score: {result['improvement_score']:.1f}%")
            print(f"  Expected view increase: +{result['expected_view_increase']}")
            print()
            
            total_improvement += result['improvement_score']
            total_expected_increase += result['expected_view_increase']
        
        print("-" * 80)
        print(f"Total profiles optimized: {len(results)}")
        print(f"Average improvement score: {total_improvement/len(results):.1f}%")
        print(f"Total expected view increase: +{total_expected_increase}")
        print()
        
        print("Next Steps:")
        print("1. Update profiles on RentMasseur with optimized bios")
        print("2. Monitor view changes over 7-14 days")
        print("3. Re-run optimization with actual view data")
        print("4. Iterate and refine patterns based on real results")
        print()
        
        print("Data saved to: data/masseur_profiles.json")


def main():
    """Main entry point"""
    optimizer = LLMBioOptimizer()
    optimizer.optimize_all_bios()


if __name__ == "__main__":
    main()
