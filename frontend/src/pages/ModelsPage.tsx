import { WorkspaceTitle } from '@/features/workspace';
import { usePageTitle } from '@/lib/usePageTitle';

// The built-in and uploaded models (#208): the title for now; the usage, the upload and the
// tiles follow.
export function ModelsPage() {
  usePageTitle('Models');
  return <WorkspaceTitle title="Models" />;
}
