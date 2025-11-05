import Link from "next/link";

import { CreateProjectModal } from "@/components/CreateProjectModal";
import { requireUser } from "@/lib/auth";
import { fetchProjects } from "@/lib/projects.server";

export const metadata = {
  title: "Projects · Scope Doc"
};

export default async function ProjectsPage() {
  await requireUser();
  const projects = await fetchProjects();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1.5rem" }}>
          <div>
            <h1>Projects</h1>
            <p>Review discovery inputs, launch new scope runs, and manage generated artifacts.</p>
          </div>
          <CreateProjectModal />
        </div>
      </div>
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Created by</th>
              <th>Last updated</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {projects.length === 0 ? (
              <tr>
                <td colSpan={4}>No projects yet</td>
              </tr>
            ) : (
              projects.map((project) => (
                <tr key={project.id}>
                  <td>
                    <Link href={`/projects/${project.id}`}>{project.name}</Link>
                  </td>
                  <td>{project.owner?.email ?? "—"}</td>
                  <td>{new Date(project.updated_at).toLocaleString()}</td>
                  <td>{project.description ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

