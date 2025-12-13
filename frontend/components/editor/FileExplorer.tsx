"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { 
  FileText, 
  FileUp, 
  History, 
  ChevronDown, 
  ChevronRight,
  File,
  FileSpreadsheet,
  FileImage,
  FileCode,
} from "lucide-react";

interface FileItem {
  id: string;
  name: string;
  type: "input" | "output" | "version";
  version?: number;  // Can be float like 1.1, 1.2
  isActive?: boolean;
  mediaType?: string;
  path?: string;
}

// Get appropriate icon based on file extension or media type
function getFileIcon(name: string, mediaType?: string) {
  const ext = name.toLowerCase().split(".").pop() || "";
  
  if (["xlsx", "xls", "csv"].includes(ext) || mediaType?.includes("spreadsheet")) {
    return <FileSpreadsheet className="h-3.5 w-3.5 text-green-600" />;
  }
  if (["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(ext) || mediaType?.startsWith("image/")) {
    return <FileImage className="h-3.5 w-3.5 text-purple-500" />;
  }
  if (["pdf", "docx", "doc", "txt", "md"].includes(ext)) {
    return <FileText className="h-3.5 w-3.5 text-blue-500" />;
  }
  if (["json", "yaml", "yml", "xml", "html"].includes(ext)) {
    return <FileCode className="h-3.5 w-3.5 text-orange-500" />;
  }
  return <File className="h-3.5 w-3.5 text-muted-foreground" />;
}

// Format version number for display (e.g., 1.1 -> "v1.1", 1 -> "v1")
function formatVersion(version: number): string {
  if (Number.isInteger(version)) {
    return `v${version}`;
  }
  return `v${version.toFixed(1)}`;
}

interface FileExplorerProps {
  inputFiles: FileItem[];
  versions: FileItem[];
  currentVersion: number;  // Can be float
  onFileSelect: (file: FileItem) => void;
  onVersionSelect: (version: number) => void;
  className?: string;
}

export function FileExplorer({
  inputFiles,
  versions,
  currentVersion,
  onFileSelect,
  onVersionSelect,
  className,
}: FileExplorerProps) {
  const [expandedSections, setExpandedSections] = React.useState<Record<string, boolean>>({
    inputs: true,
    versions: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  // Check if a version is active (handles float comparison)
  const isVersionActive = (version: number) => {
    return Math.abs(currentVersion - version) < 0.001;
  };

  return (
    <div className={cn("flex flex-col text-sm", className)}>
      {/* Input Files Section */}
      <div className="border-b border-border/50">
        <button
          onClick={() => toggleSection("inputs")}
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted/50"
        >
          {expandedSections.inputs ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <FileUp className="h-4 w-4 text-blue-500" />
          <span className="font-medium">Input Files</span>
          <span className="ml-auto text-xs text-muted-foreground">
            {inputFiles.length}
          </span>
        </button>
        {expandedSections.inputs && (
          <div className="pb-2">
            {inputFiles.length === 0 ? (
              <div className="px-7 py-2 text-xs text-muted-foreground italic">
                No input files
              </div>
            ) : (
              inputFiles.map(file => (
                <button
                  key={file.id}
                  onClick={() => onFileSelect(file)}
                  className={cn(
                    "flex w-full items-center gap-2 px-7 py-1.5 text-left hover:bg-muted/50",
                    file.isActive && "bg-muted"
                  )}
                  title={file.name}
                >
                  {getFileIcon(file.name, file.mediaType)}
                  <span className="truncate text-xs">{file.name}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* Versions Section */}
      <div>
        <button
          onClick={() => toggleSection("versions")}
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted/50"
        >
          {expandedSections.versions ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <History className="h-4 w-4 text-purple-500" />
          <span className="font-medium">Versions</span>
          <span className="ml-auto text-xs text-muted-foreground">
            {versions.length + 1}
          </span>
        </button>
        {expandedSections.versions && (
          <div className="pb-2">
            {/* Original version (v1) */}
            <button
              onClick={() => onVersionSelect(1)}
              className={cn(
                "flex w-full items-center gap-2 px-7 py-1.5 text-left hover:bg-muted/50",
                isVersionActive(1) && "bg-muted"
              )}
            >
              <FileText className="h-3.5 w-3.5 text-green-500" />
              <span className="text-xs">v1 (Original)</span>
              {isVersionActive(1) && (
                <span className="ml-auto text-xs text-green-600">Active</span>
              )}
            </button>
            
            {/* Sub-versions (1.1, 1.2, etc.) */}
            {versions.map(version => {
              const versionNum = version.version ?? 1.1;
              return (
                <button
                  key={version.id}
                  onClick={() => onVersionSelect(versionNum)}
                  className={cn(
                    "flex w-full items-center gap-2 px-7 py-1.5 text-left hover:bg-muted/50",
                    isVersionActive(versionNum) && "bg-muted"
                  )}
                >
                  <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs">{formatVersion(versionNum)}</span>
                  {isVersionActive(versionNum) && (
                    <span className="ml-auto text-xs text-green-600">Active</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
