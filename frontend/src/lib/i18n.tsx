'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { translations, Language } from '@/locales/translations';

interface LanguageContextType {
    language: Language;
    setLanguage: (lang: Language) => void;
    t: (keyPath: string) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
    const [language, setLanguageState] = useState<Language>(() => {
        if (typeof window === 'undefined') {
            return 'en';
        }
        const storedLang = localStorage.getItem('site_language');
        return storedLang === 'de' || storedLang === 'fr' || storedLang === 'en' ? storedLang : 'en';
    });

    const setLanguage = (lang: Language) => {
        if (typeof document !== 'undefined' && document.startViewTransition) {
            document.startViewTransition(() => {
                setLanguageState(lang);
                localStorage.setItem('site_language', lang);
            });
        } else {
            setLanguageState(lang);
            localStorage.setItem('site_language', lang);
        }
    };

    const t = (keyPath: string): string => {
        const keys = keyPath.split('.');
        let current: unknown = translations[language];

        for (const key of keys) {
            if (
                typeof current !== 'object' ||
                current === null ||
                !(key in (current as Record<string, unknown>))
            ) {
                console.warn(`Translation key not found: ${language}.${keyPath}`);
                return keyPath;
            }
            current = (current as Record<string, unknown>)[key];
        }
        if (typeof current !== 'string') {
            console.warn(`Translation key did not resolve to a string: ${language}.${keyPath}`);
            return keyPath;
        }
        return current;
    };

    return (
        <LanguageContext.Provider value={{ language, setLanguage, t }}>
            {children}
        </LanguageContext.Provider>
    );
}

export function useLanguage() {
    const context = useContext(LanguageContext);
    if (context === undefined) {
        throw new Error('useLanguage must be used within a LanguageProvider');
    }
    return context;
}
