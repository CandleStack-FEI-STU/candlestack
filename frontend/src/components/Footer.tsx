// The attributions the chart library and the logo source ask for (docs/frontend.md, Licenses).
const credits = [
  { text: 'Charts by', name: 'TradingView Lightweight Charts™', href: 'https://www.tradingview.com/' },
  { text: 'Logos provided by', name: 'Logo.dev', href: 'https://logo.dev' },
];

export function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-[96rem] flex-wrap gap-x-6 gap-y-1 px-4 py-4 text-xs text-muted-foreground lg:px-8">
        {credits.map(({ text, name, href }) => (
          <p key={href}>
            {text} {/* A new tab, so following a credit does not lose the chart the user is looking at. */}
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:text-foreground"
            >
              {name}
            </a>
          </p>
        ))}
      </div>
    </footer>
  );
}
