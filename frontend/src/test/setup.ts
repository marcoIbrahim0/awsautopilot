import '@testing-library/jest-dom/vitest';

function createStorageMock(): Storage {
  const store = new Map<string, string>();

  return {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    key(index: number) {
      return [...store.keys()][index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  } as Storage;
}

if (typeof window !== 'undefined') {
  const candidate = window.localStorage as Partial<Storage> | undefined;
  const hasFullStorageApi =
    typeof candidate?.getItem === 'function' &&
    typeof candidate?.setItem === 'function' &&
    typeof candidate?.removeItem === 'function' &&
    typeof candidate?.clear === 'function';

  if (!hasFullStorageApi) {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: createStorageMock(),
    });
  }
}
