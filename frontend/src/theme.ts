export type ThemePreference = 'system' | 'light' | 'dark';
export type ColorScheme = 'light' | 'dark';
export const THEME_KEY = 'ca_appearance';
export const THEME_COLORS: Record<ColorScheme, string> = {light: '#edede8', dark: '#161817'};

export function normalizeTheme(value: unknown): ThemePreference {
  return value === 'light' || value === 'dark' ? value : 'system';
}
export function resolveTheme(preference: ThemePreference, systemDark: boolean): ColorScheme {
  return preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;
}
export function readTheme(storage: Pick<Storage, 'getItem'>): ThemePreference {
  try { return normalizeTheme(storage.getItem(THEME_KEY)); } catch { return 'system'; }
}
export function writeTheme(storage: Pick<Storage, 'setItem'>, preference: ThemePreference): void {
  try { storage.setItem(THEME_KEY, preference); } catch { /* Device storage may be unavailable. */ }
}
export function updateDocumentTheme(doc: Document, preference: ThemePreference, systemDark: boolean): ColorScheme {
  const scheme = resolveTheme(preference, systemDark);
  doc.documentElement.dataset.theme = scheme;
  doc.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[scheme]);
  return scheme;
}
