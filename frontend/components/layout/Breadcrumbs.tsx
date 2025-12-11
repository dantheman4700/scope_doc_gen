"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronRight, Home, ChevronDown } from "lucide-react";
import { useMemo, useState, useEffect, useRef, useCallback } from "react";

interface BreadcrumbItem {
  label: string;
  href?: string;
  hasDropdown?: boolean;
  dropdownType?: "projects" | "project-nav" | "runs";
}

interface BreadcrumbsProps {
  items?: BreadcrumbItem[];
  className?: string;
  projectId?: string;
  projectName?: string;
  runTitle?: string;
}

// Route name mappings
const routeNames: Record<string, string> = {
  projects: "Projects",
  settings: "Settings",
  docs: "Documentation",
  roadmap: "Roadmap",
  runs: "Runs",
  upload: "Upload Files",
  new: "New",
};

interface DropdownState {
  isOpen: boolean;
  items: Array<{ label: string; href: string }>;
  position: { x: number; y: number };
  type: string | null;
}

interface RunData {
  id: string;
  instructions: string | null;
  template_type: string | null;
  project_id: string;
}

interface ProjectData {
  id: string;
  name: string;
}

export function Breadcrumbs({ items, className = "", projectId, projectName, runTitle }: BreadcrumbsProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [dropdown, setDropdown] = useState<DropdownState>({ isOpen: false, items: [], position: { x: 0, y: 0 }, type: null });
  const [projects, setProjects] = useState<ProjectData[]>([]);
  const [runs, setRuns] = useState<RunData[]>([]);
  const [currentRun, setCurrentRun] = useState<RunData | null>(null);
  const [currentProject, setCurrentProject] = useState<ProjectData | null>(null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdown(prev => ({ ...prev, isOpen: false }));
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch projects list on mount
  useEffect(() => {
    setIsLoadingProjects(true);
    fetch("/api/projects")
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setProjects(data.map((p: ProjectData) => ({ id: p.id, name: p.name })));
        }
      })
      .catch(() => {})
      .finally(() => setIsLoadingProjects(false));
  }, []);

  // Fetch current run data if on a run page
  useEffect(() => {
    const runMatch = pathname.match(/\/runs\/([0-9a-f-]{36})/i);
    if (runMatch) {
      const runId = runMatch[1];
      setIsLoadingRuns(true);
      fetch(`/api/runs/${runId}`)
        .then(res => res.json())
        .then((run: RunData) => {
          setCurrentRun(run);
          // Also fetch the project
          if (run.project_id) {
            fetch(`/api/projects/${run.project_id}`)
              .then(res => res.json())
              .then((project: ProjectData) => setCurrentProject(project))
              .catch(() => {});
            // Fetch runs for this project
            fetch(`/api/projects/${run.project_id}/runs`)
              .then(res => res.json())
              .then(data => {
                if (Array.isArray(data)) {
                  setRuns(data);
                }
              })
              .catch(() => {})
              .finally(() => setIsLoadingRuns(false));
          } else {
            setIsLoadingRuns(false);
          }
        })
        .catch(() => setIsLoadingRuns(false));
    }
  }, [pathname]);

  // Fetch runs when on a project page
  useEffect(() => {
    const projectMatch = pathname.match(/\/projects\/([0-9a-f-]{36})/i);
    if (projectMatch) {
      const pid = projectMatch[1];
      setIsLoadingRuns(true);
      // Fetch project details
      fetch(`/api/projects/${pid}`)
        .then(res => res.json())
        .then((project: ProjectData) => setCurrentProject(project))
        .catch(() => {});
      // Fetch runs
      fetch(`/api/projects/${pid}/runs`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setRuns(data);
          }
        })
        .catch(() => {})
        .finally(() => setIsLoadingRuns(false));
    }
  }, [pathname]);

  // Derive run title from run data - improved extraction
  const derivedRunTitle = useMemo(() => {
    if (runTitle) return runTitle;
    if (!currentRun) return null;
    
    const instr = currentRun.instructions || "";
    
    // Check for focus instruction pattern: "focus on XYZ" or "focusing on XYZ"
    const focusMatch = instr.match(/(?:focus(?:ing)?\s+on)[:\s]+([^.]+)/i);
    if (focusMatch) {
      const t = focusMatch[1].replace(/\s+for\s+the.*$/i, "").trim();
      return t.slice(0, 45) + (t.length > 45 ? "…" : "");
    }
    
    // Check for "XYZ for the current project" pattern
    const forMatch = instr.match(/^(.+?)(?:\s+for\s+the\s+current)/i);
    if (forMatch) {
      const t = forMatch[1].trim();
      return t.slice(0, 45) + (t.length > 45 ? "…" : "");
    }
    
    // Use short instructions if meaningful
    if (instr.length > 5 && instr.length < 50) {
      return instr;
    }
    
    // Fall back to template type
    if (currentRun.template_type) {
      return `${currentRun.template_type} Document`;
    }
    
    return null; // Will show "Run" with UUID truncated
  }, [currentRun, runTitle]);

  const breadcrumbs = useMemo(() => {
    // If custom items are provided, use them
    if (items && items.length > 0) {
      return items;
    }

    const crumbs: BreadcrumbItem[] = [];
    
    // Check if we're on a run page
    const isRunPage = pathname.startsWith("/runs/");
    const isProjectPage = pathname.startsWith("/projects/");
    
    if (isRunPage) {
      // Run page: Projects > ProjectName > RunTitle
      crumbs.push({
        label: "Projects",
        href: "/projects",
        hasDropdown: true,
        dropdownType: "projects",
      });
      
      // Show project name or loading placeholder
      if (currentProject) {
        crumbs.push({
          label: currentProject.name,
          href: `/projects/${currentProject.id}`,
          hasDropdown: true,
          dropdownType: "project-nav",
        });
      } else {
        crumbs.push({
          label: "Loading…",
          hasDropdown: false,
        });
      }
      
      // Show run title with dropdown for switching runs - ALWAYS show dropdown if we have dropdown type
      const runLabel = derivedRunTitle || (currentRun?.id ? currentRun.id.slice(0, 8) + "…" : "Run");
      crumbs.push({
        label: runLabel,
        hasDropdown: true, // Always show dropdown indicator
        dropdownType: "runs",
      });
    } else if (isProjectPage) {
      // Project page: Projects > ProjectName
      const segments = pathname.split("/").filter(Boolean);
      
      crumbs.push({
        label: "Projects",
        href: "/projects",
        hasDropdown: true,
        dropdownType: "projects",
      });
      
      if (currentProject) {
        const hasMoreSegments = segments.length > 2;
        crumbs.push({
          label: currentProject.name,
          href: hasMoreSegments ? `/projects/${currentProject.id}` : undefined,
          hasDropdown: true,
          dropdownType: "project-nav",
        });
      }
      
      // Add additional segments (upload, etc.)
      if (segments.length > 2) {
        for (let i = 2; i < segments.length; i++) {
          const segment = segments[i];
          const label = routeNames[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
          crumbs.push({
            label,
            href: i < segments.length - 1 ? `/${segments.slice(0, i + 1).join("/")}` : undefined,
          });
        }
      }
    } else {
      // Other pages: auto-generate from pathname
      const segments = pathname.split("/").filter(Boolean);
      let currentPath = "";
      
      segments.forEach((segment, index) => {
        currentPath += `/${segment}`;
        const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment);
        
        if (isUUID) {
          crumbs.push({
            label: segment.slice(0, 8) + "…",
            href: index < segments.length - 1 ? currentPath : undefined,
          });
        } else {
          const label = routeNames[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
          crumbs.push({
            label,
            href: index < segments.length - 1 ? currentPath : undefined,
            hasDropdown: segment === "projects",
            dropdownType: segment === "projects" ? "projects" : undefined,
          });
        }
      });
    }

    return crumbs;
  }, [pathname, items, currentProject, currentRun, derivedRunTitle]);

  const buildDropdownItems = useCallback((dropdownType: string): Array<{ label: string; href: string }> => {
    switch (dropdownType) {
      case "projects":
        if (isLoadingProjects) {
          return [{ label: "Loading projects…", href: "#" }];
        }
        if (projects.length === 0) {
          return [{ label: "No projects found", href: "#" }];
        }
        return projects.slice(0, 10).map(p => ({
          label: p.name,
          href: `/projects/${p.id}`
        }));
        
      case "project-nav":
        if (!currentProject) {
          return [{ label: "Loading…", href: "#" }];
        }
        const projectNavItems = [
          { label: "📁 View Project", href: `/projects/${currentProject.id}` },
          { label: "⬆️ Upload Files", href: `/projects/${currentProject.id}/upload` },
        ];
        if (runs.length > 0) {
          projectNavItems.push(
            ...runs.slice(0, 8).map(r => {
              const label = r.instructions?.slice(0, 35) || r.template_type || r.id.slice(0, 8);
              return {
                label: `🏃 ${label}${(r.instructions?.length || 0) > 35 ? "…" : ""}`,
                href: `/runs/${r.id}`
              };
            })
          );
        } else if (isLoadingRuns) {
          projectNavItems.push({ label: "Loading runs…", href: "#" });
        }
        return projectNavItems;
        
      case "runs":
        if (isLoadingRuns) {
          return [{ label: "Loading runs…", href: "#" }];
        }
        if (runs.length === 0) {
          return [{ label: "No other runs", href: "#" }];
        }
        return runs.slice(0, 10).map(r => {
          const label = r.instructions?.slice(0, 35) || r.template_type || r.id.slice(0, 8);
          return {
            label: `${label}${(r.instructions?.length || 0) > 35 ? "…" : ""}`,
            href: `/runs/${r.id}`
          };
        });
        
      default:
        return [];
    }
  }, [projects, runs, currentProject, isLoadingProjects, isLoadingRuns]);

  const handleBreadcrumbClick = useCallback((event: React.MouseEvent, crumb: BreadcrumbItem) => {
    event.preventDefault();
    event.stopPropagation();
    
    if (crumb.hasDropdown && crumb.dropdownType) {
      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const dropdownItems = buildDropdownItems(crumb.dropdownType);
      
      // Toggle dropdown if clicking same type, otherwise open new one
      if (dropdown.isOpen && dropdown.type === crumb.dropdownType) {
        setDropdown(prev => ({ ...prev, isOpen: false }));
      } else {
        setDropdown({
          isOpen: true,
          items: dropdownItems,
          position: { x: rect.left, y: rect.bottom + 4 },
          type: crumb.dropdownType,
        });
      }
      return;
    }
    
    // Default: navigate normally
    if (crumb.href) {
      router.push(crumb.href);
    }
  }, [dropdown.isOpen, dropdown.type, buildDropdownItems, router]);

  const handleDropdownSelect = useCallback((href: string) => {
    if (href === "#") return; // Ignore placeholder items
    setDropdown(prev => ({ ...prev, isOpen: false }));
    router.push(href);
  }, [router]);

  if (breadcrumbs.length === 0) {
    return null;
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className={`flex items-center gap-1 text-sm ${className}`}>
        <Link
          href="/projects"
          className="flex items-center text-muted-foreground hover:text-foreground transition-colors"
        >
          <Home className="h-4 w-4" />
        </Link>
        
        {breadcrumbs.map((crumb, index) => (
          <div key={index} className="flex items-center gap-1">
            <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
            {crumb.href || crumb.hasDropdown ? (
              <button
                type="button"
                onClick={(e) => handleBreadcrumbClick(e, crumb)}
                className={`flex items-center gap-1 transition-colors cursor-pointer bg-transparent border-none p-1 rounded hover:bg-muted/50 ${
                  crumb.hasDropdown && dropdown.isOpen && dropdown.type === crumb.dropdownType 
                    ? "text-foreground bg-muted/50" 
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span>{crumb.label}</span>
                {crumb.hasDropdown && (
                  <ChevronDown 
                    className={`h-3 w-3 transition-transform ${
                      dropdown.isOpen && dropdown.type === crumb.dropdownType ? "rotate-180" : ""
                    }`} 
                  />
                )}
              </button>
            ) : (
              <span className="text-foreground font-medium p-1">{crumb.label}</span>
            )}
          </div>
        ))}
      </nav>
      
      {/* Dropdown menu */}
      {dropdown.isOpen && dropdown.items.length > 0 && (
        <div
          ref={dropdownRef}
          className="fixed z-[100] bg-card border border-border rounded-lg shadow-xl py-1 min-w-[200px] max-w-[300px] max-h-[400px] overflow-auto"
          style={{ left: dropdown.position.x, top: dropdown.position.y }}
        >
          {dropdown.items.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleDropdownSelect(item.href)}
              disabled={item.href === "#"}
              className={`w-full text-left px-3 py-2 text-sm transition-colors cursor-pointer bg-transparent border-none ${
                item.href === "#" 
                  ? "text-muted-foreground italic cursor-default" 
                  : "text-foreground hover:bg-muted"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export default Breadcrumbs;
