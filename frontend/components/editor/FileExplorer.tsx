"use client";

import React, { useMemo } from "react";
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
  Clock,
  Trash2,
  RotateCcw,
  Eye,
  Database,
  Loader2,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";

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
  onVersionDelete?: (version: number) => void;
  onVersionRevert?: (version: number) => void;
  isIndexed?: boolean;
  isIndexing?: boolean;
  indexedChunks?: number;
  indexProgress?: number; // 0-100
  indexStatus?: string;  // Status message during indexing
  indexedFileNames?: string[];  // List of indexed file names
  indexedVersion?: number | null;  // Which version is indexed
  onIndexWorkspace?: () => void;
  className?: string;
}

interface VersionGroup {
  major: number;
  subVersions: FileItem[];
  latestSubVersion: number;
}

/**
 * Version button with context menu
 */
function VersionButton({
  version,
  label,
  isActive,
  isMajor,
  isVersionIndexed,
  onClick,
  onDelete,
  onRevert,
  className,
}: {
  version: number;
  label: string;
  isActive: boolean;
  isMajor: boolean;
  isVersionIndexed?: boolean;
  onClick: () => void;
  onDelete?: () => void;
  onRevert?: () => void;
  className?: string;
}) {
  // Prevent deletion of v1 (original)
  const canDelete = version !== 1;
  
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <button
          onClick={onClick}
          className={cn(
            "flex w-full items-center gap-2 text-left hover:bg-muted/50",
            isMajor ? "px-5 py-1.5" : "px-2 py-1",
            isActive && "bg-muted",
            className
          )}
          title={isVersionIndexed ? `${label} (indexed for AI search)` : label}
        >
          <FileText className={cn(
            isMajor ? "h-3.5 w-3.5" : "h-3 w-3",
            isMajor && version === 1 ? "text-green-500" : 
            isMajor ? "text-blue-500" : "text-muted-foreground"
          )} />
          <span className={cn(
            "text-xs flex-1",
            isMajor ? "font-medium" : "text-muted-foreground"
          )}>
            {label}
          </span>
          {isVersionIndexed && (
            <span className="h-2 w-2 rounded-full bg-green-500 shrink-0" title="Indexed" />
          )}
          {isActive && (
            <span className="text-xs text-green-600">Active</span>
          )}
        </button>
      </ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem onClick={onClick}>
          <Eye className="mr-2 h-4 w-4" />
          View
        </ContextMenuItem>
        {onRevert && !isActive && (
          <ContextMenuItem onClick={onRevert}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Revert to this version
          </ContextMenuItem>
        )}
        {canDelete && onDelete && (
          <>
            <ContextMenuSeparator />
            <ContextMenuItem 
              onClick={onDelete}
              className="text-red-600 focus:text-red-600"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </ContextMenuItem>
          </>
        )}
      </ContextMenuContent>
    </ContextMenu>
  );
}

export function FileExplorer({
  inputFiles,
  versions,
  currentVersion,
  onFileSelect,
  onVersionSelect,
  onVersionDelete,
  onVersionRevert,
  isIndexed = false,
  isIndexing = false,
  indexedChunks = 0,
  indexProgress = 0,
  indexStatus = "",
  indexedFileNames = [],
  indexedVersion = null,
  onIndexWorkspace,
  className,
}: FileExplorerProps) {
  const [expandedSections, setExpandedSections] = React.useState<Record<string, boolean>>({
    inputs: true,
    versions: true,
  });
  const [expandedMajorVersions, setExpandedMajorVersions] = React.useState<Record<number, boolean>>({});

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const toggleMajorVersion = (major: number) => {
    setExpandedMajorVersions(prev => ({
      ...prev,
      [major]: !prev[major],
    }));
  };

  // Check if a version is active (handles float comparison)
  const isVersionActive = (version: number) => {
    return Math.abs(currentVersion - version) < 0.001;
  };

  // Check if a version is the indexed one
  const isVersionTheIndexed = (version: number) => {
    if (indexedVersion === null) return false;
    return Math.abs(indexedVersion - version) < 0.001;
  };

  // Group versions by major version
  const versionGroups = useMemo((): VersionGroup[] => {
    const groups: Map<number, FileItem[]> = new Map();
    
    // Group all versions by their major number
    for (const v of versions) {
      const versionNum = v.version ?? 1;
      const major = Math.floor(versionNum);
      
      if (!groups.has(major)) {
        groups.set(major, []);
      }
      groups.get(major)!.push(v);
    }
    
    // Convert to array and sort
    const result: VersionGroup[] = [];
    const sortedMajors = Array.from(groups.keys()).sort((a, b) => b - a); // Descending
    
    for (const major of sortedMajors) {
      const subVersions = groups.get(major)!;
      // Sort sub-versions by version number descending
      subVersions.sort((a, b) => (b.version ?? 0) - (a.version ?? 0));
      
      const latestSubVersion = subVersions.length > 0 
        ? Math.max(...subVersions.map(v => v.version ?? major))
        : major;
      
      result.push({
        major,
        subVersions,
        latestSubVersion,
      });
    }
    
    return result;
  }, [versions]);

  // Get current major version
  const currentMajor = Math.floor(currentVersion);

  // Count major versions (including v1 which may not be in the list)
  const majorVersionCount = useMemo(() => {
    const majors = new Set(versionGroups.map(g => g.major));
    majors.add(1); // Always include v1
    return majors.size;
  }, [versionGroups]);

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
              inputFiles.map(file => {
                const isFileIndexed = indexedFileNames.some(
                  name => name.toLowerCase() === file.name.toLowerCase()
                );
                return (
                  <button
                    key={file.id}
                    onClick={() => onFileSelect(file)}
                    className={cn(
                      "flex w-full items-center gap-2 px-7 py-1.5 text-left hover:bg-muted/50",
                      file.isActive && "bg-muted"
                    )}
                    title={file.name + (isFileIndexed ? " (indexed)" : " (not indexed)")}
                  >
                    {getFileIcon(file.name, file.mediaType)}
                    <span className="truncate text-xs flex-1">{file.name}</span>
                    {isFileIndexed && (
                      <span className="h-2 w-2 rounded-full bg-green-500 shrink-0" title="Indexed" />
                    )}
                  </button>
                );
              })
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
            {majorVersionCount}
          </span>
        </button>
        {expandedSections.versions && (
          <div className="pb-2">
            {/* Original version (v1) - always show */}
            <div>
              <VersionButton
                version={1}
                label="v1 (Original)"
                isActive={isVersionActive(1)}
                isMajor={true}
                isVersionIndexed={isVersionTheIndexed(1)}
                onClick={() => onVersionSelect(1)}
                onDelete={onVersionDelete ? () => onVersionDelete(1) : undefined}
                onRevert={onVersionRevert ? () => onVersionRevert(1) : undefined}
                className={currentMajor === 1 ? "bg-muted/70" : ""}
              />
              
              {/* Sub-versions for v1 */}
              {versionGroups.find(g => g.major === 1)?.subVersions.length ? (
                <div className="ml-5">
                  <button
                    onClick={() => toggleMajorVersion(1)}
                    className="flex w-full items-center gap-1 px-2 py-1 text-left text-xs text-muted-foreground hover:text-foreground"
                  >
                    {expandedMajorVersions[1] ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    <Clock className="h-3 w-3" />
                    <span>
                      {versionGroups.find(g => g.major === 1)?.subVersions.length} saved edit{versionGroups.find(g => g.major === 1)?.subVersions.length !== 1 ? 's' : ''}
                    </span>
                  </button>
                  
                  {expandedMajorVersions[1] && (
                    <div className="ml-4">
                      {versionGroups.find(g => g.major === 1)?.subVersions.map(v => {
                        const vNum = v.version ?? 1.1;
                        return (
                          <VersionButton
                            key={v.id}
                            version={vNum}
                            label={formatVersion(vNum)}
                            isActive={isVersionActive(vNum)}
                            isMajor={false}
                            isVersionIndexed={isVersionTheIndexed(vNum)}
                            onClick={() => onVersionSelect(vNum)}
                            onDelete={onVersionDelete ? () => onVersionDelete(vNum) : undefined}
                            onRevert={onVersionRevert ? () => onVersionRevert(vNum) : undefined}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
            
            {/* Major versions 2+ */}
            {versionGroups
              .filter(g => g.major > 1)
              .map(group => (
                <div key={group.major}>
                  <VersionButton
                    version={group.major}
                    label={`v${group.major}`}
                    isActive={isVersionActive(group.major)}
                    isMajor={true}
                    isVersionIndexed={isVersionTheIndexed(group.major)}
                    onClick={() => onVersionSelect(group.major)}
                    onDelete={onVersionDelete ? () => onVersionDelete(group.major) : undefined}
                    onRevert={onVersionRevert ? () => onVersionRevert(group.major) : undefined}
                    className={currentMajor === group.major ? "bg-muted/70" : ""}
                  />
                  
                  {/* Sub-versions for this major */}
                  {group.subVersions.filter(v => !Number.isInteger(v.version)).length > 0 && (
                    <div className="ml-5">
                      <button
                        onClick={() => toggleMajorVersion(group.major)}
                        className="flex w-full items-center gap-1 px-2 py-1 text-left text-xs text-muted-foreground hover:text-foreground"
                      >
                        {expandedMajorVersions[group.major] ? (
                          <ChevronDown className="h-3 w-3" />
                        ) : (
                          <ChevronRight className="h-3 w-3" />
                        )}
                        <Clock className="h-3 w-3" />
                        <span>
                          {group.subVersions.filter(v => !Number.isInteger(v.version)).length} saved edit{group.subVersions.filter(v => !Number.isInteger(v.version)).length !== 1 ? 's' : ''}
                        </span>
                      </button>
                      
                      {expandedMajorVersions[group.major] && (
                        <div className="ml-4">
                          {group.subVersions
                            .filter(v => !Number.isInteger(v.version))
                            .map(v => {
                              const vNum = v.version ?? group.major + 0.1;
                              return (
                                <VersionButton
                                  key={v.id}
                                  version={vNum}
                                  label={formatVersion(vNum)}
                                  isActive={isVersionActive(vNum)}
                                  isMajor={false}
                                  isVersionIndexed={isVersionTheIndexed(vNum)}
                                  onClick={() => onVersionSelect(vNum)}
                                  onDelete={onVersionDelete ? () => onVersionDelete(vNum) : undefined}
                                  onRevert={onVersionRevert ? () => onVersionRevert(vNum) : undefined}
                                />
                              );
                            })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Index Workspace Button */}
      {onIndexWorkspace && (
        <div className="border-t border-border/50 p-3">
          <Button
            variant={isIndexed ? "outline" : "default"}
            size="sm"
            className="w-full relative overflow-hidden"
            onClick={onIndexWorkspace}
            disabled={isIndexing}
          >
            {/* Progress bar background */}
            {isIndexing && indexProgress > 0 && (
              <div 
                className="absolute inset-0 bg-primary/20 transition-all duration-300"
                style={{ width: `${indexProgress}%` }}
              />
            )}
            <span className="relative flex items-center justify-center">
              {isIndexing ? (
                <>
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  {indexProgress > 0 ? `${indexProgress}%` : "Starting..."}
                </>
              ) : isIndexed ? (
                <>
                  <Check className="mr-2 h-3.5 w-3.5 text-green-500" />
                  Indexed ({indexedChunks})
                </>
              ) : (
                <>
                  <Database className="mr-2 h-3.5 w-3.5" />
                  Index Workspace
                </>
              )}
            </span>
          </Button>
          {isIndexing && indexStatus && (
            <p className="mt-1 text-xs text-muted-foreground text-center break-words" title={indexStatus}>
              {indexStatus}
            </p>
          )}
          {isIndexed && !isIndexing && (
            <p className="mt-1 text-xs text-muted-foreground text-center">
              AI can search {indexedChunks} chunks
            </p>
          )}
        </div>
      )}
    </div>
  );
}
