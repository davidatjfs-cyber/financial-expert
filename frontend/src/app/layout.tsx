import type { Metadata, Viewport } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";

export const metadata: Metadata = {
  title: "财务分析专家",
  description: "智能分析财务报表，洞察经营状况",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased bg-[#0B0B0E] text-[#FAFAF9]">
        <div className="flex h-screen">
          {/* Sidebar - Desktop only */}
          <div className="hidden md:block">
            <Sidebar />
          </div>
          
          {/* Main Content */}
          <main className="flex-1 overflow-auto pb-20 md:pb-0">
            {children}
          </main>
        </div>
        
        {/* Mobile Bottom Nav */}
        <MobileNav />
      </body>
    </html>
  );
}
