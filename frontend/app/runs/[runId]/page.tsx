import { notFound } from "next/navigation";

import { requireUser } from "@/lib/auth";
import { apiFetchJson } from "@/lib/fetch";
import type { RunStep, RunSummary, Project } from "@/types/backend";
import { RunStatusTracker } from "@/components/RunStatusTracker";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";

export const revalidate = 0;

interface RunPageProps {
  params: { runId: string };
}

export const metadata = {
  title: "Run details · Scope Doc"
};

export default async function RunDetailPage({ params }: RunPageProps) {
  await requireUser();

  const runResponse = await apiFetchJson<RunSummary>(`/runs/${params.runId}`, {
    throwIfUnauthorized: false
  });

  if (runResponse.status === 404 || !runResponse.data) {
    notFound();
  }

  const stepsResponse = await apiFetchJson<RunStep[]>(`/runs/${params.runId}/steps`, {
      throwIfUnauthorized: false
  });

  // Fetch project name for breadcrumbs
  let projectName = "Project";
  if (runResponse.data.project_id) {
    const projectResponse = await apiFetchJson<Project>(`/projects/${runResponse.data.project_id}`, {
      throwIfUnauthorized: false
    });
    if (projectResponse.data) {
      projectName = projectResponse.data.name;
    }
  }

  const steps = stepsResponse.data ?? [];
  const run = runResponse.data;

  return (
    <div className="p-6 max-w-7xl mx-auto animate-fade-in">
      <Breadcrumbs
        items={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${run.project_id}` },
          { label: `Run ${params.runId.slice(0, 8)}…` },
        ]}
        className="mb-6"
      />
      
      <div className="card">
        <RunStatusTracker
          runId={params.runId}
          initialRun={run}
          initialSteps={steps}
        />
      </div>
    </div>
  );
}
