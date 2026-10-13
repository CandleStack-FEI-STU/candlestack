export function PageTitle({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {/* break-words: an error's description can hold a long path or id. */}
      {description && <p className="mt-2 break-words text-muted-foreground">{description}</p>}
    </div>
  );
}
