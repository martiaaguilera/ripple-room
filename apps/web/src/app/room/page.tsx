import type { Metadata } from "next";
import { ControlRoom } from "@/components/ControlRoom";

export const metadata: Metadata = { title: "Control room — Ripple Room" };

export default function RoomPage() {
  return <ControlRoom />;
}
