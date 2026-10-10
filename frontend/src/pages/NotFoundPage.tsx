import { Link } from '@tanstack/react-router';

import { PageTitle } from '@/components/PageTitle';
import { Button } from '@/components/ui/button';

export function NotFoundPage() {
  return (
    <>
      <PageTitle title="Page not found" description="There is nothing at this address." />
      <Button asChild variant="outline">
        <Link to="/">Back to instruments</Link>
      </Button>
    </>
  );
}
