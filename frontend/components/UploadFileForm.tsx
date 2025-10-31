"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

interface UploadFileFormProps {
  projectId: string;
}

export function UploadFileForm({ projectId }: UploadFileFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);

    const formData = new FormData(event.currentTarget);

    try {
      const response = await fetch(`/api/projects/${projectId}/files`, {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        setError(payload?.detail ?? "Upload failed");
        setBusy(false);
        return;
      }

      router.push(`/projects/${projectId}`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} encType="multipart/form-data">
      <div className="form-field">
        <label htmlFor="files">Select documents</label>
        <input id="files" name="files" type="file" multiple required />
      </div>
      {error ? <p style={{ color: "#dc2626" }}>{error}</p> : null}
      <button className="btn-primary" type="submit" disabled={busy}>
        {busy ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}

