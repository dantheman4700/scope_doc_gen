import { requireUser } from "@/lib/auth";
import { fetchProjects } from "@/lib/projects.server";
import { ProjectsList } from "@/components/ProjectsList";

export const metadata = {
  title: "Projects · Scope Doc"
};

export default async function ProjectsPage() {
  await requireUser();
  const projects = await fetchProjects();

  return <ProjectsList initialProjects={projects} />;
}
