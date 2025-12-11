"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronRight, ChevronLeft, Play, FileText } from "lucide-react";
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

export function RightSidebar({ sections = [], projectId, recentRuns: propRecentRuns = [], className = "" }: RightSidebarProps) {
  const pathname = usePathname();
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [fetchedRuns, setFetchedRuns] = useState<RecentRun[]>([]);
  const tocContainerRef = useRef<HTMLDivElement>(null);

  // Fetch recent runs if projectId is provided but no runs passed
  useEffect(() => {
    if (projectId && propRecentRuns.length === 0) {
      fetch(`/api/projects/${projectId}/runs`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setFetchedRuns(
              data.slice(0, 5).map((r: any) => ({
                id: r.id,
                title: r.document_title || r.instructions?.slice(0, 30) || r.template_type || r.id.slice(0, 8),
                templateType: r.template_type,
              }))
            );
          }
        })
        .catch(() => {});
    }
  }, [projectId, propRecentRuns.length]);

  const recentRuns = propRecentRuns.length > 0 ? propRecentRuns : fetchedRuns;

  // Track scroll position to highlight active section
  useEffect(() => {
    if (sections.length === 0) return;

    const handleScroll = () => {
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

  // Scroll TOC to center active item
  useEffect(() => {
    if (!tocContainerRef.current || !activeSection) return;
    
    const activeButton = tocContainerRef.current.querySelector(`[data-section-id="${activeSection}"]`) as HTMLElement;
    if (activeButton) {
      const container = tocContainerRef.current;
      const containerHeight = container.clientHeight;
      const buttonTop = activeButton.offsetTop;
      const buttonHeight = activeButton.clientHeight;
      
      // Calculate scroll position to center the active item
      const targetScroll = buttonTop - (containerHeight / 2) + (buttonHeight / 2);
      
      container.scrollTo({
        top: Math.max(0, targetScroll),
        behavior: "smooth",
      });
    }
  }, [activeSection]);

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
    if (activeIndex === -1) return {};
    
    const distance = Math.abs(index - activeIndex);
    
    // Scale and opacity based on distance from active
    const scale = sectionId === activeSection ? 1 : Math.max(0.85, 1 - distance * 0.05);
    const opacity = sectionId === activeSection ? 1 : Math.max(0.5, 1 - distance * 0.15);
    
    return {
      transform: `scale(${scale})`,
      opacity,
      transition: "all 0.2s ease-out",
    };
  }, [activeSection, sections]);

  const isRunPage = pathname.startsWith("/runs/");
  const isProjectPage = pathname.startsWith("/projects/") && pathname !== "/projects";
  const isProjectsHome = pathname === "/projects" || pathname === "/projects/";
  const isSettingsPage = pathname.startsWith("/settings");
  const isDocsPage = pathname.startsWith("/docs");
  const isRoadmapPage = pathname.startsWith("/roadmap");

  // Don't show on projects home page
  if (isProjectsHome) {
    return null;
  }

  const showToc = sections.length > 0 && isRunPage;
  const showRuns = (isProjectPage || isRunPage) && recentRuns.length > 0;

  // Show sidebar on all pages except /projects home, but may be empty for settings/docs/roadmap
  const hasContent = showToc || showRuns;

  // For pages without content, show a minimal collapsed sidebar indicator
  if (!hasContent && !isSettingsPage && !isDocsPage && !isRoadmapPage) {
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
        <div className="flex-1 flex flex-col overflow-hidden py-4 px-2">
          {/* Table of Contents - with vertical centering via flex */}
          {showToc && (
            <div className="flex-1 flex flex-col min-h-0 mb-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-2 mb-3 shrink-0">
                On this page
              </div>
              <div 
                ref={tocContainerRef}
                className="flex-1 overflow-y-auto flex flex-col justify-center"
              >
                <nav className="flex flex-col">
                  {sections.map((section, index) => {
                    const isActive = activeSection === section.id;
                    return (
                      <button
                        key={section.id}
                        data-section-id={section.id}
                        onClick={() => scrollToSection(section.id)}
                        className={cn(
                          "w-full text-left px-3 py-1.5 rounded-md transition-all text-sm my-0.5",
                          isActive
                            ? "bg-primary/20 text-primary font-semibold border-l-2 border-primary"
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
            </div>
          )}

          {/* Recent Runs */}
          {showRuns && (
            <div className="shrink-0">
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
                        ? "bg-primary/20 text-primary font-medium border-l-2 border-primary"
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

          {/* Show helpful message if no content */}
          {!showToc && !showRuns && (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-xs text-muted-foreground text-center px-2">
                Navigation will appear when viewing runs
              </p>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

export default RightSidebar;
