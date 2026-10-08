import { brand } from '@/brand';
import { cn } from '@/lib/utils';

// Both variants are in the page; CSS shows the one that fits the theme, so it never flickers.
export function Logo({ className }: { className?: string }) {
  return (
    <>
      <img src={brand.logoLight} alt={brand.name} className={cn('h-7 w-auto dark:hidden', className)} />
      <img src={brand.logoDark} alt={brand.name} className={cn('hidden h-7 w-auto dark:block', className)} />
    </>
  );
}
