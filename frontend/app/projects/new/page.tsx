import { redirect } from "next/navigation";

import { requireUser } from "@/lib/auth";
import { apiFetchJson } from "@/lib/fetch";
import type { Project } from "@/types/backend";

export const metadata = {
  title: "New project · Scope Doc"
};

export default async function NewProjectPage() {
  await requireUser();

  async function createProject(formData: FormData) {
    "use server";

    const payload = {
      name: (formData.get("name") as string)?.trim(),
      description: (formData.get("description") as string)?.trim() || undefined,
      flags: {}
    };

    const response = await apiFetchJson<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (response.status >= 400 || !response.data) {
      throw new Error("Project creation failed");
    }

    redirect(`/projects/${response.data.id}`);
  }

  return (
    <div className="card" style={{ maxWidth: 520 }}>
      <h1>Create project</h1>
      <form action={createProject}>
        <div className="form-field">
          <label htmlFor="name">Name</label>
          <input id="name" name="name" type="text" required maxLength={200} />
        </div>
        <div className="form-field">
          <label htmlFor="description">Description</label>
          <textarea id="description" name="description" rows={3} />
        </div>
        <button className="btn-primary" type="submit">
          Create project
        </button>
      </form>
    </div>
  );
}

