'use client';

import { useState, useEffect, useRef } from 'react';

const SPECIALTIES = [
  { id: 'swedish', name: 'Swedish', icon: '🌿' },
  { id: 'deep', name: 'Deep Tissue', icon: '💪' },
  { id: 'sports', name: 'Sports', icon: '⚽' },
  { id: 'thai', name: 'Thai', icon: '🧘' },
  { id: 'hotstone', name: 'Hot Stone', icon: '🔥' },
  { id: 'aromatherapy', name: 'Aromatherapy', icon: '🌸' },
  { id: 'reflexology', name: 'Reflexology', icon: '🦶' },
  { id: 'shiatsu', name: 'Shiatsu', icon: '👐' },
];

const MASSEURS = [
  { id: 1, name: 'Marcus', age: 32, specialties: ['deep', 'sports'], rating: 4.9, reviews: 127, rate: 85, distance: '1.2 mi', verified: true, bio: 'Certified sports massage therapist with 8 years experience. Former NFL recovery specialist.', avatar: 'M' },
  { id: 2, name: 'Elena', age: 29, specialties: ['swedish', 'aromatherapy'], rating: 5.0, reviews: 203, rate: 95, distance: '2.5 mi', verified: true, bio: 'Luxury spa-trained masseuse specializing in relaxation and stress relief.', avatar: 'E' },
  { id: 3, name: 'Kenji', age: 41, specialties: ['shiatsu', 'thai'], rating: 4.8, reviews: 89, rate: 110, distance: '3.1 mi', verified: true, bio: 'Tokyo-trained shiatsu master. 15 years of traditional Japanese techniques.', avatar: 'K' },
  { id: 4, name: 'Sofia', age: 35, specialties: ['hotstone', 'swedish'], rating: 4.9, reviews: 156, rate: 90, distance: '0.8 mi', verified: true, bio: 'Hot stone specialist with wellness center background. Holistic approach.', avatar: 'S' },
  { id: 5, name: 'James', age: 38, specialties: ['deep', 'reflexology'], rating: 4.7, reviews: 72, rate: 75, distance: '4.2 mi', verified: false, bio: 'Licensed massage therapist focusing on deep tissue and foot reflexology.', avatar: 'J' },
  { id: 6, name: 'Aisha', age: 27, specialties: ['thai', 'sports'], rating: 4.9, reviews: 98, rate: 80, distance: '1.9 mi', verified: true, bio: 'Thailand-trained Thai massage practitioner. Competitive athlete recovery focus.', avatar: 'A' },
];

export default function Home() {
  const [selectedSpec, setSelectedSpec] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredMasseurs, setFilteredMasseurs] = useState(MASSEURS);
  const [selectedMasseur, setSelectedMasseur] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    let result = MASSEURS;
    if (selectedSpec) {
      result = result.filter(m => m.specialties.includes(selectedSpec));
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(m => m.name.toLowerCase().includes(q) || m.bio.toLowerCase().includes(q));
    }
    setFilteredMasseurs(result);
  }, [selectedSpec, searchQuery]);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Header */}
      <header style={{
        background: 'rgba(10,10,15,0.85)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border)', padding: '14px 24px', display: 'flex',
        alignItems: 'center', gap: '16px', position: 'sticky', top: 0, zIndex: 50,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '50%',
            background: 'var(--accent-dim)', border: '1px solid var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px',
          }}>💆</div>
          <div>
            <div style={{ fontSize: '16px', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>RentMasseur</div>
            <div style={{ fontSize: '9px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px' }}>Find your masseur</div>
          </div>
        </div>
        <div style={{ flex: 1, maxWidth: '400px', position: 'relative' }}>
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search by name or specialty..."
            style={{
              width: '100%', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', padding: '9px 14px 9px 36px', color: 'var(--text)',
              fontSize: '13px', outline: 'none', transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent)'}
            onBlur={e => e.target.style.borderColor = 'var(--border)'}
          />
          <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', fontSize: '14px', opacity: 0.4 }}>🔍</span>
        </div>
        <button style={{
          background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
          padding: '8px 18px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
        }}>Sign In</button>
      </header>

      {/* Hero */}
      <section style={{
        padding: '60px 24px 40px', textAlign: 'center', maxWidth: '800px', margin: '0 auto',
        animation: 'fadeIn 0.6s ease',
      }}>
        <h1 style={{ fontSize: '36px', fontWeight: 800, color: '#fff', marginBottom: '12px', letterSpacing: '-1px' }}>
          Professional Massage, <span style={{ color: 'var(--accent)' }}>On Demand</span>
        </h1>
        <p style={{ fontSize: '15px', color: 'var(--text-dim)', maxWidth: '500px', margin: '0 auto 32px', lineHeight: 1.6 }}>
          Verified, reviewed masseurs in your area. Book in seconds, relax in minutes.
        </p>

        {/* Specialty filter pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center', marginBottom: '40px' }}>
          {SPECIALTIES.map(spec => (
            <button
              key={spec.id}
              onClick={() => setSelectedSpec(selectedSpec === spec.id ? null : spec.id)}
              style={{
                background: selectedSpec === spec.id ? 'var(--accent)' : 'var(--bg-elevated)',
                color: selectedSpec === spec.id ? '#fff' : 'var(--text-dim)',
                border: selectedSpec === spec.id ? 'none' : '1px solid var(--border)',
                borderRadius: '24px', padding: '8px 16px', fontSize: '12px', fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: '6px',
              }}
            >
              <span>{spec.icon}</span> {spec.name}
            </button>
          ))}
        </div>
      </section>

      {/* Masseur grid */}
      <section style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 24px 60px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#fff' }}>
            {loading ? 'Loading...' : `${filteredMasseurs.length} masseurs available`}
          </h2>
          <span style={{ fontSize: '11px', color: 'var(--text-faint)' }}>Sorted by distance</span>
        </div>

        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '20px' }}>
                <div style={{ display: 'flex', gap: '14px', marginBottom: '16px' }}>
                  <div className="rm-skeleton" style={{ width: '56px', height: '56px', borderRadius: '50%' }} />
                  <div style={{ flex: 1 }}>
                    <div className="rm-skeleton" style={{ width: '60%', height: '14px', marginBottom: '8px' }} />
                    <div className="rm-skeleton" style={{ width: '40%', height: '10px' }} />
                  </div>
                </div>
                <div className="rm-skeleton" style={{ width: '100%', height: '32px', marginBottom: '12px' }} />
                <div style={{ display: 'flex', gap: '8px' }}>
                  <div className="rm-skeleton" style={{ width: '60px', height: '24px', borderRadius: '20px' }} />
                  <div className="rm-skeleton" style={{ width: '60px', height: '24px', borderRadius: '20px' }} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {filteredMasseurs.map((m, i) => (
              <MasseurCard key={m.id} masseur={m} onClick={() => setSelectedMasseur(m)} index={i} />
            ))}
          </div>
        )}

        {!loading && filteredMasseurs.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-faint)' }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>🔍</div>
            <div style={{ fontSize: '14px' }}>No masseurs match your filters. Try a different specialty.</div>
          </div>
        )}
      </section>

      {/* Detail modal */}
      {selectedMasseur && (
        <MasseurModal masseur={selectedMasseur} onClose={() => setSelectedMasseur(null)} />
      )}
    </div>
  );
}

function MasseurCard({ masseur, onClick, index }) {
  return (
    <div
      className="rm-fade-in-up"
      onClick={onClick}
      style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
        padding: '20px', cursor: 'pointer', transition: 'all 0.2s ease',
        animationDelay: `${index * 0.05}s`,
      }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-hover)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      <div style={{ display: 'flex', gap: '14px', marginBottom: '14px' }}>
        <div style={{
          width: '56px', height: '56px', borderRadius: '50%', flexShrink: 0,
          background: 'var(--accent-dim)', border: '1px solid var(--accent)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '22px', fontWeight: 700, color: 'var(--accent)',
        }}>{masseur.avatar}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
            <span style={{ fontSize: '15px', fontWeight: 700, color: '#fff' }}>{masseur.name}</span>
            {masseur.verified && (
              <span style={{ fontSize: '9px', color: 'var(--green)', background: 'rgba(0,184,148,0.1)', padding: '1px 6px', borderRadius: '10px', fontWeight: 600 }}>✓ Verified</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-dim)' }}>
            <span style={{ color: 'var(--gold)' }}>★ {masseur.rating}</span>
            <span>·</span>
            <span>{masseur.reviews} reviews</span>
            <span>·</span>
            <span>{masseur.distance}</span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>${masseur.rate}</div>
          <div style={{ fontSize: '9px', color: 'var(--text-faint)' }}>per hour</div>
        </div>
      </div>
      <p style={{ fontSize: '12px', color: 'var(--text-dim)', lineHeight: 1.5, marginBottom: '14px' }}>{masseur.bio}</p>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {masseur.specialties.map(specId => {
          const spec = SPECIALTIES.find(s => s.id === specId);
          return spec ? (
            <span key={specId} style={{
              fontSize: '10px', color: 'var(--text-dim)', background: 'var(--bg-elevated)',
              padding: '3px 10px', borderRadius: '20px', border: '1px solid var(--border)',
            }}>{spec.icon} {spec.name}</span>
          ) : null;
        })}
      </div>
    </div>
  );
}

function MasseurModal({ masseur, onClose }) {
  const [bookingDate, setBookingDate] = useState('');
  const [bookingTime, setBookingTime] = useState('');
  const [booked, setBooked] = useState(false);

  return (
    <div className="rm-fade-in" style={{
      position: 'fixed', inset: 0, background: 'rgba(8,8,15,0.85)',
      backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '20px',
    }} onClick={onClose}>
      <div className="rm-scale-in" style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
        maxWidth: '480px', width: '100%', padding: '32px', position: 'relative',
      }} onClick={e => e.stopPropagation()}>
        <button onClick={onClose} style={{
          position: 'absolute', top: '16px', right: '16px', background: 'transparent',
          border: 'none', color: 'var(--text-faint)', fontSize: '18px', cursor: 'pointer',
        }}>✕</button>

        <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
          <div style={{
            width: '72px', height: '72px', borderRadius: '50%',
            background: 'var(--accent-dim)', border: '2px solid var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '28px', fontWeight: 700, color: 'var(--accent)',
          }}>{masseur.avatar}</div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{ fontSize: '20px', fontWeight: 800, color: '#fff' }}>{masseur.name}</span>
              {masseur.verified && (
                <span style={{ fontSize: '10px', color: 'var(--green)', background: 'rgba(0,184,148,0.1)', padding: '2px 8px', borderRadius: '10px', fontWeight: 600 }}>✓ Verified</span>
              )}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>
              <span style={{ color: 'var(--gold)' }}>★ {masseur.rating}</span> · {masseur.reviews} reviews · {masseur.distance} away
            </div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent)' }}>${masseur.rate}/hour</div>
          </div>
        </div>

        <p style={{ fontSize: '13px', color: 'var(--text-dim)', lineHeight: 1.6, marginBottom: '20px' }}>{masseur.bio}</p>

        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 700, marginBottom: '8px' }}>Specialties</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {masseur.specialties.map(specId => {
              const spec = SPECIALTIES.find(s => s.id === specId);
              return spec ? (
                <span key={specId} style={{
                  fontSize: '11px', color: 'var(--text)', background: 'var(--bg-elevated)',
                  padding: '5px 12px', borderRadius: '20px', border: '1px solid var(--border)',
                }}>{spec.icon} {spec.name}</span>
              ) : null;
            })}
          </div>
        </div>

        {booked ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ fontSize: '40px', marginBottom: '12px' }}>✅</div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>Booking Confirmed!</div>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
              {masseur.name} will see your request for {bookingDate} at {bookingTime}
            </div>
            <button onClick={onClose} style={{
              marginTop: '20px', background: 'var(--bg-elevated)', color: 'var(--text-dim)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
              padding: '8px 20px', fontSize: '12px', cursor: 'pointer',
            }}>Close</button>
          </div>
        ) : (
          <>
            <div style={{ fontSize: '10px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 700, marginBottom: '8px' }}>Book a session</div>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
              <input
                type="date"
                value={bookingDate}
                onChange={e => setBookingDate(e.target.value)}
                style={{
                  flex: 1, background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '10px 12px', color: 'var(--text)',
                  fontSize: '13px', outline: 'none', colorScheme: 'dark',
                }}
              />
              <select
                value={bookingTime}
                onChange={e => setBookingTime(e.target.value)}
                style={{
                  flex: 1, background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '10px 12px', color: 'var(--text)',
                  fontSize: '13px', outline: 'none', cursor: 'pointer',
                }}
              >
                <option value="">Select time</option>
                <option value="9:00 AM">9:00 AM</option>
                <option value="10:00 AM">10:00 AM</option>
                <option value="11:00 AM">11:00 AM</option>
                <option value="12:00 PM">12:00 PM</option>
                <option value="1:00 PM">1:00 PM</option>
                <option value="2:00 PM">2:00 PM</option>
                <option value="3:00 PM">3:00 PM</option>
                <option value="4:00 PM">4:00 PM</option>
                <option value="5:00 PM">5:00 PM</option>
                <option value="6:00 PM">6:00 PM</option>
                <option value="7:00 PM">7:00 PM</option>
                <option value="8:00 PM">8:00 PM</option>
              </select>
            </div>
            <button
              onClick={() => bookingDate && bookingTime && setBooked(true)}
              disabled={!bookingDate || !bookingTime}
              style={{
                width: '100%', background: 'var(--accent)', color: '#fff', border: 'none',
                borderRadius: 'var(--radius-sm)', padding: '12px', fontSize: '14px',
                fontWeight: 600, cursor: bookingDate && bookingTime ? 'pointer' : 'not-allowed',
                opacity: bookingDate && bookingTime ? 1 : 0.4, transition: 'all 0.15s',
              }}
            >
              Request Booking — ${masseur.rate}/hr
            </button>
          </>
        )}
      </div>
    </div>
  );
}
