import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Next, Big_Shoulders } from "next/font/google";
import "./globals.css";

const display = Big_Shoulders({ subsets: ["latin"], variable: "--font-big-shoulders", axes: ["opsz"] });
const body = Atkinson_Hyperlegible_Next({ subsets: ["latin"], variable: "--font-atkinson" });

export const metadata: Metadata = {
  title: "Ripple Room — See the chain reaction. Fix the day.",
  description:
    "A live operations simulator for small events: watch a disruption ripple through the plan, then rescue it with NVIDIA Nemotron on Nebius and a constraint solver that checks every fix.",
};

export const viewport: Viewport = {
  themeColor: "#090d13",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
