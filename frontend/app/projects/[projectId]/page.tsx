import { notFound } from "next/navigation";

import { requireUser } from "@/lib/auth";
import { fetchProject, fetchProjectFiles, fetchProjectRuns } from "@/lib/projects.server";
import ProjectWorkspace from "@/components/ProjectWorkspace";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const revalidate = 0;

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
  
  return (
    <div className="p-6 max-w-7xl mx-auto animate-fade-in">
      <Breadcrumbs
        items={[
          { label: "Projects", href: "/projects" },
          { label: project.name },
        ]}
        className="mb-6"
      />
      <ProjectWorkspace project={project} initialFiles={files} initialRuns={runs} />
    </div>
  );
}
