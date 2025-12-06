import Link from "next/link";
import { notFound } from "next/navigation";

import { requireUser } from "@/lib/auth";
import { apiFetchJson } from "@/lib/fetch";
import type { RunStep, RunSummary } from "@/types/backend";
import { RunStatusTracker } from "@/components/RunStatusTracker";

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

  const steps = stepsResponse.data ?? [];
  const run = runResponse.data;

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <RunStatusTracker
        runId={params.runId}
        initialRun={run}
        initialSteps={steps}
      />
      <Link href={`/projects/${run.project_id}`} className="btn-secondary" style={{ alignSelf: "flex-start" }}>
        Back to project
      </Link>
    </div>
  );
}

