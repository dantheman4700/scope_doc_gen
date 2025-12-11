"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronRight, Home, ChevronDown } from "lucide-react";
import { useMemo, useState, useEffect, useRef } from "react";

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
  const [dropdown, setDropdown] = useState<DropdownState>({ isOpen: false, items: [], position: { x: 0, y: 0 } });
  const [projects, setProjects] = useState<ProjectData[]>([]);
  const [runs, setRuns] = useState<RunData[]>([]);
  const [currentRun, setCurrentRun] = useState<RunData | null>(null);
  const [currentProject, setCurrentProject] = useState<ProjectData | null>(null);
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

  // Fetch projects list
  useEffect(() => {
    fetch("/api/projects")
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setProjects(data.map((p: ProjectData) => ({ id: p.id, name: p.name })));
        }
      })
      .catch(() => {});
  }, []);

  // Fetch current run data if on a run page
  useEffect(() => {
    const runMatch = pathname.match(/\/runs\/([0-9a-f-]{36})/i);
    if (runMatch) {
      const runId = runMatch[1];
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
              .catch(() => {});
          }
        })
        .catch(() => {});
    }
  }, [pathname]);

  // Fetch runs when on a project page
  useEffect(() => {
    const projectMatch = pathname.match(/\/projects\/([0-9a-f-]{36})/i);
    if (projectMatch) {
      const pid = projectMatch[1];
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
        .catch(() => {});
    }
  }, [pathname]);

  // Derive run title from run data
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
    
    return currentRun.id.slice(0, 8) + "…";
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
        // Show loading state while fetching project
        crumbs.push({
          label: "Loading…",
          hasDropdown: false,
        });
      }
      
      // Show run title with dropdown for switching runs
      crumbs.push({
        label: derivedRunTitle || (currentRun ? `${currentRun.template_type || "Run"}` : "Run"),
        hasDropdown: runs.length > 0,
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
  }, [pathname, items, currentProject, currentRun, derivedRunTitle, runs.length]);

  const handleBreadcrumbClick = (event: React.MouseEvent, crumb: BreadcrumbItem, index: number) => {
    const rect = (event.target as HTMLElement).getBoundingClientRect();
    
    if (crumb.hasDropdown && crumb.dropdownType) {
      event.preventDefault();
      
      let dropdownItems: Array<{ label: string; href: string }> = [];
      
      switch (crumb.dropdownType) {
        case "projects":
          dropdownItems = projects.slice(0, 10).map(p => ({
            label: p.name,
            href: `/projects/${p.id}`
          }));
          break;
          
        case "project-nav":
          if (currentProject) {
            dropdownItems = [
              { label: "📁 View Project", href: `/projects/${currentProject.id}` },
              { label: "⬆️ Upload Files", href: `/projects/${currentProject.id}/upload` },
              ...runs.slice(0, 8).map(r => {
                const label = r.instructions?.slice(0, 35) || r.template_type || r.id.slice(0, 8);
                return {
                  label: `🏃 ${label}${(r.instructions?.length || 0) > 35 ? "…" : ""}`,
                  href: `/runs/${r.id}`
                };
              })
            ];
          }
          break;
          
        case "runs":
          dropdownItems = runs.slice(0, 10).map(r => {
            const label = r.instructions?.slice(0, 35) || r.template_type || r.id.slice(0, 8);
            return {
              label: `${label}${(r.instructions?.length || 0) > 35 ? "…" : ""}`,
              href: `/runs/${r.id}`
            };
          });
          break;
      }
      
      if (dropdownItems.length > 0) {
        setDropdown({
          isOpen: true,
          items: dropdownItems,
          position: { x: rect.left, y: rect.bottom + 4 }
        });
        return;
      }
    }
    
    // Default: navigate normally
    if (crumb.href) {
      router.push(crumb.href);
    }
  };

  const handleDropdownSelect = (href: string) => {
    setDropdown(prev => ({ ...prev, isOpen: false }));
    router.push(href);
  };

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
                onClick={(e) => handleBreadcrumbClick(e, crumb, index)}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-none p-0"
              >
                <span>{crumb.label}</span>
                {crumb.hasDropdown && <ChevronDown className="h-3 w-3 opacity-50" />}
              </button>
            ) : (
              <span className="text-foreground font-medium">{crumb.label}</span>
            )}
          </div>
        ))}
      </nav>
      
      {/* Dropdown menu */}
      {dropdown.isOpen && dropdown.items.length > 0 && (
        <div
          ref={dropdownRef}
          className="fixed z-50 bg-card border border-border rounded-lg shadow-lg py-1 min-w-[200px] max-h-[300px] overflow-auto"
          style={{ left: dropdown.position.x, top: dropdown.position.y }}
        >
          {dropdown.items.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleDropdownSelect(item.href)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors cursor-pointer bg-transparent border-none text-foreground"
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
