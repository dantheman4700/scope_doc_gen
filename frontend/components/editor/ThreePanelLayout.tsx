"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { PanelLeftClose, PanelRightClose, PanelLeftOpen, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ThreePanelLayoutProps {
  leftPanel: React.ReactNode;
  centerPanel: React.ReactNode;
  rightPanel: React.ReactNode;
  leftPanelWidth?: number;
  rightPanelWidth?: number;
  className?: string;
}

export function ThreePanelLayout({
  leftPanel,
  centerPanel,
  rightPanel,
  leftPanelWidth = 256,
  rightPanelWidth = 384,
  className,
}: ThreePanelLayoutProps) {
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [isRightCollapsed, setIsRightCollapsed] = useState(false);

  return (
    <div className={cn("flex h-full w-full overflow-hidden", className)}>
      {/* Left Panel - File Explorer */}
      <div
        className={cn(
          "flex flex-col border-r border-border bg-muted/30 transition-all duration-300",
          isLeftCollapsed ? "w-0 overflow-hidden" : ""
        )}
        style={{ width: isLeftCollapsed ? 0 : leftPanelWidth }}
      >
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <span className="text-sm font-medium text-muted-foreground">Files</span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setIsLeftCollapsed(true)}
          >
            <PanelLeftClose className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-auto">
          {leftPanel}
        </div>
      </div>

      {/* Left Panel Toggle (when collapsed) */}
      {isLeftCollapsed && (
        <div className="flex items-start border-r border-border p-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setIsLeftCollapsed(false)}
          >
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Center Panel - Editor */}
      <div className="flex min-w-0 flex-1 flex-col">
        {centerPanel}
      </div>

      {/* Right Panel Toggle (when collapsed) */}
      {isRightCollapsed && (
        <div className="flex items-start border-l border-border p-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setIsRightCollapsed(false)}
          >
            <PanelRightOpen className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Right Panel - Chat */}
      <div
        className={cn(
          "flex flex-col border-l border-border bg-muted/30 transition-all duration-300",
          isRightCollapsed ? "w-0 overflow-hidden" : ""
        )}
        style={{ width: isRightCollapsed ? 0 : rightPanelWidth }}
      >
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <span className="text-sm font-medium text-muted-foreground">AI Assistant</span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setIsRightCollapsed(true)}
          >
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          {rightPanel}
        </div>
      </div>
    </div>
  );
}
