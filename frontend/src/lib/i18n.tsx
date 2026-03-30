'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { translations, Language } from '@/locales/translations';

interface LanguageContextType {
    language: Language;
    setLanguage: (lang: Language) => void;
    t: (keyPath: string) => string | any;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
    const [language, setLanguageState] = useState<Language>('en');

    useEffect(() => {
        // Check local storage on mount
        const storedLang = localStorage.getItem('site_language') as Language;
        if (storedLang && ['en', 'de', 'fr'].includes(storedLang)) {
            setLanguageState(storedLang);
        }
    }, []);

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

    const t = (keyPath: string): string | any => {
        const keys = keyPath.split('.');
        let current: any = translations[language];

        for (const key of keys) {
            if (current[key] === undefined) {
                console.warn(`Translation key not found: ${language}.${keyPath}`);
                return keyPath;
            }
            current = current[key];
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
