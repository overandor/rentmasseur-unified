#!/usr/bin/env python3
"""
Comprehensive Bio Analysis
Advanced multi-dimensional analysis with detailed metrics
"""

import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple
import statistics

def load_profiles(json_file: str) -> List[Dict[str, Any]]:
    """Load profiles from JSON file"""
    with open(json_file, 'r') as f:
        return json.load(f)

def extract_all_services(bio: str) -> Dict[str, List[str]]:
    """Extract all services with categorization"""
    categories = {
        'traditional': ['swedish', 'deep tissue', 'sports', 'shiatsu', 'thai', 'reflexology'],
        'specialty': ['hot stone', 'aromatherapy', 'hydrotherapy', 'cryotherapy'],
        'sensual': ['sensual', 'tantric', 'nuru', 'lingam', 'yoni', 'erotic'],
        'therapeutic': ['trigger point', 'myofascial', 'neuromuscular', 'lymphatic'],
        'medical': ['prenatal', 'postnatal', 'geriatric', 'rehabilitation', 'injury'],
        'wellness': ['stretching', 'yoga', 'meditation', 'energy work', 'reiki'],
        'combined': ['four hands', 'couples', 'duo', 'tandem']
    }
    
    found = {cat: [] for cat in categories}
    bio_lower = bio.lower()
    
    for category, services in categories.items():
        for service in services:
            if service in bio_lower:
                found[category].append(service)
    
    return found

def analyze_bio_complexity(bio: str) -> Dict[str, Any]:
    """Analyze bio complexity metrics"""
    words = bio.split()
    sentences = re.split(r'[.!?]+', bio)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Average word length
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
    
    # Vocabulary richness (unique words / total words)
    unique_words = len(set(w.lower() for w in words))
    vocab_richness = unique_words / len(words) if words else 0
    
    # Paragraph structure
    paragraphs = [p.strip() for p in bio.split('\n') if p.strip()]
    
    # Emoji usage
    emoji_pattern = re.compile(r'[😀-🿿]|[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F1E0-\U0001F1FF]')
    emojis = emoji_pattern.findall(bio)
    
    return {
        'word_count': len(words),
        'sentence_count': len(sentences),
        'paragraph_count': len(paragraphs),
        'avg_sentence_length': len(words) / len(sentences) if sentences else 0,
        'avg_word_length': avg_word_len,
        'vocab_richness': vocab_richness,
        'emoji_count': len(emojis),
        'has_emojis': len(emojis) > 0,
        'has_paragraphs': len(paragraphs) > 1
    }

def extract_detailed_pricing(bio: str) -> Dict[str, Any]:
    """Extract detailed pricing information"""
    # Look for price patterns with time units
    time_patterns = [
        (r'(\d+)\s*min(?:ute)?s?\s*\$(\d+)', 'per_minute'),
        (r'(\d+)\s*hr(?:our)?s?\s*\$(\d+)', 'per_hour'),
        (r'\$(\d+)\s*/\s*(\d+)\s*min(?:ute)?s?', 'per_minute'),
        (r'\$(\d+)\s*/\s*(\d+)\s*hr(?:our)?s?', 'per_hour'),
        (r'(\d+)\s*min(?:ute)?s?\s*\$?(\d+)', 'per_minute'),
        (r'(\d+)\s*hr(?:our)?s?\s*\$?(\d+)', 'per_hour'),
    ]
    
    prices = []
    for pattern, unit in time_patterns:
        matches = re.findall(pattern, bio, re.IGNORECASE)
        for match in matches:
            if len(match) == 2:
                time, price = match
                prices.append({
                    'time': int(time),
                    'price': int(price),
                    'unit': unit,
                    'hourly_rate': int(price) * (60 / int(time)) if unit == 'per_minute' else int(price)
                })
    
    # Standalone prices
    standalone = re.findall(r'\$(\d+)', bio)
    standalone_prices = [int(p) for p in standalone if int(p) > 10 and int(p) < 1000]
    
    return {
        'has_pricing': len(prices) > 0 or len(standalone_prices) > 0,
        'time_based_pricing': prices,
        'standalone_prices': standalone_prices,
        'price_mentions': len(prices) + len(standalone_prices),
        'avg_hourly_rate': statistics.mean([p['hourly_rate'] for p in prices]) if prices else None,
        'min_price': min(standalone_prices) if standalone_prices else None,
        'max_price': max(standalone_prices) if standalone_prices else None
    }

def analyze_geographic_distribution(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze geographic distribution from phone numbers"""
    country_codes = {
        '+1': 'USA/Canada',
        '+44': 'UK',
        '+34': 'Spain',
        '+54': 'Argentina',
        '+61': 'Australia',
        '+51': 'Peru',
        '+32': 'Belgium',
        '+598': 'Uruguay',
        '+31': 'Netherlands',
        '+55': 'Brazil'
    }
    
    geo_dist = Counter()
    for profile in profiles:
        phone = profile.get('phone', '')
        if phone:
            for code, country in country_codes.items():
                if phone.startswith(code):
                    geo_dist[country] += 1
                    break
    
    return dict(geo_dist)

def analyze_certification_details(bio: str) -> Dict[str, Any]:
    """Extract detailed certification information"""
    cert_patterns = {
        'licensed': r'licensed\s+(?:massage\s+)?therapist|LMT',
        'certified': r'certified\s+(?:massage\s+)?therapist|CMT',
        'registered': r'registered\s+(?:massage\s+)?therapist|RMT',
        'university': r'(?:certified|graduated|degree)\s+(?:by|from|at)\s+([^.]+)',
        'school': r'(?:trained|studied|educated)\s+(?:at|by)\s+([^.]+)',
        'years': r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|practice)'
    }
    
    found = {}
    for cert_type, pattern in cert_patterns.items():
        matches = re.findall(pattern, bio, re.IGNORECASE)
        if matches:
            found[cert_type] = matches
    
    return found

def analyze_marketing_language(bio: str) -> Dict[str, Any]:
    """Analyze marketing language and persuasion techniques"""
    marketing_keywords = {
        'urgency': ['now', 'today', 'book now', 'available', 'limited'],
        'exclusivity': ['exclusive', 'vip', 'premium', 'luxury', 'elite'],
        'guarantee': ['guarantee', 'satisfaction', 'promise', 'ensure'],
        'social_proof': ['reviews', 'rated', 'recommended', 'featured'],
        'emotional': ['relax', 'peace', 'calm', 'bliss', 'euphoria', 'healing'],
        'professional': ['professional', 'expert', 'specialist', 'trained']
    }
    
    found = {}
    for category, keywords in marketing_keywords.items():
        count = sum(1 for kw in keywords if kw.lower() in bio.lower())
        if count > 0:
            found[category] = count
    
    return found

def analyze_session_details(bio: str) -> Dict[str, Any]:
    """Extract session-specific details"""
    session_keywords = {
        'duration': ['60 min', '90 min', '120 min', '30 min', '2 hour', '1 hour', '90 minute'],
        'environment': ['shower', 'music', 'candles', 'aromatherapy', 'heated table', 'towel'],
        'amenities': ['parking', 'towels', 'oils', 'lotions', 'refreshments'],
        'location_type': ['studio', 'home', 'office', 'spa', 'gym', 'hotel']
    }
    
    found = {}
    for category, keywords in session_keywords.items():
        matches = [kw for kw in keywords if kw.lower() in bio.lower()]
        if matches:
            found[category] = matches
    
    return found

def calculate_profile_completeness(profile: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate profile completeness score"""
    completeness_factors = {
        'has_bio': bool(profile.get('bio')),
        'has_phone': bool(profile.get('phone')),
        'bio_length': analysis['complexity']['word_count'] > 50,
        'has_services': len(analysis['services']['traditional']) + len(analysis['services']['sensual']) > 0,
        'has_pricing': analysis['pricing']['has_pricing'],
        'has_certification': len(analysis['certifications']) > 0,
        'has_availability': len(analysis['session_details']) > 0,
        'structured_bio': analysis['complexity']['paragraph_count'] > 1
    }
    
    score = sum(completeness_factors.values()) / len(completeness_factors) * 100
    
    return {
        'completeness_score': round(score, 1),
        'factors': completeness_factors
    }

def comprehensive_analyze_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Perform comprehensive analysis on a single profile"""
    bio = profile.get('bio', '')
    
    analysis = {
        'username': profile.get('username'),
        'phone': profile.get('phone'),
        'services': extract_all_services(bio),
        'complexity': analyze_bio_complexity(bio),
        'pricing': extract_detailed_pricing(bio),
        'certifications': analyze_certification_details(bio),
        'marketing': analyze_marketing_language(bio),
        'session_details': analyze_session_details(bio),
        'completeness': {}
    }
    
    analysis['completeness'] = calculate_profile_completeness(profile, analysis)
    
    return analysis

def generate_comprehensive_report(analyzed_profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate comprehensive aggregate report"""
    # Service category distribution
    service_categories = defaultdict(int)
    for profile in analyzed_profiles:
        for category, services in profile['services'].items():
            if services:
                service_categories[category] += 1
    
    # Complexity statistics
    word_counts = [p['complexity']['word_count'] for p in analyzed_profiles]
    sentence_counts = [p['complexity']['sentence_count'] for p in analyzed_profiles]
    vocab_richness = [p['complexity']['vocab_richness'] for p in analyzed_profiles]
    
    # Pricing statistics
    profiles_with_pricing = [p for p in analyzed_profiles if p['pricing']['has_pricing']]
    hourly_rates = [p['pricing']['avg_hourly_rate'] for p in profiles_with_pricing if p['pricing']['avg_hourly_rate']]
    
    # Completeness distribution
    completeness_scores = [p['completeness']['completeness_score'] for p in analyzed_profiles]
    
    # Marketing language analysis
    marketing_usage = defaultdict(int)
    for profile in analyzed_profiles:
        for category in profile['marketing'].keys():
            marketing_usage[category] += 1
    
    # Certification analysis
    profiles_with_certs = [p for p in analyzed_profiles if p['certifications']]
    
    # Session details
    session_features = defaultdict(int)
    for profile in analyzed_profiles:
        for feature in profile['session_details'].keys():
            session_features[feature] += 1
    
    return {
        'total_profiles': len(analyzed_profiles),
        'service_category_distribution': dict(service_categories),
        'bio_complexity_stats': {
            'avg_word_count': statistics.mean(word_counts) if word_counts else 0,
            'median_word_count': statistics.median(word_counts) if word_counts else 0,
            'min_word_count': min(word_counts) if word_counts else 0,
            'max_word_count': max(word_counts) if word_counts else 0,
            'avg_sentence_count': statistics.mean(sentence_counts) if sentence_counts else 0,
            'avg_vocab_richness': statistics.mean(vocab_richness) if vocab_richness else 0
        },
        'pricing_analysis': {
            'profiles_with_pricing': len(profiles_with_pricing),
            'percentage_with_pricing': len(profiles_with_pricing) / len(analyzed_profiles) * 100,
            'avg_hourly_rate': statistics.mean(hourly_rates) if hourly_rates else None,
            'median_hourly_rate': statistics.median(hourly_rates) if hourly_rates else None,
            'rate_range': (min(hourly_rates), max(hourly_rates)) if hourly_rates else None
        },
        'completeness_distribution': {
            'avg_completeness': statistics.mean(completeness_scores),
            'median_completeness': statistics.median(completeness_scores),
            'high_quality_profiles': len([s for s in completeness_scores if s >= 80]),
            'medium_quality_profiles': len([s for s in completeness_scores if 50 <= s < 80]),
            'low_quality_profiles': len([s for s in completeness_scores if s < 50])
        },
        'marketing_language_usage': dict(marketing_usage),
        'certification_stats': {
            'profiles_with_certifications': len(profiles_with_certs),
            'certification_types': len(set().union(*[p['certifications'].keys() for p in profiles_with_certs]))
        },
        'session_features': dict(session_features),
        'top_profiles_by_completeness': sorted(
            analyzed_profiles, 
            key=lambda x: x['completeness']['completeness_score'], 
            reverse=True
        )[:10]
    }

def main():
    input_file = "complete_profiles_with_bios_phones.json"
    output_report = "comprehensive_analysis_report.json"
    output_profiles = "comprehensive_analyzed_profiles.json"
    
    print("Loading profiles...")
    profiles = load_profiles(input_file)
    
    print(f"Performing comprehensive analysis on {len(profiles)} profiles...")
    analyzed = [comprehensive_analyze_profile(p) for p in profiles]
    
    print("Generating comprehensive report...")
    report = generate_comprehensive_report(analyzed)
    
    # Save results
    with open(output_report, 'w') as f:
        json.dump(report, f, indent=2)
    
    with open(output_profiles, 'w') as f:
        json.dump(analyzed, f, indent=2)
    
    # Print detailed summary
    print("\n" + "="*80)
    print("COMPREHENSIVE BIO ANALYSIS REPORT")
    print("="*80)
    
    print(f"\nTotal profiles analyzed: {report['total_profiles']}")
    
    print(f"\n--- Service Category Distribution ---")
    for category, count in report['service_category_distribution'].items():
        pct = count / report['total_profiles'] * 100
        print(f"  {category}: {count} ({pct:.1f}%)")
    
    print(f"\n--- Bio Complexity Statistics ---")
    stats = report['bio_complexity_stats']
    print(f"  Average word count: {stats['avg_word_count']:.1f}")
    print(f"  Median word count: {stats['median_word_count']:.1f}")
    print(f"  Word count range: {stats['min_word_count']} - {stats['max_word_count']}")
    print(f"  Average sentence count: {stats['avg_sentence_count']:.1f}")
    print(f"  Average vocabulary richness: {stats['avg_vocab_richness']:.3f}")
    
    print(f"\n--- Pricing Analysis ---")
    pricing = report['pricing_analysis']
    print(f"  Profiles with pricing: {pricing['profiles_with_pricing']} ({pricing['percentage_with_pricing']:.1f}%)")
    if pricing['avg_hourly_rate']:
        print(f"  Average hourly rate: ${pricing['avg_hourly_rate']:.2f}")
        print(f"  Median hourly rate: ${pricing['median_hourly_rate']:.2f}")
        print(f"  Rate range: ${pricing['rate_range'][0]:.0f} - ${pricing['rate_range'][1]:.0f}")
    
    print(f"\n--- Profile Completeness ---")
    completeness = report['completeness_distribution']
    print(f"  Average completeness score: {completeness['avg_completeness']:.1f}/100")
    print(f"  Median completeness score: {completeness['median_completeness']:.1f}/100")
    print(f"  High quality profiles (80%+): {completeness['high_quality_profiles']}")
    print(f"  Medium quality profiles (50-79%): {completeness['medium_quality_profiles']}")
    print(f"  Low quality profiles (<50%): {completeness['low_quality_profiles']}")
    
    print(f"\n--- Marketing Language Usage ---")
    for category, count in report['marketing_language_usage'].items():
        print(f"  {category}: {count} profiles")
    
    print(f"\n--- Certification Statistics ---")
    certs = report['certification_stats']
    print(f"  Profiles with certifications: {certs['profiles_with_certifications']}")
    print(f"  Unique certification types mentioned: {certs['certification_types']}")
    
    print(f"\n--- Session Features ---")
    for feature, count in report['session_features'].items():
        print(f"  {feature}: {count} profiles")
    
    print(f"\n--- Top 10 Profiles by Completeness ---")
    for idx, profile in enumerate(report['top_profiles_by_completeness'], 1):
        print(f"  {idx}. {profile['username']} - Score: {profile['completeness']['completeness_score']}/100")
        print(f"     Word count: {profile['complexity']['word_count']}")
        print(f"     Services: {sum(len(s) for s in profile['services'].values())}")
        print(f"     Has pricing: {profile['pricing']['has_pricing']}")
        print(f"     Has certifications: {len(profile['certifications']) > 0}")
    
    print(f"\nFiles saved:")
    print(f"  {output_report}")
    print(f"  {output_profiles}")

if __name__ == "__main__":
    main()
