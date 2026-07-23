#!/usr/bin/env python3
"""
Deep Bio Analysis
Comprehensive multi-factor analysis of masseur bios
"""

import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple

def load_profiles(json_file: str) -> List[Dict[str, Any]]:
    """Load profiles from JSON file"""
    with open(json_file, 'r') as f:
        return json.load(f)

def extract_pricing(bio: str) -> Dict[str, Any]:
    """Extract pricing information"""
    patterns = [
        r'\$(\d+)',  # USD
        r'£(\d+)',   # GBP
        r'€(\d+)',   # EUR
        r'(\d+)\s*(?:dollars?|usd)',  # Text USD
        r'(\d+)\s*(?:pounds?|gbp)',   # Text GBP
    ]
    
    prices = []
    for pattern in patterns:
        matches = re.findall(pattern, bio, re.IGNORECASE)
        prices.extend([int(m) for m in matches])
    
    return {
        'has_pricing': len(prices) > 0,
        'price_mentions': prices,
        'price_range': (min(prices), max(prices)) if prices else None,
        'avg_price': sum(prices) / len(prices) if prices else None
    }

def extract_availability(bio: str) -> Dict[str, Any]:
    """Extract availability information"""
    availability_keywords = {
        '24/7': 'always_available',
        '24 hours': 'always_available',
        'weekends': 'weekends',
        'weekday': 'weekdays',
        'evening': 'evenings',
        'morning': 'mornings',
        'night': 'nights',
        'available': 'general_availability',
        'booking': 'booking_required',
        'appointment': 'appointment_required'
    }
    
    found = {}
    for keyword, category in availability_keywords.items():
        if keyword.lower() in bio.lower():
            found[category] = found.get(category, 0) + 1
    
    return {
        'availability_types': list(found.keys()),
        'has_24_7': 'always_available' in found,
        'has_booking_info': 'booking_required' in found or 'appointment_required' in found
    }

def extract_business_model(bio: str) -> Dict[str, Any]:
    """Extract business model (incall/outcall)"""
    incall_keywords = ['incall', 'studio', 'my place', 'my location', 'home studio']
    outcall_keywords = ['outcall', 'mobile', 'your place', 'your location', 'hotel', 'home visit']
    
    incall_count = sum(1 for kw in incall_keywords if kw.lower() in bio.lower())
    outcall_count = sum(1 for kw in outcall_keywords if kw.lower() in bio.lower())
    
    model = 'both' if incall_count > 0 and outcall_count > 0 else \
            'incall' if incall_count > 0 else \
            'outcall' if outcall_count > 0 else 'unspecified'
    
    return {
        'business_model': model,
        'incall': incall_count > 0,
        'outcall': outcall_count > 0,
        'mobile_service': outcall_count > 0
    }

def extract_payment_methods(bio: str) -> List[str]:
    """Extract payment methods"""
    payment_keywords = {
        'cash': 'cash',
        'credit': 'credit_card',
        'card': 'credit_card',
        'zelle': 'zelle',
        'venmo': 'venmo',
        'paypal': 'paypal',
        'bank transfer': 'bank_transfer',
        'crypto': 'crypto',
        'bitcoin': 'crypto'
    }
    
    methods = []
    for keyword, method in payment_keywords.items():
        if keyword.lower() in bio.lower():
            methods.append(method)
    
    return list(set(methods))

def extract_languages(bio: str) -> List[str]:
    """Extract languages mentioned"""
    languages = [
        'english', 'spanish', 'french', 'german', 'italian', 'portuguese',
        'russian', 'chinese', 'japanese', 'korean', 'arabic', 'hindi',
        'dutch', 'swedish', 'norwegian', 'danish', 'finnish', 'polish',
        'greek', 'turkish', 'hebrew', 'thai', 'vietnamese'
    ]
    
    found = []
    for lang in languages:
        if lang.lower() in bio.lower():
            found.append(lang)
    
    return list(set(found))

def analyze_tone(bio: str) -> Dict[str, Any]:
    """Analyze tone of the bio"""
    professional_words = ['professional', 'therapist', 'certified', 'licensed', 'trained', 'expert']
    casual_words = ['fun', 'chill', 'relaxed', 'easy-going', 'friendly', 'buddy']
    sensual_words = ['sensual', 'erotic', 'intimate', 'pleasure', 'desire']
    medical_words = ['therapy', 'therapeutic', 'treatment', 'recovery', 'rehabilitation', 'pain']
    
    prof_count = sum(1 for w in professional_words if w.lower() in bio.lower())
    casual_count = sum(1 for w in casual_words if w.lower() in bio.lower())
    sensual_count = sum(1 for w in sensual_words if w.lower() in bio.lower())
    medical_count = sum(1 for w in medical_words if w.lower() in bio.lower())
    
    dominant = max([('professional', prof_count), ('casual', casual_count), 
                   ('sensual', sensual_count), ('medical', medical_count)], 
                  key=lambda x: x[1])
    
    return {
        'tone_scores': {
            'professional': prof_count,
            'casual': casual_count,
            'sensual': sensual_count,
            'medical': medical_count
        },
        'dominant_tone': dominant[0] if dominant[1] > 0 else 'neutral'
    }

def extract_specializations(bio: str) -> List[str]:
    """Extract specializations"""
    specializations = [
        'sports massage', 'injury', 'rehabilitation', 'athletes',
        'stress relief', 'relaxation', 'wellness',
        'tantric', 'sensual', 'erotic',
        'deep tissue', 'trigger point', 'myofascial',
        'pregnancy', 'prenatal', 'postnatal',
        'elderly', 'geriatric', 'seniors',
        'couples', 'partners', 'duo',
        'corporate', 'office', 'chair massage'
    ]
    
    found = []
    for spec in specializations:
        if spec.lower() in bio.lower():
            found.append(spec)
    
    return list(set(found))

def deep_analyze_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Perform deep analysis on a single profile"""
    bio = profile.get('bio', '')
    
    return {
        'username': profile.get('username'),
        'pricing': extract_pricing(bio),
        'availability': extract_availability(bio),
        'business_model': extract_business_model(bio),
        'payment_methods': extract_payment_methods(bio),
        'languages': extract_languages(bio),
        'tone': analyze_tone(bio),
        'specializations': extract_specializations(bio),
        'has_phone': bool(profile.get('phone')),
        'phone_country': profile.get('phone', '')[:3] if profile.get('phone') else None
    }

def generate_aggregate_analysis(analyzed_profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate aggregate analysis across all profiles"""
    business_models = Counter([p['business_model']['business_model'] for p in analyzed_profiles])
    payment_methods = Counter([m for p in analyzed_profiles for m in p['payment_methods']])
    languages = Counter([l for p in analyzed_profiles for l in p['languages']])
    tones = Counter([p['tone']['dominant_tone'] for p in analyzed_profiles])
    specializations = Counter([s for p in analyzed_profiles for s in p['specializations']])
    
    pricing_profiles = [p for p in analyzed_profiles if p['pricing']['has_pricing']]
    avg_prices = [p['pricing']['avg_price'] for p in pricing_profiles if p['pricing']['avg_price']]
    
    return {
        'total_profiles': len(analyzed_profiles),
        'business_models': dict(business_models.most_common()),
        'payment_methods': dict(payment_methods.most_common(10)),
        'languages': dict(languages.most_common(10)),
        'tone_distribution': dict(tones.most_common()),
        'top_specializations': dict(specializations.most_common(10)),
        'pricing_stats': {
            'profiles_with_pricing': len(pricing_profiles),
            'avg_price': sum(avg_prices) / len(avg_prices) if avg_prices else None,
            'price_range': (min(avg_prices), max(avg_prices)) if avg_prices else None
        },
        'phone_availability': {
            'with_phone': sum(1 for p in analyzed_profiles if p['has_phone']),
            'without_phone': sum(1 for p in analyzed_profiles if not p['has_phone'])
        },
        'availability_stats': {
            '24_7_available': sum(1 for p in analyzed_profiles if p['availability']['has_24_7']),
            'booking_required': sum(1 for p in analyzed_profiles if p['availability']['has_booking_info'])
        }
    }

def main():
    input_file = "complete_profiles_with_bios_phones.json"
    output_analysis = "deep_analysis_report.json"
    output_profiles = "deep_analyzed_profiles.json"
    
    print("Loading profiles...")
    profiles = load_profiles(input_file)
    
    print(f"Performing deep analysis on {len(profiles)} profiles...")
    analyzed = [deep_analyze_profile(p) for p in profiles]
    
    print("Generating aggregate analysis...")
    aggregate = generate_aggregate_analysis(analyzed)
    
    # Save results
    with open(output_analysis, 'w') as f:
        json.dump(aggregate, f, indent=2)
    
    with open(output_profiles, 'w') as f:
        json.dump(analyzed, f, indent=2)
    
    # Print summary
    print("\n" + "="*70)
    print("DEEP BIO ANALYSIS REPORT")
    print("="*70)
    
    print(f"\nTotal profiles analyzed: {aggregate['total_profiles']}")
    
    print(f"\nBusiness Models:")
    for model, count in list(aggregate['business_models'].items())[:5]:
        print(f"  {model}: {count} ({count/aggregate['total_profiles']*100:.1f}%)")
    
    print(f"\nPayment Methods:")
    for method, count in list(aggregate['payment_methods'].items())[:5]:
        print(f"  {method}: {count}")
    
    print(f"\nLanguages Spoken:")
    for lang, count in list(aggregate['languages'].items())[:5]:
        print(f"  {lang}: {count}")
    
    print(f"\nTone Distribution:")
    for tone, count in aggregate['tone_distribution'].items():
        print(f"  {tone}: {count} ({count/aggregate['total_profiles']*100:.1f}%)")
    
    print(f"\nTop Specializations:")
    for spec, count in list(aggregate['top_specializations'].items())[:5]:
        print(f"  {spec}: {count}")
    
    print(f"\nPricing:")
    print(f"  Profiles with pricing: {aggregate['pricing_stats']['profiles_with_pricing']}")
    if aggregate['pricing_stats']['avg_price']:
        print(f"  Average price: ${aggregate['pricing_stats']['avg_price']:.2f}")
        print(f"  Price range: ${aggregate['pricing_stats']['price_range'][0]:.0f} - ${aggregate['pricing_stats']['price_range'][1]:.0f}")
    
    print(f"\nPhone Availability:")
    print(f"  With phone: {aggregate['phone_availability']['with_phone']} ({aggregate['phone_availability']['with_phone']/aggregate['total_profiles']*100:.1f}%)")
    print(f"  Without phone: {aggregate['phone_availability']['without_phone']} ({aggregate['phone_availability']['without_phone']/aggregate['total_profiles']*100:.1f}%)")
    
    print(f"\nAvailability:")
    print(f"  24/7 available: {aggregate['availability_stats']['24_7_available']}")
    print(f"  Booking required: {aggregate['availability_stats']['booking_required']}")
    
    print(f"\nFiles saved:")
    print(f"  {output_analysis}")
    print(f"  {output_profiles}")

if __name__ == "__main__":
    main()
