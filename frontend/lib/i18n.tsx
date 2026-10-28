"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

/*
 * Localization framework. English is the source language; other languages fall back to English
 * key-by-key, so a partially translated language never shows blank text. Add a language by adding
 * a dictionary here and its code to the backend's LANGUAGES list.
 * Hindi strings are UI copy only and need review by a native speaker before launch.
 */
const en = {
  "brand.tagline": "Understand your rights. Prepare with confidence.",
  "nav.home": "Home",
  "nav.ask": "Ask AI",
  "nav.rights": "My Legal Rights",
  "nav.advocate": "AI Advocate",
  "nav.lawyer": "AI Lawyer",
  "nav.judge": "AI Judge",
  "nav.documents": "Document Studio",
  "nav.findLawyer": "Find a Lawyer",
  "nav.legalAid": "Legal Aid",
  "nav.cases": "My Cases",
  "nav.library": "Legal Library",
  "nav.settings": "Settings",
  "nav.admin": "Admin console",
  "nav.menu": "Menu",
  "nav.skip": "Skip to main content",
  "auth.signIn": "Sign in",
  "auth.signOut": "Sign out",
  "auth.register": "Create account",
  "auth.email": "Email address",
  "auth.password": "Password",
  "auth.displayName": "Your name (optional)",
  "auth.noAccount": "New to JUSTICE AI?",
  "auth.haveAccount": "Already have an account?",
  "home.title": "Legal help that explains, not intimidates",
  "home.lead":
    "JUSTICE AI helps you understand your rights under Indian law, organise your situation and prepare to speak with a qualified lawyer.",
  "home.understand": "Understand Your Rights",
  "home.ask": "Ask a Legal Question",
  "home.prepare": "Prepare My Case",
  "home.review": "Review a Document",
  "home.analyse": "Analyse Both Sides",
  "home.find": "Find a Lawyer",
  "home.aid": "Get Legal Aid",
  "disclaimer.short":
    "JUSTICE AI provides legal information, not legal advice. It is not a lawyer, advocate or court. For decisions about your matter, consult a qualified advocate.",
  "emergency.banner": "In immediate danger? Call 112 (India's national emergency number).",
  "status.comingPhase": "Not available yet",
  "settings.title": "Settings",
  "cases.title": "My Cases",
  "admin.title": "Admin console",
  "lang.label": "Language",
};

type Key = keyof typeof en;

const hi: Partial<Record<Key, string>> = {
  "brand.tagline": "अपने अधिकार समझें। आत्मविश्वास के साथ तैयारी करें।",
  "nav.home": "मुख्य पृष्ठ",
  "nav.ask": "AI से पूछें",
  "nav.rights": "मेरे कानूनी अधिकार",
  "nav.advocate": "AI एडवोकेट",
  "nav.lawyer": "AI वकील",
  "nav.judge": "AI जज",
  "nav.documents": "दस्तावेज़ स्टूडियो",
  "nav.findLawyer": "वकील खोजें",
  "nav.legalAid": "कानूनी सहायता",
  "nav.cases": "मेरे मामले",
  "nav.library": "कानूनी पुस्तकालय",
  "nav.settings": "सेटिंग्स",
  "nav.admin": "एडमिन कंसोल",
  "nav.menu": "मेनू",
  "nav.skip": "मुख्य सामग्री पर जाएँ",
  "auth.signIn": "साइन इन करें",
  "auth.signOut": "साइन आउट करें",
  "auth.register": "खाता बनाएँ",
  "auth.email": "ईमेल पता",
  "auth.password": "पासवर्ड",
  "auth.displayName": "आपका नाम (वैकल्पिक)",
  "auth.noAccount": "JUSTICE AI पर नए हैं?",
  "auth.haveAccount": "पहले से खाता है?",
  "home.title": "कानूनी मदद जो समझाए, डराए नहीं",
  "home.lead":
    "JUSTICE AI भारतीय कानून के तहत आपके अधिकार समझने, आपकी स्थिति को व्यवस्थित करने और किसी योग्य वकील से बात करने की तैयारी में आपकी मदद करता है।",
  "home.understand": "अपने अधिकार समझें",
  "home.ask": "कानूनी प्रश्न पूछें",
  "home.prepare": "मेरा मामला तैयार करें",
  "home.review": "दस्तावेज़ की समीक्षा करें",
  "home.analyse": "दोनों पक्षों का विश्लेषण",
  "home.find": "वकील खोजें",
  "home.aid": "कानूनी सहायता पाएँ",
  "disclaimer.short":
    "JUSTICE AI कानूनी जानकारी देता है, कानूनी सलाह नहीं। यह वकील, एडवोकेट या अदालत नहीं है। अपने मामले से जुड़े निर्णयों के लिए किसी योग्य एडवोकेट से परामर्श करें।",
  "emergency.banner": "तुरंत खतरे में हैं? 112 पर कॉल करें (भारत का राष्ट्रीय आपातकालीन नंबर)।",
  "status.comingPhase": "अभी उपलब्ध नहीं",
  "settings.title": "सेटिंग्स",
  "cases.title": "मेरे मामले",
  "admin.title": "एडमिन कंसोल",
  "lang.label": "भाषा",
};

const dictionaries: Record<string, Partial<Record<Key, string>>> = { en, hi };
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
];

type Ctx = { lang: string; setLang: (l: string) => void; t: (k: Key) => string };
const I18nContext = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (k) => en[k] });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("justice_lang");
      if (saved && dictionaries[saved]) setLangState(saved);
    } catch {}
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: string) => {
    if (!dictionaries[l]) return;
    setLangState(l);
    try {
      localStorage.setItem("justice_lang", l);
    } catch {}
  }, []);

  const t = useCallback((k: Key) => dictionaries[lang]?.[k] ?? en[k], [lang]);
  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);
