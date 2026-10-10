import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useEffect, useRef } from 'react';

import type { Market } from '@/api';
import { useTheme } from '@/theme';

import type { Bar } from './bars';
import { chartTimeZone, crosshairFormatter, tickFormatter } from './time';

// Start loading the older page this many bars before the left edge, so it is there in time.
const PRELOAD_BARS = 30;

type Series = { candles: ISeriesApi<'Candlestick'>; volume: ISeriesApi<'Histogram'> };

// '#089981' at 40%: the volume bars are a softer shade of their candle's color.
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
    // Price levels only: vertical lines on top of the time axis labels add little.
    grid: { vertLines: { visible: false }, horzLines: { color: colors.grid } },
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

type Props = { bars: readonly Bar[]; market: Market; onNearLeftEdge: () => void };

export function CandleChart({ bars, market, onNearLeftEdge }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<{ chart: IChartApi; series: Series } | null>(null);
  const firstTime = useRef<number | undefined>(undefined);
  const nearEdge = useRef(onNearLeftEdge);
  const { theme } = useTheme();

  useEffect(() => {
    nearEdge.current = onNearLeftEdge;
  }, [onNearLeftEdge]);

  // One chart per market (the time zone of the axis); the bars only get replaced.
  useEffect(() => {
    if (!container.current) return;
    const created = create(container.current, market);
    chart.current = created;
    const onRange = (range: LogicalRange | null) => {
      if (range && range.from < PRELOAD_BARS) nearEdge.current();
    };
    created.chart.timeScale().subscribeVisibleLogicalRangeChange(onRange);
    return () => {
      created.chart.remove();
      chart.current = null;
      firstTime.current = undefined;
    };
  }, [market]);

  useEffect(() => {
    const current = chart.current;
    if (!current) return;
    const colors = applyTheme(current.chart, current.series);
    const timeScale = current.chart.timeScale();
    const range = timeScale.getVisibleLogicalRange();
    // Older bars were added on the left: shift the view by as many, so it does not jump.
    const added = firstTime.current === undefined ? 0 : bars.findIndex((bar) => bar.time === firstTime.current);
    setBars(current.series, bars, colors);
    if (range && added > 0) timeScale.setVisibleLogicalRange({ from: range.from + added, to: range.to + added });
    firstTime.current = bars[0]?.time;
  }, [bars, theme, market]);

  // As tall as the screen leaves room for: the header, the instrument info and the switch take
  // about 23rem. Never under 20rem (phones in landscape), never over 60rem (tall monitors).
  return <div ref={container} className="h-[clamp(20rem,calc(100dvh-23rem),60rem)] w-full" />;
}
