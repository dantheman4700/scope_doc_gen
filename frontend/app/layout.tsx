import type { Metadata } from "next";
import "./globals.css";

import { getSessionUser } from "@/lib/auth";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarLayout } from "@/components/layout/SidebarLayout";

export const metadata: Metadata = {
  title: "ScopeGen",
  description: "AI-powered scope document generation platform",
  icons: {
    icon: "/favicon.ico",
    apple: "/logo.png",
  },
};

export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans antialiased">
        <TooltipProvider>
          <SidebarLayout user={user ? { email: user.email } : null}>
            {children}
          </SidebarLayout>
          <Toaster />
        </TooltipProvider>
      </body>
    </html>
  );
}
