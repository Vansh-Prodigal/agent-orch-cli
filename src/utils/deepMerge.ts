/**
 * Recursively deep-merge `overrides` into `base`.
 * Returns a new object — inputs are not mutated.
 */
export function deepMerge<T extends Record<string, unknown>>(
  base: T,
  overrides: Partial<T>,
): T {
  const result = { ...base };

  for (const key of Object.keys(overrides) as (keyof T)[]) {
    const baseVal = result[key];
    const overVal = overrides[key];

    if (
      baseVal &&
      overVal &&
      typeof baseVal === "object" &&
      typeof overVal === "object" &&
      !Array.isArray(baseVal) &&
      !Array.isArray(overVal)
    ) {
      result[key] = deepMerge(
        baseVal as Record<string, unknown>,
        overVal as Record<string, unknown>,
      ) as T[keyof T];
    } else {
      result[key] = overVal as T[keyof T];
    }
  }

  return result;
}
