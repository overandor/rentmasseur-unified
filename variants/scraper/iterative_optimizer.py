#!/usr/bin/env python3
"""
Iterative Bio Optimizer with Real View Data
Allows manual entry of actual view data and refines patterns based on real results
"""

import json
from datetime import datetime
from typing import Dict, List, Any
import re


class IterativeBioOptimizer:
    """Iterative optimization system with real data integration"""
    
    def __init__(self, filepath: str = "data/masseur_profiles.json"):
        self.filepath = filepath
        self.data = self.load_data()
        self.optimization_history = []
        self.pattern_history = []
        
    def load_data(self) -> Dict:
        """Load profile data"""
        with open(self.filepath, 'r') as f:
            return json.load(f)
    
    def save_data(self):
        """Save updated profile data"""
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def enter_real_view_data(self):
        """Interactive system for entering real view data"""
        print("="*80)
        print("REAL VIEW DATA ENTRY SYSTEM")
        print("="*80)
        print("Enter actual view counts for each profile")
        print("Press Enter to skip a profile or use placeholder value")
        print()
        
        for username in sorted(self.data.keys()):
            current_views = self.data[username].get('total_views', 0)
            print(f"Profile: {username}")
            print(f"Current views: {current_views}")
            
            user_input = input(f"Enter actual views (or press Enter to keep {current_views}): ").strip()
            
            if user_input:
                try:
                    new_views = int(user_input)
                    self.data[username]['total_views'] = new_views
                    print(f"  Updated to: {new_views}")
                except ValueError:
                    print(f"  Invalid input, keeping {current_views}")
            else:
                print(f"  Keeping {current_views}")
            
            print()
        
        self.save_data()
        print("Real view data saved!")
        print()
    
    def calculate_views_per_day(self, username: str) -> float:
        """Calculate views per day based on registration date"""
        profile = self.data[username]
        total_views = profile.get('total_views', 0)
        reg_date = profile.get('registration_date', '')
        
        if not reg_date or total_views == 0:
            return 0.0
        
        try:
            # Try different date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%B %Y', '%b %Y', '%Y']:
                try:
                    reg_date_obj = datetime.strptime(reg_date.split()[0], fmt)
                    days_active = (datetime.now() - reg_date_obj).days
                    if days_active > 0:
                        return round(total_views / days_active, 2)
                except:
                    continue
        except:
            pass
        return 0.0
    
    def analyze_bio_characteristics(self, bio: str) -> Dict[str, Any]:
        """Analyze bio characteristics"""
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
    
    def identify_top_performers(self, top_n: int = 3) -> List[Dict[str, Any]]:
        """Identify top performers by views"""
        profiles_with_data = [
            (username, profile)
            for username, profile in self.data.items()
            if profile.get('total_views', 0) > 0
        ]
        
        sorted_profiles = sorted(
            profiles_with_data,
            key=lambda x: x[1].get('total_views', 0),
            reverse=True
        )
        
        top_performers = []
        for username, profile in sorted_profiles[:top_n]:
            top_performers.append({
                'username': username,
                'profile': profile,
                'characteristics': self.analyze_bio_characteristics(profile.get('bio', '')),
                'views_per_day': self.calculate_views_per_day(username)
            })
        
        return top_performers
    
    def extract_refined_patterns(self, top_performers: List[Dict]) -> Dict[str, Any]:
        """Extract refined patterns from multiple top performers"""
        if not top_performers:
            return {}
        
        # Aggregate characteristics from top performers
        aggregated = {
            'lengths': [],
            'words': [],
            'sentences': [],
            'availability_mentions': [],
            'experience_mentions': [],
            'benefit_mentions': [],
            'urgency_mentions': [],
            'specialty_mentions': [],
            'all_keywords': []
        }
        
        for performer in top_performers:
            chars = performer['characteristics']
            aggregated['lengths'].append(chars['length'])
            aggregated['words'].append(chars['words'])
            aggregated['sentences'].append(chars['sentences'])
            aggregated['availability_mentions'].append(chars['availability_mentions'])
            aggregated['experience_mentions'].append(chars['experience_mentions'])
            aggregated['benefit_mentions'].append(chars['benefit_mentions'])
            aggregated['urgency_mentions'].append(chars['urgency_mentions'])
            aggregated['specialty_mentions'].append(chars['specialty_mentions'])
            aggregated['all_keywords'].extend(chars['keywords'])
        
        # Calculate refined patterns
        refined_patterns = {
            'optimal_length_range': (
                min(aggregated['lengths']) if aggregated['lengths'] else 100,
                max(aggregated['lengths']) if aggregated['lengths'] else 1000
            ),
            'optimal_word_count': int(sum(aggregated['words']) / len(aggregated['words'])) if aggregated['words'] else 100,
            'optimal_sentence_count': int(sum(aggregated['sentences']) / len(aggregated['sentences'])) if aggregated['sentences'] else 5,
            'keyword_density': {
                'availability': int(sum(aggregated['availability_mentions']) / len(aggregated['availability_mentions'])) if aggregated['availability_mentions'] else 2,
                'experience': int(sum(aggregated['experience_mentions']) / len(aggregated['experience_mentions'])) if aggregated['experience_mentions'] else 1,
                'benefits': int(sum(aggregated['benefit_mentions']) / len(aggregated['benefit_mentions'])) if aggregated['benefit_mentions'] else 2,
                'urgency': int(sum(aggregated['urgency_mentions']) / len(aggregated['urgency_mentions'])) if aggregated['urgency_mentions'] else 2,
                'specialties': int(sum(aggregated['specialty_mentions']) / len(aggregated['specialty_mentions'])) if aggregated['specialty_mentions'] else 2
            },
            'successful_keywords': list(set(aggregated['all_keywords'])),
            'sample_count': len(top_performers)
        }
        
        return refined_patterns
    
    def generate_refined_bio(self, username: str, patterns: Dict[str, Any]) -> str:
        """Generate bio using refined patterns"""
        profile = self.data.get(username, {})
        
        # Bio templates based on refined patterns
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
        
        # Select template based on refined patterns
        optimal_length = patterns['optimal_length_range'][0]
        
        if optimal_length < 200:
            template = bio_templates['short']
        elif optimal_length < 500:
            template = bio_templates['medium']
        else:
            template = bio_templates['long']
        
        # Customize with refined keyword density
        keyword_density = patterns['keyword_density']
        optimized_bio = template
        
        # Adjust availability mentions
        if keyword_density['availability'] > 2:
            if '24/7' not in optimized_bio:
                optimized_bio = optimized_bio.replace('Available', 'Available 24/7')
        
        # Adjust experience mentions
        if keyword_density['experience'] > 1 and 'experienced' not in optimized_bio.lower():
            optimized_bio = optimized_bio.replace('Professional', 'Professional and experienced')
        
        return optimized_bio
    
    def run_iterative_optimization(self):
        """Run iterative optimization with real data"""
        print("="*80)
        print("ITERATIVE BIO OPTIMIZATION WITH REAL DATA")
        print("="*80)
        print(f"Started: {datetime.now().isoformat()}")
        print()
        
        # Step 1: Enter real view data
        print("Step 1: Enter real view data")
        print("-" * 80)
        self.enter_real_view_data()
        
        # Step 2: Identify top performers
        print("Step 2: Identifying top performers...")
        top_performers = self.identify_top_performers(top_n=3)
        
        if not top_performers:
            print("No profiles with view data found. Using default patterns.")
            return
        
        print(f"Top {len(top_performers)} performers:")
        for i, performer in enumerate(top_performers, 1):
            print(f"  {i}. {performer['username']}: {performer['profile'].get('total_views', 0)} views ({performer['views_per_day']}/day)")
        print()
        
        # Step 3: Extract refined patterns
        print("Step 3: Extracting refined patterns from top performers...")
        refined_patterns = self.extract_refined_patterns(top_performers)
        
        print("Refined patterns:")
        print(f"  Sample size: {refined_patterns['sample_count']} profiles")
        print(f"  Optimal length: {refined_patterns['optimal_length_range']}")
        print(f"  Optimal words: {refined_patterns['optimal_word_count']}")
        print(f"  Optimal sentences: {refined_patterns['optimal_sentence_count']}")
        print(f"  Keyword density: {refined_patterns['keyword_density']}")
        print(f"  Successful keywords: {refined_patterns['successful_keywords']}")
        print()
        
        # Save pattern history
        self.pattern_history.append({
            'timestamp': datetime.now().isoformat(),
            'patterns': refined_patterns,
            'top_performers': [p['username'] for p in top_performers]
        })
        
        # Step 4: Optimize bios with refined patterns
        print("Step 4: Optimizing bios with refined patterns...")
        
        optimization_results = []
        top_usernames = {p['username'] for p in top_performers}
        
        for username, profile in self.data.items():
            # Skip top performers
            if username in top_usernames:
                print(f"  Skipping {username} (top performer)")
                continue
            
            current_bio = profile.get('bio', '')
            current_views = profile.get('total_views', 0)
            
            # Generate refined bio
            refined_bio = self.generate_refined_bio(username, refined_patterns)
            
            # Calculate improvement
            current_chars = self.analyze_bio_characteristics(current_bio)
            refined_chars = self.analyze_bio_characteristics(refined_bio)
            
            improvement_score = self.calculate_improvement_score(
                current_chars, 
                refined_chars, 
                refined_patterns
            )
            
            # Update profile
            self.data[username]['bio'] = refined_bio
            self.data[username]['last_updated'] = datetime.now().isoformat()
            
            optimization_results.append({
                'username': username,
                'old_length': len(current_bio),
                'new_length': len(refined_bio),
                'improvement_score': improvement_score,
                'current_views': current_views
            })
            
            print(f"  Optimized {username}: {len(current_bio)} -> {len(refined_bio)} chars (score: {improvement_score:.1f})")
        
        # Save updated data
        self.save_data()
        
        print()
        print("Step 5: Optimization complete!")
        print()
        
        # Step 6: Generate detailed report
        self.generate_iterative_report(optimization_results, top_performers, refined_patterns)
    
    def calculate_improvement_score(self, current: Dict, refined: Dict, patterns: Dict) -> float:
        """Calculate improvement score based on refined patterns"""
        score = 0.0
        
        # Length optimization
        optimal_min, optimal_max = patterns['optimal_length_range']
        if optimal_min <= refined['length'] <= optimal_max:
            score += 25
        elif current['length'] == 0 and refined['length'] > 0:
            score += 35
        
        # Keyword density matching
        keyword_density = patterns['keyword_density']
        
        if refined['availability_mentions'] >= keyword_density['availability']:
            score += 15
        if refined['experience_mentions'] >= keyword_density['experience']:
            score += 10
        if refined['benefit_mentions'] >= keyword_density['benefits']:
            score += 10
        if refined['urgency_mentions'] >= keyword_density['urgency']:
            score += 10
        if refined['specialty_mentions'] >= keyword_density['specialties']:
            score += 10
        
        # Keyword overlap
        successful_keywords = set(patterns['successful_keywords'])
        refined_keywords = set(refined['keywords'])
        overlap = len(successful_keywords & refined_keywords)
        
        if successful_keywords:
            score += (overlap / len(successful_keywords)) * 10
        
        return min(score, 100)
    
    def generate_iterative_report(self, results: List[Dict], top_performers: List[Dict], patterns: Dict):
        """Generate iterative optimization report"""
        print("="*80)
        print("ITERATIVE OPTIMIZATION REPORT")
        print("="*80)
        print()
        
        print("Top Performers Analysis:")
        for i, performer in enumerate(top_performers, 1):
            print(f"  {i}. {performer['username']}")
            print(f"     Views: {performer['profile'].get('total_views', 0)}")
            print(f"     Views/Day: {performer['views_per_day']}")
            print(f"     Bio length: {performer['characteristics']['length']} chars")
            print()
        
        print("Refined Patterns Applied:")
        print(f"  Sample size: {patterns['sample_count']} profiles")
        print(f"  Optimal length range: {patterns['optimal_length_range']}")
        print(f"  Keyword density targets: {patterns['keyword_density']}")
        print(f"  Successful keywords: {patterns['successful_keywords']}")
        print()
        
        print("Optimization Results:")
        print("-" * 80)
        
        total_improvement = 0
        for result in sorted(results, key=lambda x: x['improvement_score'], reverse=True):
            print(f"{result['username']}:")
            print(f"  Bio length: {result['old_length']} -> {result['new_length']}")
            print(f"  Improvement score: {result['improvement_score']:.1f}%")
            print(f"  Current views: {result['current_views']}")
            print()
            
            total_improvement += result['improvement_score']
        
        print("-" * 80)
        print(f"Total profiles optimized: {len(results)}")
        print(f"Average improvement score: {total_improvement/len(results):.1f}%")
        print()
        
        print("Next Iteration Steps:")
        print("1. Update profiles on RentMasseur with refined bios")
        print("2. Wait 7-14 days for view data to update")
        print("3. Re-enter new view counts")
        print("4. Re-run iterative optimization")
        print("5. Compare pattern evolution across iterations")
        print()
        
        print("Pattern Evolution:")
        print(f"Current iteration: {len(self.pattern_history)}")
        if len(self.pattern_history) > 1:
            print("Pattern changes detected across iterations")
            for i, history in enumerate(self.pattern_history[-2:], 1):
                print(f"  Iteration {i}: {history['timestamp']}")
                print(f"    Top performers: {history['top_performers']}")
        print()
        
        print("Data saved to: data/masseur_profiles.json")


def main():
    """Main entry point"""
    optimizer = IterativeBioOptimizer()
    optimizer.run_iterative_optimization()


if __name__ == "__main__":
    main()
