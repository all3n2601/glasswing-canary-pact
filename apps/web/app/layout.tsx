import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Canary Pact · Organizational simulation",
  description: "Explore the organizational blast radius of a decision before committing.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
