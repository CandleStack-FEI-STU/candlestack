import { useState } from 'react';

import { PageTitle } from '@/components/PageTitle';
import { formatUsage, ModelsGrid, plural, UploadCard, UploadDialog, useModels } from '@/features/models';
import { NewBacktestDialog } from '@/features/workspace';
import { usePageTitle } from '@/lib/usePageTitle';

// What the line under the title says: how many models and the storage they take; why they could
// not load; nothing while they load.
function useDescription(): string | undefined {
  const { data, error } = useModels();
  if (data)
    return `${plural(data.models.length, 'model')} · ${formatUsage(data.usage.used_bytes, data.usage.quota_bytes)} used`;
  return error?.message;
}

// The user's uploaded models (#208, mockups/app ddModels): the title with the Upload card beside
// it, then a tile per model. Backtest with it, after an upload, opens New backtest.
export function ModelsPage() {
  usePageTitle('Models');
  const { data } = useModels();
  const description = useDescription();
  const [backtest, setBacktest] = useState(false);
  return (
    <>
      <PageTitle
        variant="workspace"
        title="Models"
        description={description}
        action={
          <UploadDialog onBacktest={() => setBacktest(true)}>
            <UploadCard className="w-[300px] max-w-full flex-none" />
          </UploadDialog>
        }
      />
      {data && <ModelsGrid models={data.models} />}
      <NewBacktestDialog open={backtest} onOpenChange={setBacktest} />
    </>
  );
}
