#!/usr/bin/env python3
"""
Bio Analysis using LLM
Analyzes masseur bios to extract insights, categorize services, and identify patterns
"""

import json
import re
from collections import Counter
from typing import List, Dict, Any

def load_bios(json_file: str) -> List[Dict[str, Any]]:
    """Load bios from JSON file"""
    with open(json_file, 'r') as f:
        return json.load(f)

def extract_services(bio: str) -> List[str]:
    """Extract massage services mentioned in bio"""
    services = [
        'swedish', 'deep tissue', 'sports', 'shiatsu', 'thai', 
        'reflexology', 'hot stone', 'aromatherapy', 'sensual', 
        'tantric', 'nuru', 'four hands', 'prostate', 'lingam',
        'yoni', 'couples', 'stretching', 'trigger point', 'lomilomi',
        'neuromuscular', 'myofascial', 'lymphatic', 'prenatal'
    ]
    
    bio_lower = bio.lower()
    found_services = []
    for service in services:
        if service in bio_lower:
            found_services.append(service)
    
    return found_services

def extract_certifications(bio: str) -> List[str]:
    """Extract certifications mentioned in bio"""
    cert_patterns = [
        r'licensed', r'certified', r'certified by', r'certification',
        r'degree in', r'certified massage therapist', r'CMT',
        r'LMT', r'RMT', r'NCTMB'
    ]
    
    found_certs = []
    for pattern in cert_patterns:
        if re.search(pattern, bio, re.IGNORECASE):
            found_certs.append(pattern)
    
    return found_certs

def extract_experience(bio: str) -> str:
    """Extract years of experience"""
    patterns = [
        r'(\d+)\s*years?\s*(?:of\s*)?(?:experience|massaging)',
        r'(\d+)\s*years?\s*(?:of\s*)?practice',
        r'experience\s*(?:of\s*)?(\d+)\s*years?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, bio, re.IGNORECASE)
        if match:
            return f"{match.group(1)} years"
    
    return "Not specified"

def analyze_bio(bio: str) -> Dict[str, Any]:
    """Analyze a single bio"""
    return {
        'services': extract_services(bio),
        'certifications': extract_certifications(bio),
        'experience': extract_experience(bio),
        'word_count': len(bio.split()),
        'char_count': len(bio)
    }

def generate_analysis_report(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate comprehensive analysis report"""
    all_services = []
    all_certs = []
    experience_levels = []
    bio_lengths = []
    
    for profile in profiles:
        bio = profile.get('bio', '')
        if bio:
            analysis = analyze_bio(bio)
            all_services.extend(analysis['services'])
            all_certs.extend(analysis['certifications'])
            experience_levels.append(analysis['experience'])
            bio_lengths.append(analysis['word_count'])
    
    service_counts = Counter(all_services)
    cert_counts = Counter(all_certs)
    exp_counts = Counter(experience_levels)
    
    return {
        'total_profiles': len(profiles),
        'profiles_with_bios': len([p for p in profiles if p.get('bio')]),
        'most_common_services': dict(service_counts.most_common(10)),
        'most_common_certifications': dict(cert_counts.most_common(5)),
        'experience_distribution': dict(exp_counts.most_common(5)),
        'bio_length_stats': {
            'min': min(bio_lengths) if bio_lengths else 0,
            'max': max(bio_lengths) if bio_lengths else 0,
            'avg': sum(bio_lengths) / len(bio_lengths) if bio_lengths else 0
        }
    }

def save_analysis_report(report: Dict[str, Any], output_file: str):
    """Save analysis report to JSON"""
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

def save_enriched_profiles(profiles: List[Dict[str, Any]], output_file: str):
    """Save profiles with analysis data"""
    enriched = []
    for profile in profiles:
        bio = profile.get('bio', '')
        if bio:
            analysis = analyze_bio(bio)
            enriched_profile = profile.copy()
            enriched_profile['analysis'] = analysis
            enriched.append(enriched_profile)
    
    with open(output_file, 'w') as f:
        json.dump(enriched, f, indent=2)

def main():
    input_file = "complete_profiles_with_bios_phones.json"
    output_report = "bio_analysis_report.json"
    output_enriched = "enriched_profiles.json"
    
    print("Loading profiles...")
    profiles = load_bios(input_file)
    
    print(f"Analyzing {len(profiles)} profiles...")
    report = generate_analysis_report(profiles)
    
    print("Saving analysis report...")
    save_analysis_report(report, output_report)
    
    print("Saving enriched profiles...")
    save_enriched_profiles(profiles, output_enriched)
    
    print("\n" + "="*60)
    print("BIO ANALYSIS COMPLETE")
    print("="*60)
    print(f"Total profiles: {report['total_profiles']}")
    print(f"Profiles with bios: {report['profiles_with_bios']}")
    print(f"\nTop services:")
    for service, count in list(report['most_common_services'].items())[:5]:
        print(f"  {service}: {count}")
    print(f"\nBio length stats:")
    print(f"  Min: {report['bio_length_stats']['min']} words")
    print(f"  Max: {report['bio_length_stats']['max']} words")
    print(f"  Avg: {report['bio_length_stats']['avg']:.1f} words")
    print(f"\nFiles saved:")
    print(f"  {output_report}")
    print(f"  {output_enriched}")

if __name__ == "__main__":
    main()
