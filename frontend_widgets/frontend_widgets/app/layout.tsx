import type { Metadata } from "next";
import "../src/PlanWidget.css";

export const metadata: Metadata = {
  title: "InstaPlan widget handoff",
  description: "Standalone design and motion handoff for the InstaPlan hackathon demo",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
