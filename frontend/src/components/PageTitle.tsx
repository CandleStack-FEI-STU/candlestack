export function PageTitle({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {description && <p className="mt-2 text-muted-foreground">{description}</p>}
    </div>
  );
}
