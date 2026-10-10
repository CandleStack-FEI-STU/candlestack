import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { ChevronsRight } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { Market } from '@/api';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/theme';

import type { Bar } from './bars';
import { ChartLegend } from './ChartLegend';
import { legendFor, priceDecimals } from './legend';
import { chartTimeZone, crosshairFormatter, tickFormatter } from './time';

// Start loading the older page this many bars before the left edge, so it is there in time.
const PRELOAD_BARS = 30;
// Further than this from the newest candle, the "go to the latest candle" button shows.
const AWAY_BARS = 3;

type Series = { candles: ISeriesApi<'Candlestick'>; volume: ISeriesApi<'Histogram'> };

// '#43b049' at 40%: the volume bars are a softer shade of their candle's color.
function withAlpha(hex: string, alpha: number): string {
  const value = Number.parseInt(hex.replace('#', ''), 16);
  if (hex.length !== 7 || Number.isNaN(value)) return hex;
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}

// The chart's colors come from the theme in src/index.css, like everything else.
function themeColors() {
  const css = getComputedStyle(document.documentElement);
  const read = (name: string) => css.getPropertyValue(name).trim();
  return { text: read('--muted'), grid: read('--rule'), up: read('--candle-up'), down: read('--candle-down') };
}

function applyTheme(chart: IChartApi, series: Series) {
  const colors = themeColors();
  chart.applyOptions({
    layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: colors.text },
    grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
    rightPriceScale: { borderColor: colors.grid },
    timeScale: { borderColor: colors.grid },
  });
  series.candles.applyOptions({
    upColor: colors.up,
    downColor: colors.down,
    wickUpColor: colors.up,
    wickDownColor: colors.down,
  });
  return colors;
}

function create(container: HTMLElement, market: Market) {
  const zone = chartTimeZone(market);
  const ticks = tickFormatter(zone);
  const crosshair = crosshairFormatter(zone);
  const chart = createChart(container, {
    autoSize: true,
    localization: { timeFormatter: (time: Time) => crosshair(time as number) },
    timeScale: { timeVisible: true, tickMarkFormatter: (time: Time, tick: number) => ticks(time as number, tick) },
  });
  const candles = chart.addSeries(CandlestickSeries, { borderVisible: false });
  const volume = chart.addSeries(HistogramSeries, { priceScaleId: '', priceFormat: { type: 'volume' } });
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
  return { chart, series: { candles, volume } };
}

function setBars(series: Series, bars: readonly Bar[], colors: { up: string; down: string }) {
  series.candles.setData(
    bars.map(({ time, open, high, low, close }) => ({ time: time as UTCTimestamp, open, high, low, close })),
  );
  series.volume.setData(
    bars.map((bar) => ({
      time: bar.time as UTCTimestamp,
      value: bar.volume,
      color: withAlpha(bar.close >= bar.open ? colors.up : colors.down, 0.4),
    })),
  );
}

type Instance = { chart: IChartApi; series: Series };

// The candle under the cursor, by its index in the bars; null when the cursor is off the chart.
function hoveredIndex(event: MouseEventParams): number | null {
  return event.point && event.logical !== undefined ? Math.round(event.logical) : null;
}

// Puts the bars into the chart, in the theme's colors and with enough decimals for the price.
// Older bars added on the left shift the view by as many, so it does not jump. Returns the time
// of the first bar, to compare with on the next call.
function showBars(instance: Instance, bars: readonly Bar[], firstTime: number | undefined) {
  const colors = applyTheme(instance.chart, instance.series);
  const decimals = priceDecimals(bars.at(-1)?.close ?? 0);
  instance.series.candles.applyOptions({
    priceFormat: { type: 'price', precision: decimals, minMove: 10 ** -decimals },
  });
  const timeScale = instance.chart.timeScale();
  const range = timeScale.getVisibleLogicalRange();
  const added = firstTime === undefined ? 0 : bars.findIndex((bar) => bar.time === firstTime);
  setBars(instance.series, bars, colors);
  if (range && added > 0) timeScale.setVisibleLogicalRange({ from: range.from + added, to: range.to + added });
  return bars[0]?.time;
}

// Creates the chart and follows it: loads older pages near the left edge, tracks the candle under
// the cursor for the legend, and whether the newest candle is out of view.
function useCandleChart(market: Market, bars: readonly Bar[], onNearLeftEdge: () => void) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<Instance | null>(null);
  const lastIndex = useRef(-1);
  const firstTime = useRef<number | undefined>(undefined);
  const nearEdge = useRef(onNearLeftEdge);
  const [hovered, setHovered] = useState<number | null>(null);
  const [awayFromLatest, setAwayFromLatest] = useState(false);
  const { theme } = useTheme();

  // loadOlder changes when a fetch ends or a page arrives. It skips while a page is loading, so
  // if the view still sits at the left edge, ask again now: a user who stopped there gets the
  // older page without moving the chart.
  useEffect(() => {
    nearEdge.current = onNearLeftEdge;
    const range = chart.current?.chart.timeScale().getVisibleLogicalRange();
    if (range && range.from < PRELOAD_BARS) onNearLeftEdge();
  }, [onNearLeftEdge]);

  // One chart per market (the time zone of the axis); the bars only get replaced.
  useEffect(() => {
    if (!container.current) return;
    const created = create(container.current, market);
    chart.current = created;
    created.chart.timeScale().subscribeVisibleLogicalRangeChange((range: LogicalRange | null) => {
      if (!range) return;
      if (range.from < PRELOAD_BARS) nearEdge.current();
      setAwayFromLatest(Math.abs(range.to - lastIndex.current) > AWAY_BARS);
    });
    created.chart.subscribeCrosshairMove((event) => setHovered(hoveredIndex(event)));
    return () => {
      created.chart.remove();
      chart.current = null;
      firstTime.current = undefined;
    };
  }, [market]);

  useEffect(() => {
    if (!chart.current) return;
    lastIndex.current = bars.length - 1;
    firstTime.current = showBars(chart.current, bars, firstTime.current);
  }, [bars, theme, market]);

  const scrollToLatest = useCallback(() => chart.current?.chart.timeScale().scrollToRealTime(), []);
  return { container, hovered, awayFromLatest, scrollToLatest };
}

type Props = { bars: readonly Bar[]; market: Market; onNearLeftEdge: () => void };

export function CandleChart({ bars, market, onNearLeftEdge }: Props) {
  const { container, hovered, awayFromLatest, scrollToLatest } = useCandleChart(market, bars, onNearLeftEdge);
  const legend = legendFor(bars, hovered, priceDecimals(bars.at(-1)?.close ?? 0));

  // As tall as the screen leaves room for: the header, the instrument info and the switch take
  // about 23rem. Never under 20rem (phones in landscape), never over 60rem (tall monitors).
  return (
    <div className="relative">
      <div ref={container} className="h-[clamp(20rem,calc(100dvh-23rem),60rem)] w-full" />
      {legend && <ChartLegend legend={legend} />}
      {awayFromLatest && (
        <Button
          variant="outline"
          size="icon-sm"
          className="absolute right-20 bottom-10 z-10"
          aria-label="Go to the latest candle"
          title="Go to the latest candle"
          onClick={scrollToLatest}
        >
          <ChevronsRight />
        </Button>
      )}
    </div>
  );
}
