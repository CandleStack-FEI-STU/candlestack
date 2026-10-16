// The title row of a workspace page (mockups/app, .ttl): 30/36 semibold, a muted line under it,
// 20 px above the page.
export function WorkspaceTitle({ title, lead }: { title: string; lead?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-3xl font-semibold tracking-tight text-balance">{title}</h1>
      {lead && <p className="mt-1 text-muted-foreground">{lead}</p>}
    </div>
  );
}
