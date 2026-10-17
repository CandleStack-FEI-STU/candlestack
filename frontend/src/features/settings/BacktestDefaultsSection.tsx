import { useMutation, useQueryClient, useSuspenseQuery } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';

import { preferencesQueryOptions, saveBacktestDefaults, type DefaultTimeframe } from '@/api';
import { ACCENT_BUTTON, BUTTON_SIZES } from '@/components/buttonStyles';
import { SlidersIcon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';

import { BenchmarkSelect } from './BenchmarkSelect';
import { SettingsCard, SettingsFooter, SettingsRow } from './Card';
import { DirectionCards, PeriodInput, UnitInput, ValueSlider } from './defaultsControls';
import { checkDefaults, formOf, sameDefaults, type DefaultsForm, type TypedField } from './defaultsForm';

const TIMEFRAMES: readonly DefaultTimeframe[] = ['5m', '30m', '1h', '1d'];

type Setter = <K extends keyof DefaultsForm>(key: K) => (value: DefaultsForm[K]) => void;
type FieldsProps = { form: DefaultsForm; set: Setter; invalid: ReadonlySet<TypedField> };

// The card being edited, starting from the saved defaults. Save sends it once something changed
// and every typed field is right; the API's answer becomes the account's defaults.
function useDefaultsForm() {
  const queryClient = useQueryClient();
  const saved = useSuspenseQuery(preferencesQueryOptions()).data.backtest_defaults;
  const [form, setForm] = useState<DefaultsForm>(() => formOf(saved));
  const save = useMutation({
    mutationFn: saveBacktestDefaults,
    onSuccess: (defaults) =>
      queryClient.setQueryData(
        preferencesQueryOptions().queryKey,
        (preferences) => preferences && { ...preferences, backtest_defaults: defaults },
      ),
  });
  const { defaults, invalid } = checkDefaults(form);
  const canSave = defaults !== undefined && !sameDefaults(defaults, saved) && !save.isPending;
  const set: Setter = (key) => (value) => setForm((current) => ({ ...current, [key]: value }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (canSave) save.mutate(defaults);
  };
  return { form, set, invalid, canSave, submit, error: save.error?.message };
}

// What to test: the timeframe and the test period.
function DataRows({ form, set, invalid }: FieldsProps) {
  return (
    <>
      <SettingsRow label="Timeframe">
        <ToggleGroup value={form.timeframe} onValueChange={set('timeframe')} aria-label="Timeframe">
          {TIMEFRAMES.map((timeframe) => (
            <ToggleGroupItem key={timeframe} value={timeframe}>
              {timeframe}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </SettingsRow>
      <SettingsRow label="Test period">
        <div className="flex items-center gap-2">
          <PeriodInput
            label="From"
            value={form.period_start}
            invalid={invalid.has('period_start')}
            onChange={set('period_start')}
          />
          <span className="text-muted-foreground">to</span>
          <PeriodInput
            label="To"
            value={form.period_end}
            invalid={invalid.has('period_end')}
            onChange={set('period_end')}
          />
        </div>
      </SettingsRow>
    </>
  );
}

// How to trade: the direction, the threshold and the stop loss.
function TradeRows({ form, set }: FieldsProps) {
  return (
    <>
      <SettingsRow label="Direction" top>
        <DirectionCards value={form.direction} onChange={set('direction')} />
      </SettingsRow>
      <SettingsRow label="Threshold" hint="Signal strength to trade">
        <ValueSlider
          label="Threshold"
          value={form.threshold}
          min={0}
          max={0.5}
          step={0.01}
          format={(value) => value.toFixed(2)}
          onChange={set('threshold')}
        />
      </SettingsRow>
      <SettingsRow label="Stop loss" hint="Exit when a trade loses this much">
        <ValueSlider
          label="Stop loss"
          value={form.stop_loss_pct}
          min={1}
          max={20}
          step={1}
          format={(value) => `${value} %`}
          onChange={set('stop_loss_pct')}
        />
      </SettingsRow>
    </>
  );
}

// What it costs and what it is measured against.
function CostRows({ form, set, invalid }: FieldsProps) {
  return (
    <>
      <SettingsRow label="Fees">
        <UnitInput
          label="Fees"
          unit="% per side"
          value={form.fees_pct}
          invalid={invalid.has('fees_pct')}
          onChange={set('fees_pct')}
        />
      </SettingsRow>
      <SettingsRow label="Slippage">
        <UnitInput
          label="Slippage"
          unit="%"
          value={form.slippage_pct}
          invalid={invalid.has('slippage_pct')}
          onChange={set('slippage_pct')}
        />
      </SettingsRow>
      <SettingsRow label="Benchmark" hint="What each backtest is measured against">
        <BenchmarkSelect value={form.benchmark} onChange={set('benchmark')} />
      </SettingsRow>
    </>
  );
}

// How a new backtest starts: every control of the design, then Save defaults.
export function BacktestDefaultsSection() {
  const { form, set, invalid, canSave, submit, error } = useDefaultsForm();
  const fields = { form, set, invalid };
  return (
    <SettingsCard
      icon={SlidersIcon}
      title="Backtest defaults"
      aside={<span className="text-xs text-muted-foreground">New backtests start here</span>}
    >
      <form onSubmit={submit} className="contents">
        <DataRows {...fields} />
        <TradeRows {...fields} />
        <CostRows {...fields} />
        <SettingsFooter error={error}>
          <Button type="submit" className={cn(BUTTON_SIZES.sm, ACCENT_BUTTON)} disabled={!canSave}>
            Save defaults
          </Button>
        </SettingsFooter>
      </form>
    </SettingsCard>
  );
}
