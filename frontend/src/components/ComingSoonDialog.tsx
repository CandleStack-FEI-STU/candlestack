import type { ReactNode } from 'react';

import { ComingSoon } from '@/components/ComingSoon';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

type Props = {
  title: string;
  // What the part will do, one line under the title.
  lead: string;
  // A faint sketch of the part, under the Coming soon tag.
  sketch: ReactNode;
  // The button that opens the dialog.
  children: ReactNode;
};

// What an entry of the app opens while its part is not built yet (mockups/app: New backtest,
// later Compare and a backtest's page): the title, what it will do, and the home page's Coming
// soon card over a sketch of it.
export function ComingSoonDialog({ title, lead, sketch, children }: Props) {
  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <DialogDescription>{lead}</DialogDescription>
          <ComingSoon>{sketch}</ComingSoon>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
