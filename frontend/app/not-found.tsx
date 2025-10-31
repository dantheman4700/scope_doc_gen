export default function NotFoundPage() {
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem", alignItems: "flex-start" }}>
      <h1>Page not found</h1>
      <p>The page you are looking for doesn&apos;t exist or may have been moved.</p>
      <a className="btn-secondary" href="/projects">
        Back to projects
      </a>
    </div>
  );
}

