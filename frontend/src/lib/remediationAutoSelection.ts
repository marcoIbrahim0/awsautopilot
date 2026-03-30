import type {
  RemediationOption,
  RemediationOptionsResponse,
  StrategyInputSchemaField,
} from '@/lib/api';
import { allowsDeterministicAlternateGeneration } from '@/lib/remediationOptionSupport';

export type AutoPrOnlySelectionResult =
  | {
      ok: true;
      strategy: RemediationOption | null;
      strategyId?: string;
      strategyInputs: Record<string, unknown>;
    }
  | {
      ok: false;
      message: string;
      strategy: RemediationOption | null;
    };

export function stringifyDefaultValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return '';
}

export function parseBooleanInput(rawValue: string): boolean | undefined {
  if (rawValue === 'true') return true;
  if (rawValue === 'false') return false;
  return undefined;
}

function parseNumberInput(rawValue: string): number | undefined {
  if (!rawValue.trim()) return undefined;
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function resolveRawFieldValue(
  field: StrategyInputSchemaField,
  rawValues: Record<string, string>,
): string {
  if (rawValues[field.key] !== undefined) {
    return rawValues[field.key];
  }
  return stringifyDefaultValue(field.default_value);
}

export function resolveSafeDefaultValue(
  field: StrategyInputSchemaField,
  accountId: string,
  region?: string | null,
  detectedPublicIpv4Cidr?: string | null,
): string {
  if (field.safe_default_value === undefined || field.safe_default_value === null) {
    return '';
  }
  let value = stringifyDefaultValue(field.safe_default_value);
  if (!value) return '';
  value = value
    .split('{{account_id}}')
    .join(accountId.trim())
    .split('{{region}}')
    .join((region ?? '').trim())
    .split('{{detected_public_ipv4_cidr}}')
    .join((detectedPublicIpv4Cidr ?? '').trim())
    .trim();
  return /{{[^}]+}}/.test(value) ? '' : value;
}

function matchesVisibleWhen(actual: unknown, expected: unknown): boolean {
  if (Array.isArray(expected)) {
    return expected.some((item) => matchesVisibleWhen(actual, item));
  }
  if (typeof expected === 'boolean' || typeof expected === 'number') {
    return actual === expected;
  }
  return String(actual ?? '').trim() === String(expected ?? '').trim();
}

export function isFieldVisible(
  field: StrategyInputSchemaField,
  rawValues: Record<string, string>,
  allFields: StrategyInputSchemaField[],
): boolean {
  if (!field.visible_when) return true;
  const dependencyField = allFields.find((item) => item.key === field.visible_when?.field);
  if (!dependencyField) return false;
  const dependencyRawValue = resolveRawFieldValue(dependencyField, rawValues);
  if (dependencyField.type === 'boolean') {
    return matchesVisibleWhen(parseBooleanInput(dependencyRawValue), field.visible_when.equals);
  }
  if (dependencyField.type === 'number') {
    return matchesVisibleWhen(parseNumberInput(dependencyRawValue), field.visible_when.equals);
  }
  return matchesVisibleWhen(dependencyRawValue.trim(), field.visible_when.equals);
}

function coerceFieldValue(field: StrategyInputSchemaField, rawValue: string): unknown {
  if (field.type === 'string_array') {
    const values = rawValue
      .split(/[\n,]/)
      .map((value) => value.trim())
      .filter((value, index, self) => value.length > 0 && self.indexOf(value) === index);
    return values.length > 0 ? values : undefined;
  }
  if (field.type === 'boolean') {
    return parseBooleanInput(rawValue.trim());
  }
  if (field.type === 'number') {
    return parseNumberInput(rawValue.trim());
  }
  const trimmed = rawValue.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function buildInitialStrategyInputValues(
  strategy: RemediationOption | null,
  detectedPublicIpv4Cidr?: string | null,
): Record<string, string> {
  if (!strategy) return {};
  const values: Record<string, string> = {};
  const fields = strategy.input_schema?.fields ?? [];
  for (const field of fields) {
    if (field.default_value !== undefined) {
      values[field.key] = stringifyDefaultValue(field.default_value);
      continue;
    }
    if (field.type === 'select' && field.options && field.options.length > 0) {
      values[field.key] = field.options[0].value;
    }
  }
  return applyContextDefaults(strategy, values, fields, detectedPublicIpv4Cidr);
}

function applyContextDefaults(
  strategy: RemediationOption,
  rawValues: Record<string, string>,
  fields: StrategyInputSchemaField[],
  detectedPublicIpv4Cidr?: string | null,
): Record<string, string> {
  const values = { ...rawValues };
  const contextualDefaults = strategy.context?.default_inputs;
  if (contextualDefaults && typeof contextualDefaults === 'object' && !Array.isArray(contextualDefaults)) {
    for (const field of fields) {
      const contextualValue = (contextualDefaults as Record<string, unknown>)[field.key];
      if (contextualValue === undefined || contextualValue === null) continue;
      applyContextDefaultValue(field, contextualValue, values);
    }
  }
  if (strategy.strategy_id === 'sg_restrict_public_ports_guided' && detectedPublicIpv4Cidr && !values.allowed_cidr) {
    values.allowed_cidr = detectedPublicIpv4Cidr;
  }
  return values;
}

function applySelectContextDefault(
  field: StrategyInputSchemaField,
  contextualValue: unknown,
  values: Record<string, string>,
): boolean {
  const normalized = stringifyDefaultValue(contextualValue).trim();
  const optionValues = new Set((field.options ?? []).map((option) => option.value));
  if (!normalized || !optionValues.has(normalized)) return false;
  values[field.key] = normalized;
  return true;
}

function applyTypedContextDefault(
  field: StrategyInputSchemaField,
  contextualValue: unknown,
  values: Record<string, string>,
): boolean {
  if (field.type === 'boolean' && typeof contextualValue === 'boolean') {
    values[field.key] = contextualValue ? 'true' : 'false';
    return true;
  }
  if (field.type === 'number' && typeof contextualValue === 'number' && Number.isFinite(contextualValue)) {
    values[field.key] = String(contextualValue);
    return true;
  }
  return false;
}

function applyContextDefaultValue(
  field: StrategyInputSchemaField,
  contextualValue: unknown,
  values: Record<string, string>,
): void {
  if (field.type === 'select' && applySelectContextDefault(field, contextualValue, values)) return;
  if (applyTypedContextDefault(field, contextualValue, values)) return;
  const normalized = stringifyDefaultValue(contextualValue);
  if (normalized) values[field.key] = normalized;
}

export function buildStrategyInputs(
  strategy: RemediationOption | null,
  rawValues: Record<string, string>,
): Record<string, unknown> {
  if (!strategy) return {};
  const fields = strategy.input_schema?.fields ?? [];
  const result: Record<string, unknown> = {};
  for (const field of fields) {
    if (!isFieldVisible(field, rawValues, fields)) continue;
    const rawValue = resolveRawFieldValue(field, rawValues);
    const coercedValue = coerceFieldValue(field, rawValue);
    if (coercedValue !== undefined) {
      result[field.key] = coercedValue;
    }
  }
  return result;
}

export function missingRequiredInputFields(
  strategy: RemediationOption | null,
  rawValues: Record<string, string>,
): string[] {
  if (!strategy) return [];
  const missing: string[] = [];
  const fields = strategy.input_schema?.fields ?? [];
  for (const field of fields) {
    if (!field.required || !isFieldVisible(field, rawValues, fields)) continue;
    const rawValue = resolveRawFieldValue(field, rawValues);
    const coercedValue = coerceFieldValue(field, rawValue);
    if (coercedValue === undefined || (Array.isArray(coercedValue) && coercedValue.length === 0)) {
      missing.push(field.key);
    }
  }
  return missing;
}

export function selectInitialStrategyForMode(
  strategies: RemediationOption[],
  mode: 'pr_only' | 'direct_fix',
): RemediationOption | null {
  const modeStrategies = strategies.filter((strategy) => strategy.mode === mode);
  if (modeStrategies.length === 0) return null;
  const nonExceptionStrategies = modeStrategies.filter((strategy) => !strategy.exception_only);
  const recommended = nonExceptionStrategies.find((strategy) => strategy.recommended);
  return recommended ?? nonExceptionStrategies[0] ?? modeStrategies[0] ?? null;
}

function selectPreferredPrOnlyStrategy(strategies: RemediationOption[]): RemediationOption | null {
  const candidates = strategies.filter((strategy) => strategy.mode === 'pr_only' && !strategy.exception_only);
  if (candidates.length === 0) return null;
  return candidates.find((strategy) => strategy.recommended) ?? candidates[0] ?? null;
}

function applyDerivableSafeDefaults(
  strategy: RemediationOption,
  rawValues: Record<string, string>,
  accountId: string,
  region?: string | null,
  detectedPublicIpv4Cidr?: string | null,
): Record<string, string> {
  const fields = strategy.input_schema?.fields ?? [];
  const values = { ...rawValues };
  for (let index = 0; index < fields.length; index += 1) {
    let applied = false;
    for (const field of fields) {
      if (!isFieldVisible(field, values, fields)) continue;
      if (coerceFieldValue(field, resolveRawFieldValue(field, values)) !== undefined) continue;
      const safeDefault = resolveSafeDefaultValue(field, accountId, region, detectedPublicIpv4Cidr);
      if (!safeDefault) continue;
      values[field.key] = safeDefault;
      applied = true;
    }
    if (!applied) break;
  }
  return values;
}

function summarizeChecks(strategy: RemediationOption, statuses: Array<'fail' | 'warn' | 'unknown'>): string {
  const messages = strategy.dependency_checks
    .filter((check) => (statuses as string[]).includes(check.status))
    .map((check) => check.message.trim())
    .filter(Boolean);
  return messages.join(' ');
}

function failSelection(message: string, strategy: RemediationOption | null): AutoPrOnlySelectionResult {
  return { ok: false, message, strategy };
}

function supportsPrOnlyMode(options: RemediationOptionsResponse): boolean {
  return options.mode_options.includes('pr_only');
}

function validateAutoRunnableStrategy(strategy: RemediationOption): AutoPrOnlySelectionResult | null {
  const hasFailingChecks = strategy.dependency_checks.some((check) => check.status === 'fail');
  if (hasFailingChecks && !allowsDeterministicAlternateGeneration(strategy)) {
    return failSelection(summarizeChecks(strategy, ['fail']), strategy);
  }
  if (strategy.dependency_checks.some((check) => check.status === 'warn' || check.status === 'unknown')) {
    const message = summarizeChecks(strategy, ['warn', 'unknown']);
    return failSelection(`Manual review required before auto-run. ${message}`.trim(), strategy);
  }
  return null;
}

function buildDerivedStrategyInputs(
  strategy: RemediationOption,
  accountId: string,
  region?: string | null,
  detectedPublicIpv4Cidr?: string | null,
): AutoPrOnlySelectionResult {
  const initialValues = buildInitialStrategyInputValues(strategy, detectedPublicIpv4Cidr);
  const rawValues = applyDerivableSafeDefaults(strategy, initialValues, accountId, region, detectedPublicIpv4Cidr);
  const missingFields = missingRequiredInputFields(strategy, rawValues);
  if (missingFields.length > 0) {
    return failSelection(
      `Required strategy inputs are not safely derivable: ${missingFields.join(', ')}.`,
      strategy,
    );
  }
  return {
    ok: true,
    strategy,
    strategyId: strategy.strategy_id,
    strategyInputs: buildStrategyInputs(strategy, rawValues),
  };
}

export function deriveAutoPrOnlySelection(
  options: RemediationOptionsResponse,
  accountId: string,
  region?: string | null,
  detectedPublicIpv4Cidr?: string | null,
): AutoPrOnlySelectionResult {
  if (!supportsPrOnlyMode(options)) return failSelection('PR bundle mode is not available for this action.', null);
  if (options.manual_workflow?.manual_only) return failSelection(options.manual_workflow.summary, null);
  if (options.strategies.length === 0) return { ok: true, strategy: null, strategyInputs: {} };
  const strategy = selectPreferredPrOnlyStrategy(options.strategies);
  if (!strategy) return failSelection('No non-exception PR bundle strategy is available.', null);
  const validationFailure = validateAutoRunnableStrategy(strategy);
  if (validationFailure) return validationFailure;
  return buildDerivedStrategyInputs(strategy, accountId, region, detectedPublicIpv4Cidr);
}
