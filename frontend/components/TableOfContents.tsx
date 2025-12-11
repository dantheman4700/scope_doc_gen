"use client";

import { useState, useEffect, useCallback } from "react";
import { ChevronUp, List } from "lucide-react";

interface TocSection {
  id: string;
  title: string;
  level: number;
}

interface TableOfContentsProps {
  sections: TocSection[];
}

export function TableOfContents({ sections }: TableOfContentsProps) {
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Track scroll position to highlight active section
  useEffect(() => {
    const handleScroll = () => {
      const scrollPos = window.scrollY + 100; // Offset for header
      
      // Find the current section
      for (let i = sections.length - 1; i >= 0; i--) {
        const section = sections[i];
        const element = document.getElementById(section.id);
        if (element && element.offsetTop <= scrollPos) {
          setActiveSection(section.id);
          return;
        }
      }
      setActiveSection(null);
    };

    window.addEventListener("scroll", handleScroll);
    handleScroll(); // Initial check
    
    return () => window.removeEventListener("scroll", handleScroll);
  }, [sections]);

  const scrollToSection = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 80; // Account for fixed header
      const elementPosition = element.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({
        top: elementPosition - offset,
        behavior: "smooth",
      });
    }
  }, []);

  const scrollToTop = useCallback(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  if (sections.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        position: "fixed",
        right: "1rem",
        top: "50%",
        transform: "translateY(-50%)",
        zIndex: 40,
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      }}
    >
      {/* Toggle button */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        style={{
          alignSelf: "flex-end",
          padding: "0.5rem",
          background: "rgba(31, 41, 55, 0.9)",
          border: "1px solid #374151",
          borderRadius: "0.5rem",
          color: "#9ca3af",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        title={isCollapsed ? "Show navigation" : "Hide navigation"}
      >
        <List className="h-4 w-4" />
      </button>

      {/* Table of contents */}
      {!isCollapsed && (
        <nav
          style={{
            background: "rgba(15, 15, 26, 0.95)",
            border: "1px solid #374151",
            borderRadius: "0.5rem",
            padding: "0.75rem",
            maxHeight: "60vh",
            overflowY: "auto",
            minWidth: "180px",
            maxWidth: "220px",
            backdropFilter: "blur(8px)",
          }}
        >
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "#6b7280",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "0.5rem",
              paddingBottom: "0.5rem",
              borderBottom: "1px solid #374151",
            }}
          >
            On this page
          </div>
          
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            {sections.map((section) => (
              <li key={section.id}>
                <button
                  onClick={() => scrollToSection(section.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "0.375rem 0.5rem",
                    paddingLeft: section.level > 1 ? `${section.level * 0.5}rem` : "0.5rem",
                    background: activeSection === section.id ? "rgba(96, 165, 250, 0.15)" : "transparent",
                    border: "none",
                    borderRadius: "0.25rem",
                    color: activeSection === section.id ? "#60a5fa" : "#9ca3af",
                    fontSize: section.level === 1 ? "0.8125rem" : "0.75rem",
                    fontWeight: section.level === 1 ? 500 : 400,
                    cursor: "pointer",
                    transition: "all 0.15s",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={section.title}
                >
                  {section.title}
                </button>
              </li>
            ))}
          </ul>
          
          {/* Back to top button */}
          <button
            onClick={scrollToTop}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "0.375rem",
              marginTop: "0.75rem",
              padding: "0.5rem",
              background: "rgba(55, 65, 81, 0.5)",
              border: "none",
              borderRadius: "0.375rem",
              color: "#9ca3af",
              fontSize: "0.75rem",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            <ChevronUp className="h-3 w-3" />
            Back to top
          </button>
        </nav>
      )}
    </div>
  );
}

export default TableOfContents;

