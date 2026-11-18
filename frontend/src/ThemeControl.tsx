import {useEffect, useState} from 'react';
import {Monitor, Moon, Sun} from 'lucide-react';
import {normalizeTheme, readTheme, writeTheme, updateDocumentTheme, THEME_KEY, type ThemePreference} from './theme';

const systemQuery = '(prefers-color-scheme: dark)';
// Apply before React mounts, including after a reload or account change.
let preference: ThemePreference = readTheme(window.localStorage);
updateDocumentTheme(document, preference, window.matchMedia(systemQuery).matches);

export function ThemeControl() {
  const [value, setValue] = useState<ThemePreference>(() => preference);
  useEffect(() => {
    const media = window.matchMedia(systemQuery);
    const apply = () => updateDocumentTheme(document, preference, media.matches);
    const sync = (event: StorageEvent) => {
      if (event.key !== THEME_KEY && event.key !== null) return;
      if (event.storageArea !== window.localStorage) return;
      preference = readTheme(window.localStorage);
      setValue(preference);
      apply();
    };
    apply();
    media.addEventListener('change', apply);
    window.addEventListener('storage', sync);
    return () => {
      media.removeEventListener('change', apply);
      window.removeEventListener('storage', sync);
    };
  }, []);
  const Icon = value === 'light' ? Sun : value === 'dark' ? Moon : Monitor;
  return <label className="theme-control" title="Appearance">
    <Icon size={16} aria-hidden="true"/>
    <span className="sr-only">Appearance</span>
    <select aria-label="Appearance" value={value} onChange={event => {
      preference = normalizeTheme(event.currentTarget.value);
      writeTheme(window.localStorage, preference);
      setValue(preference);
      updateDocumentTheme(document, preference, window.matchMedia(systemQuery).matches);
    }}>
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  </label>;
}
