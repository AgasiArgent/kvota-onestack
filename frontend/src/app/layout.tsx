import type { Metadata } from "next";
import "./globals.css";
import { Plus_Jakarta_Sans } from "next/font/google";
import { cn } from "@/lib/utils";

const plusJakartaSans = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-sans", weight: ["300","400","500","600","700"] });

export const metadata: Metadata = {
  title: "OneStack",
  description: "Система управления коммерческими предложениями",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" className={cn("font-sans", plusJakartaSans.variable)} suppressHydrationWarning>
      <body className="antialiased">{children}</body>
    </html>
  );
}
