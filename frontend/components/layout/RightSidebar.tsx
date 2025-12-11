"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, ChevronLeft, FileText, Play } from "lucide-react";
import { cn } from "@/lib/utils";

interface TocSection {
  id: string;
  title: string;
  level: number;
}

interface RecentRun {
  id: string;
  title: string;
  templateType?: string;
}

interface RightSidebarProps {
  sections?: TocSection[];
  projectId?: string;
  recentRuns?: RecentRun[];
  className?: string;
}

export function RightSidebar({ sections = [], projectId, recentRuns = [], className = "" }: RightSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Track scroll position to highlight active section
  useEffect(() => {
    const handleScroll = () => {
      if (sections.length === 0) return;
      
      const scrollPos = window.scrollY + 150; // Offset for header
      
      // Find the current section
      for (let i = sections.length - 1; i >= 0; i--) {
        const section = sections[i];
        const element = document.getElementById(section.id);
        if (element && element.offsetTop <= scrollPos) {
          setActiveSection(section.id);
          return;
        }
      }
      setActiveSection(sections[0]?.id || null);
    };

    window.addEventListener("scroll", handleScroll);
    handleScroll(); // Initial check
    
    return () => window.removeEventListener("scroll", handleScroll);
  }, [sections]);

  // Load collapsed state
  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("right-sidebar-collapsed");
    if (saved === "true") {
      setCollapsed(true);
    }
  }, []);

  // Save collapsed state
  useEffect(() => {
    if (mounted) {
      localStorage.setItem("right-sidebar-collapsed", String(collapsed));
    }
  }, [collapsed, mounted]);

  const scrollToSection = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 100;
      const elementPosition = element.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({
        top: elementPosition - offset,
        behavior: "smooth",
      });
    }
  }, []);

  // Determine visibility of sections based on active state (wheel effect)
  const getItemStyle = useCallback((sectionId: string, index: number): React.CSSProperties => {
    const activeIndex = sections.findIndex(s => s.id === activeSection);
    const distance = Math.abs(index - activeIndex);
    
    // Scale based on distance from active
    const scale = activeSection === sectionId ? 1 : Math.max(0.7, 1 - distance * 0.1);
    const opacity = activeSection === sectionId ? 1 : Math.max(0.5, 1 - distance * 0.15);
    
    return {
      transform: `scale(${scale})`,
      opacity,
      transition: "all 0.2s ease-out",
    };
  }, [activeSection, sections]);

  const isRunPage = pathname.startsWith("/runs/");
  const isProjectPage = pathname.startsWith("/projects/");
  const showToc = sections.length > 0 && isRunPage;
  const showRuns = (isProjectPage || isRunPage) && recentRuns.length > 0;

  // Don't render if nothing to show
  if (!showToc && !showRuns) {
    return null;
  }

  return (
    <aside
      className={cn(
        "fixed right-0 top-0 z-30 h-screen flex flex-col border-l border-border bg-card/50 backdrop-blur-sm transition-all duration-300",
        collapsed ? "w-10" : "w-52",
        className
      )}
    >
      {/* Collapse button */}
      <div className="flex h-16 items-center justify-center border-b border-border">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto py-4 px-2">
          {/* Table of Contents */}
          {showToc && (
            <div className="mb-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-2 mb-3">
                On this page
              </div>
              <nav className="flex flex-col items-center">
                {sections.map((section, index) => {
                  const isActive = activeSection === section.id;
                  return (
                    <button
                      key={section.id}
                      onClick={() => scrollToSection(section.id)}
                      className={cn(
                        "w-full text-left px-3 py-1.5 rounded-md transition-all text-sm",
                        isActive
                          ? "bg-primary/15 text-primary font-medium"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                      )}
                      style={getItemStyle(section.id, index)}
                      title={section.title}
                    >
                      <span className="block truncate">
                        {section.title}
                      </span>
                    </button>
                  );
                })}
              </nav>
            </div>
          )}

          {/* Recent Runs */}
          {showRuns && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-2 mb-3">
                Recent Runs
              </div>
              <nav className="space-y-1">
                {recentRuns.slice(0, 5).map((run) => (
                  <Link
                    key={run.id}
                    href={`/runs/${run.id}`}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                      pathname === `/runs/${run.id}`
                        ? "bg-primary/15 text-primary font-medium"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                    )}
                  >
                    <Play className="h-3 w-3 shrink-0" />
                    <span className="truncate text-xs">{run.title}</span>
                  </Link>
                ))}
              </nav>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

export default RightSidebar;

