import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ja from "./locales/ja.json";
import en from "./locales/en.json";

const STORAGE_KEY = "app-language";
const SUPPORTED_LANGUAGES = ["ja", "en"];

function getInitialLanguage(): string {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && SUPPORTED_LANGUAGES.includes(saved)) return saved;
  } catch {
    // localStorage unavailable
  }

  // First visit: detect from browser language
  const browserLangs = navigator.languages ?? [navigator.language];
  for (const lang of browserLangs) {
    const code = lang.split("-")[0]; // "en-US" → "en"
    if (SUPPORTED_LANGUAGES.includes(code)) return code;
  }

  return "en";
}

i18n.use(initReactI18next).init({
  resources: {
    ja: { translation: ja },
    en: { translation: en },
  },
  lng: getInitialLanguage(),
  fallbackLng: "ja",
  interpolation: {
    escapeValue: false,
  },
});

/** Persist language selection to localStorage. */
i18n.on("languageChanged", (lng) => {
  try {
    localStorage.setItem(STORAGE_KEY, lng);
  } catch {
    // localStorage unavailable — ignore
  }
});

export default i18n;
