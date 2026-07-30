export const metadata = {
  title: 'RentMasseur — Find Your Perfect Masseur',
  description: 'Discover professional masseurs near you. Verified profiles, instant booking, premium service.',
};

import './globals.css';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
