import { notFound } from "next/navigation";

import { requireUser } from "@/lib/auth";
import { fetchProject, fetchProjectFiles, fetchProjectRuns } from "@/lib/projects.server";
import ProjectWorkspace from "@/components/ProjectWorkspace";

interface ProjectDetailPageProps {
  params: { projectId: string };
}

export const metadata = {
  title: "Project · Scope Doc"
};

export default async function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  await requireUser();
  const project = await fetchProject(params.projectId);
  if (!project) {
    notFound();
  }
  const projectId = project.id;

  const [files, runs] = await Promise.all([
    fetchProjectFiles(projectId),
    fetchProjectRuns(projectId)
  ]);
  return <ProjectWorkspace project={project} initialFiles={files} initialRuns={runs} />;
}

