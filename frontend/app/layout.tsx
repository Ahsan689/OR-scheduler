import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ORFlow",
  description:
    "Operating room scheduling and utilization. Portfolio project — synthetic data only.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
