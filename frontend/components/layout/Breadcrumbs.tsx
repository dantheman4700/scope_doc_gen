"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronRight, Home, ChevronDown } from "lucide-react";
import { useMemo, useState, useEffect, useRef } from "react";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbsProps {
  items?: BreadcrumbItem[];
  className?: string;
  projectId?: string;
  projectName?: string;
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

export function Breadcrumbs({ items, className = "", projectId, projectName }: BreadcrumbsProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [dropdown, setDropdown] = useState<DropdownState>({ isOpen: false, items: [], position: { x: 0, y: 0 } });
  const [projects, setProjects] = useState<Array<{ id: string; name: string }>>([]);
  const [runs, setRuns] = useState<Array<{ id: string; instructions: string | null; template_type: string | null }>>([]);
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

  // Fetch projects when needed
  useEffect(() => {
    if (pathname.includes("/projects")) {
      fetch("/api/projects")
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setProjects(data.map((p: { id: string; name: string }) => ({ id: p.id, name: p.name })));
          }
        })
        .catch(() => {});
    }
  }, [pathname]);

  // Fetch runs when on a project page
  useEffect(() => {
    const projectMatch = pathname.match(/\/projects\/([^/]+)/);
    if (projectMatch) {
      const pid = projectMatch[1];
      fetch(`/api/projects/${pid}/runs`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setRuns(data.map((r: { id: string; instructions: string | null; template_type: string | null }) => ({
              id: r.id,
              instructions: r.instructions,
              template_type: r.template_type
            })));
          }
        })
        .catch(() => {});
    }
  }, [pathname]);

  const breadcrumbs = useMemo(() => {
    // If custom items are provided, use them
    if (items && items.length > 0) {
      return items;
    }

    // Auto-generate breadcrumbs from pathname
    const segments = pathname.split("/").filter(Boolean);
    const crumbs: BreadcrumbItem[] = [];

    let currentPath = "";
    segments.forEach((segment, index) => {
      currentPath += `/${segment}`;
      
      // Skip UUID segments but include them in the path
      const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment);
      
      if (isUUID) {
        // For UUIDs, use a shortened version as label
        const shortId = segment.slice(0, 8) + "…";
        crumbs.push({
          label: shortId,
          href: index < segments.length - 1 ? currentPath : undefined,
        });
      } else {
        const label = routeNames[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
        crumbs.push({
          label,
          href: index < segments.length - 1 ? currentPath : undefined,
        });
      }
    });

    return crumbs;
  }, [pathname, items]);

  const handleBreadcrumbClick = (event: React.MouseEvent, crumb: BreadcrumbItem, index: number) => {
    // Determine what kind of dropdown to show
    const rect = (event.target as HTMLElement).getBoundingClientRect();
    
    // Check if this is the "Projects" breadcrumb
    if (crumb.label === "Projects") {
      event.preventDefault();
      setDropdown({
        isOpen: true,
        items: projects.slice(0, 10).map(p => ({
          label: p.name,
          href: `/projects/${p.id}`
        })),
        position: { x: rect.left, y: rect.bottom + 4 }
      });
      return;
    }
    
    // Check if this is a project UUID (in projects context)
    const isProjectContext = pathname.includes("/projects/");
    const isUUID = /^[0-9a-f]{8}…$/i.test(crumb.label);
    
    if (isProjectContext && isUUID && runs.length > 0) {
      event.preventDefault();
      setDropdown({
        isOpen: true,
        items: [
          { label: "📁 Files", href: crumb.href || pathname },
          { label: "⬆️ Upload Files", href: `${crumb.href || pathname.split('/runs')[0]}/upload` },
          ...runs.slice(0, 8).map(r => {
            const runLabel = r.instructions?.slice(0, 40) || r.template_type || r.id.slice(0, 8);
            return {
              label: `🏃 ${runLabel}${r.instructions && r.instructions.length > 40 ? '…' : ''}`,
              href: `/runs/${r.id}`
            };
          })
        ],
        position: { x: rect.left, y: rect.bottom + 4 }
      });
      return;
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
            {crumb.href ? (
              <button
                onClick={(e) => handleBreadcrumbClick(e, crumb, index)}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-none p-0"
              >
                <span>{crumb.label}</span>
                <ChevronDown className="h-3 w-3 opacity-50" />
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
