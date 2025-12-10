"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { useMemo } from "react";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbsProps {
  items?: BreadcrumbItem[];
  className?: string;
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

export function Breadcrumbs({ items, className = "" }: BreadcrumbsProps) {
  const pathname = usePathname();

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

  if (breadcrumbs.length === 0) {
    return null;
  }

  return (
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
            <Link
              href={crumb.href}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {crumb.label}
            </Link>
          ) : (
            <span className="text-foreground font-medium">{crumb.label}</span>
          )}
        </div>
      ))}
    </nav>
  );
}

export default Breadcrumbs;

