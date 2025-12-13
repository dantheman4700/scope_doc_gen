"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";

interface SidebarLayoutProps {
  children: React.ReactNode;
  user: {
    email: string;
  } | null;
}

// Pages that should NOT show the sidebar
const noSidebarPaths = ["/login", "/register"];

// Pages that need full viewport height without padding (e.g., editor)
const fullViewportPaths = ["/editor"];

export function SidebarLayout({ children, user }: SidebarLayoutProps) {
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  const showSidebar = !noSidebarPaths.includes(pathname);
  
  // Check if this is a full viewport page (like editor) that needs no padding
  const isFullViewport = fullViewportPaths.some(path => pathname.endsWith(path));
  
  // Show right sidebar on run pages and project detail pages (not /projects home)
  // But NOT on the editor page which has its own layout
  const isProjectsHome = pathname === "/projects" || pathname === "/projects/";
  const showRightSidebar = !isProjectsHome && !isFullViewport && (
    pathname.startsWith("/runs/") || 
    (pathname.startsWith("/projects/") && pathname !== "/projects" && pathname !== "/projects/")
  );

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved === "true") {
      setSidebarCollapsed(true);
    }
    const savedRight = localStorage.getItem("right-sidebar-collapsed");
    if (savedRight === "true") {
      setRightSidebarCollapsed(true);
    }
    
    // Listen for localStorage changes
    const handleStorage = () => {
      const saved = localStorage.getItem("sidebar-collapsed");
      setSidebarCollapsed(saved === "true");
      const savedRight = localStorage.getItem("right-sidebar-collapsed");
      setRightSidebarCollapsed(savedRight === "true");
    };
    
    window.addEventListener("storage", handleStorage);
    
    // Also listen for changes via a custom event
    const handleCollapse = () => {
      const saved = localStorage.getItem("sidebar-collapsed");
      setSidebarCollapsed(saved === "true");
      const savedRight = localStorage.getItem("right-sidebar-collapsed");
      setRightSidebarCollapsed(savedRight === "true");
    };
    window.addEventListener("sidebar-collapse-change", handleCollapse);
    
    // Poll for changes (backup)
    const interval = setInterval(() => {
      const saved = localStorage.getItem("sidebar-collapsed");
      setSidebarCollapsed(saved === "true");
      const savedRight = localStorage.getItem("right-sidebar-collapsed");
      setRightSidebarCollapsed(savedRight === "true");
    }, 100);
    
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sidebar-collapse-change", handleCollapse);
      clearInterval(interval);
    };
  }, []);

  if (!showSidebar) {
    return <>{children}</>;
  }

  return (
    <div className={cn("flex", isFullViewport ? "h-screen overflow-hidden" : "min-h-screen")}>
      <Sidebar user={user} />
      <main
        className={cn(
          "flex-1 transition-all duration-300",
          isFullViewport ? "h-screen overflow-hidden" : "p-6",
          mounted && sidebarCollapsed ? "ml-16" : "ml-64",
          showRightSidebar && (mounted && rightSidebarCollapsed ? "mr-10" : "mr-52")
        )}
      >
        {children}
      </main>
    </div>
  );
}

export default SidebarLayout;

