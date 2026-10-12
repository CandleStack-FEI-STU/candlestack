// The attributions the chart library and the logo source ask for (docs/frontend.md, Licenses).
export function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-[96rem] flex-wrap gap-x-6 gap-y-1 px-4 py-4 text-xs text-muted-foreground lg:px-8">
        <p>
          Charts by{' '}
          <a href="https://www.tradingview.com/" className="underline underline-offset-2 hover:text-foreground">
            TradingView Lightweight Charts™
          </a>
        </p>
        <p>
          Logos provided by{' '}
          <a href="https://logo.dev" className="underline underline-offset-2 hover:text-foreground">
            Logo.dev
          </a>
        </p>
      </div>
    </footer>
  );
}
