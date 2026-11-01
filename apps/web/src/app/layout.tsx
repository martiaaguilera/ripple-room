import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Next, Big_Shoulders } from "next/font/google";
import { MOTION_BOOT } from "@/lib/useReducedMotion";
import "./globals.css";

const display = Big_Shoulders({ subsets: ["latin"], variable: "--font-big-shoulders", axes: ["opsz"] });
const body = Atkinson_Hyperlegible_Next({ subsets: ["latin"], variable: "--font-atkinson" });

const TITLE = "Ripple Room · Nebius × NVIDIA Global AI Hackathon 2026";
const DESCRIPTION =
  "Built at the Nebius × NVIDIA Global AI Hackathon 2026. Watch a disruption ripple through a live-event plan, then recover it: NVIDIA Nemotron on Nebius proposes fixes, a constraint solver verifies each one, and you approve.";

export const metadata: Metadata = {
  metadataBase: new URL("https://ripple-room-five.vercel.app"),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    type: "website",
    url: "/",
    siteName: "Ripple Room",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Ripple Room: a late truck ripples through an event plan" }],
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: ["/og.png"] },
};

export const viewport: Viewport = {
  themeColor: "#090d13",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // The boot script sets data-motion on <html> before hydration, hence suppressHydrationWarning.
    <html lang="en" className={`${display.variable} ${body.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: MOTION_BOOT }} />
      </head>
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
