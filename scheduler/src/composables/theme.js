export const aliasStyleToTheme = {
  homelab: "theme-homelab",
  professional: "theme-professional",
  studio: "theme-studio",
};

const ALL_THEMES = ["theme-default", "theme-homelab", "theme-professional", "theme-studio"];

export function applyThemeFromAliasStyle(aliasStyle) {
  const normalized = (aliasStyle || "").toLowerCase();
  const themeClass = aliasStyleToTheme[normalized] || "theme-default";

  const root = document.documentElement;
  ALL_THEMES.forEach(c => root.classList.remove(c));
  root.classList.add(themeClass);

  return themeClass;
}

export function watchThemeClass(onChange) {
  const root = document.documentElement;
  const update = () => {
    const current =
      Array.from(root.classList).find(c => c.startsWith("theme-")) || "theme-default";
    onChange?.(current);
  };
  update();
  const observer = new MutationObserver(update);
  observer.observe(root, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}
