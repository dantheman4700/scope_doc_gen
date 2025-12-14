"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { 
  FolderOpen, 
  FileText, 
  Settings, 
  Construction, 
  ChevronLeft,
  ChevronRight,
  LogOut,
  User
} from "lucide-react";
import { cn } from "@/lib/utils";
import { APP_VERSION } from "@/lib/version";

interface SidebarProps {
  user: {
    email: string;
  } | null;
}

const navigation = [
  { name: "Projects", href: "/projects", icon: FolderOpen },
  { name: "Documentation", href: "/docs", icon: FileText },
  { name: "Roadmap", href: "/roadmap", icon: Construction },
];

export function Sidebar({ user }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Load collapsed state from localStorage
  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved === "true") {
      setCollapsed(true);
    }
  }, []);

  // Save collapsed state to localStorage
  useEffect(() => {
    if (mounted) {
      localStorage.setItem("sidebar-collapsed", String(collapsed));
    }
  }, [collapsed, mounted]);

  const isActive = (href: string) => {
    if (href === "/projects") {
      return pathname === "/projects" || pathname.startsWith("/projects/");
    }
    return pathname === href || pathname.startsWith(href + "/");
  };

  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = useCallback(async () => {
    setLoggingOut(true);
    try {
      await fetch("/api/logout", {
        method: "POST",
        credentials: "include",
      });
      router.push("/login");
      router.refresh();
    } catch {
      // Still redirect on error
      router.push("/login");
    } finally {
      setLoggingOut(false);
    }
  }, [router]);

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-screen flex flex-col border-r border-border bg-card transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-border px-4">
        {!collapsed && (
          <Link href="/projects" className="flex items-baseline gap-2">
            <span className="text-lg font-semibold text-foreground">ScopeGen</span>
            <span className="text-xs text-muted-foreground">v{APP_VERSION}</span>
          </Link>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors",
            collapsed && "mx-auto"
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-all relative",
                active
                  ? "bg-primary/15 text-primary font-semibold text-base border-l-2 border-primary ml-0 pl-2.5"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground font-medium",
                collapsed && "justify-center px-2 border-l-0"
              )}
              title={collapsed ? item.name : undefined}
            >
              <item.icon className={cn("shrink-0", active ? "h-5 w-5" : "h-5 w-5")} />
              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="border-t border-border p-3">
        {user ? (
          <div className="space-y-1">
            <Link
              href="/settings"
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-all",
                isActive("/settings")
                  ? "bg-primary/15 text-primary font-semibold text-base border-l-2 border-primary ml-0 pl-2.5"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground font-medium",
                collapsed && "justify-center px-2 border-l-0"
              )}
              title={collapsed ? "Settings" : undefined}
            >
              <Settings className="h-5 w-5 shrink-0" />
              {!collapsed && <span>Settings</span>}
            </Link>
            
            {!collapsed && (
              <div className="flex items-center gap-3 px-3 py-2">
                <User className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span className="text-sm text-muted-foreground truncate">
                  {user.email}
                </span>
              </div>
            )}
            
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className={cn(
                "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors",
                collapsed && "justify-center px-2",
                loggingOut && "opacity-50 cursor-not-allowed"
              )}
              title={collapsed ? "Sign out" : undefined}
            >
              <LogOut className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{loggingOut ? "Signing out..." : "Sign out"}</span>}
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors",
              collapsed && "justify-center px-2"
            )}
            title={collapsed ? "Sign in" : undefined}
          >
            <User className="h-5 w-5 shrink-0" />
            {!collapsed && <span>Sign in</span>}
          </Link>
        )}
      </div>
    </aside>
  );
}

export default Sidebar;

