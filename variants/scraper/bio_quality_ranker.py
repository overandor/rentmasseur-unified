#!/usr/bin/env python3
"""
Bio Quality Ranking
Ranks masseur bios by quality using multi-factor scoring
"""

import json
from typing import List, Dict, Any

def load_profiles(json_file: str) -> List[Dict[str, Any]]:
    """Load profiles from JSON file"""
    with open(json_file, 'r') as f:
        return json.load(f)

def score_bio_quality(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Score a bio based on multiple quality factors"""
    bio = profile.get('bio', '')
    phone = profile.get('phone', '')
    
    score = 0
    factors = {}
    
    # 1. Bio length (longer = more detailed)
    word_count = len(bio.split())
    if word_count > 200:
        score += 20
        factors['bio_length'] = 20
    elif word_count > 100:
        score += 15
        factors['bio_length'] = 15
    elif word_count > 50:
        score += 10
        factors['bio_length'] = 10
    else:
        factors['bio_length'] = 0
    
    # 2. Phone number availability
    if phone:
        score += 15
        factors['has_phone'] = 15
    else:
        factors['has_phone'] = 0
    
    # 3. Professional keywords
    professional_keywords = [
        'licensed', 'certified', 'certification', 'degree',
        'therapist', 'professional', 'experience', 'trained',
        'specialist', 'expert', 'qualified'
    ]
    prof_count = sum(1 for kw in professional_keywords if kw.lower() in bio.lower())
    factors['professional_keywords'] = min(prof_count * 3, 15)
    score += factors['professional_keywords']
    
    # 4. Service variety
    services = [
        'swedish', 'deep tissue', 'sports', 'shiatsu', 'thai',
        'reflexology', 'hot stone', 'aromatherapy', 'sensual',
        'tantric', 'nuru', 'stretching', 'trigger point'
    ]
    service_count = sum(1 for svc in services if svc.lower() in bio.lower())
    factors['service_variety'] = min(service_count * 2, 15)
    score += factors['service_variety']
    
    # 5. Personal touch (mentions of creating experience, atmosphere, etc.)
    personal_keywords = [
        'create', 'experience', 'atmosphere', 'space', 'environment',
        'comfortable', 'safe', 'welcoming', 'relaxing', 'nurturing'
    ]
    personal_count = sum(1 for kw in personal_keywords if kw.lower() in bio.lower())
    factors['personal_touch'] = min(personal_count * 2, 10)
    score += factors['personal_touch']
    
    # 6. Specific details (location, hours, payment methods)
    detail_keywords = [
        'location', 'studio', 'incall', 'outcall', 'available',
        'hours', 'booking', 'appointment', 'payment', 'cash',
        'credit', 'zelle', 'venmo'
    ]
    detail_count = sum(1 for kw in detail_keywords if kw.lower() in bio.lower())
    factors['specific_details'] = min(detail_count * 2, 10)
    score += factors['specific_details']
    
    # 7. Grammar and structure (basic check for sentences)
    sentences = bio.count('.') + bio.count('!') + bio.count('?')
    if sentences > 5:
        factors['structure'] = 15
        score += 15
    elif sentences > 2:
        factors['structure'] = 10
        score += 10
    else:
        factors['structure'] = 0
    
    return {
        'total_score': score,
        'factors': factors,
        'word_count': word_count
    }

def rank_bios(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank bios by quality score"""
    scored_profiles = []
    
    for profile in profiles:
        scoring = score_bio_quality(profile)
        scored_profile = profile.copy()
        scored_profile['quality_score'] = scoring['total_score']
        scored_profile['score_breakdown'] = scoring['factors']
        scored_profile['word_count'] = scoring['word_count']
        scored_profiles.append(scored_profile)
    
    # Sort by quality score descending
    ranked = sorted(scored_profiles, key=lambda x: x['quality_score'], reverse=True)
    return ranked

def generate_ranking_report(ranked_profiles: List[Dict[str, Any]], output_file: str = "best_bios_report.json"):
    """Generate ranking report"""
    top_20 = ranked_profiles[:20]
    
    report = {
        'total_analyzed': len(ranked_profiles),
        'top_20_bios': top_20,
        'summary': {
            'highest_score': top_20[0]['quality_score'] if top_20 else 0,
            'lowest_score': top_20[-1]['quality_score'] if top_20 else 0,
            'average_score': sum(p['quality_score'] for p in top_20) / len(top_20) if top_20 else 0
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report

def main():
    input_file = "complete_profiles_with_bios_phones.json"
    output_file = "best_bios_report.json"
    
    print("Loading profiles...")
    profiles = load_profiles(input_file)
    
    print(f"Scoring {len(profiles)} bios...")
    ranked = rank_bios(profiles)
    
    print("Generating ranking report...")
    report = generate_ranking_report(ranked, output_file)
    
    print("\n" + "="*60)
    print("TOP 10 BEST BIOS")
    print("="*60)
    
    for idx, profile in enumerate(ranked[:10], 1):
        print(f"\n{idx}. {profile['username']} - Score: {profile['quality_score']}/100")
        print(f"   Phone: {profile.get('phone', 'N/A')}")
        print(f"   Bio length: {profile['word_count']} words")
        print(f"   Score breakdown:")
        for factor, value in profile['score_breakdown'].items():
            print(f"     - {factor}: {value}")
        print(f"   Bio preview: {profile.get('bio', '')[:150]}...")
    
    print(f"\nReport saved to: {output_file}")
    print(f"Total profiles analyzed: {report['total_analyzed']}")
    print(f"Highest score: {report['summary']['highest_score']}")
    print(f"Average score (top 20): {report['summary']['average_score']:.1f}")

if __name__ == "__main__":
    main()
