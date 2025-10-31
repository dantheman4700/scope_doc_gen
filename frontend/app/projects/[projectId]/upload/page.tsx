import { requireUser } from "@/lib/auth";
import { UploadFileForm } from "@/components/UploadFileForm";

interface UploadPageProps {
  params: { projectId: string };
}

export const metadata = {
  title: "Upload files · Scope Doc"
};

export default async function UploadPage({ params }: UploadPageProps) {
  await requireUser();

  return (
    <div className="card" style={{ maxWidth: 480 }}>
      <h1>Upload files</h1>
      <UploadFileForm projectId={params.projectId} />
    </div>
  );
}

