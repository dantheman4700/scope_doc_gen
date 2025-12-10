"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { CreateProjectModal } from "@/components/CreateProjectModal";
import type { Project, Team } from "@/types/backend";

interface ProjectsListProps {
  initialProjects: Project[];
}

export function ProjectsList({ initialProjects }: ProjectsListProps) {
  const [projects] = useState<Project[]>(initialProjects);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamFilter, setSelectedTeamFilter] = useState<string>("all");

  // Extract unique teams from projects
  useEffect(() => {
    const uniqueTeams = new Map<string, Team>();
    projects.forEach((p) => {
      if (p.team) {
        uniqueTeams.set(p.team.id, p.team as Team);
      }
    });
    setTeams(Array.from(uniqueTeams.values()));
    
    // Load saved filter from localStorage
    const savedFilter = localStorage.getItem("projects-team-filter");
    if (savedFilter) {
      setSelectedTeamFilter(savedFilter);
    }
  }, [projects]);

  // Save filter to localStorage
  useEffect(() => {
    localStorage.setItem("projects-team-filter", selectedTeamFilter);
  }, [selectedTeamFilter]);

  const filteredProjects = useMemo(() => {
    if (selectedTeamFilter === "all") return projects;
    if (selectedTeamFilter === "personal") return projects.filter((p) => !p.team);
    return projects.filter((p) => p.team?.id === selectedTeamFilter);
  }, [projects, selectedTeamFilter]);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto animate-fade-in">
      <div className="card">
        <div className="flex justify-between items-start gap-6 flex-wrap">
          <div>
            <h1 className="text-2xl font-semibold mb-2">Projects</h1>
            <p className="text-muted-foreground">
              Review discovery inputs, launch new scope runs, and manage generated artifacts.
            </p>
          </div>
          <CreateProjectModal />
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        {/* Filter bar */}
        <div className="flex items-center gap-4 p-4 border-b border-border bg-muted/30">
          <span className="text-sm font-medium text-muted-foreground">Filter by team:</span>
          <select
            value={selectedTeamFilter}
            onChange={(e) => setSelectedTeamFilter(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="all">All teams ({projects.length})</option>
            <option value="personal">Personal ({projects.filter((p) => !p.team).length})</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name} ({projects.filter((p) => p.team?.id === team.id).length})
              </option>
            ))}
          </select>
          {selectedTeamFilter !== "all" && (
            <button
              onClick={() => setSelectedTeamFilter("all")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Clear filter
            </button>
          )}
        </div>

        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Team</th>
              <th>Created by</th>
              <th>Last updated</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {filteredProjects.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-12">
                  <div className="flex flex-col items-center gap-3">
                    <span className="text-4xl">📁</span>
                    <p className="text-muted-foreground">
                      {selectedTeamFilter === "all" 
                        ? "No projects yet" 
                        : "No projects in this team"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {selectedTeamFilter === "all"
                        ? "Create your first project to get started"
                        : "Create a new project or change the filter"}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              filteredProjects.map((project) => (
                <tr key={project.id} className="group">
                  <td>
                    <Link 
                      href={`/projects/${project.id}`}
                      className="font-medium text-foreground hover:text-primary transition-colors"
                    >
                      {project.name}
                    </Link>
                  </td>
                  <td>
                    {project.team ? (
                      <Badge variant="secondary" className="text-xs">
                        {project.team.name}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-sm">Personal</span>
                    )}
                  </td>
                  <td className="text-sm text-muted-foreground">
                    {project.owner?.email ?? "—"}
                  </td>
                  <td className="text-sm text-muted-foreground">
                    {new Date(project.updated_at).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </td>
                  <td className="text-sm text-muted-foreground max-w-xs truncate">
                    {project.description || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ProjectsList;

