export type Page =
  | "home"
  | "products"
  | "refurbished"
  | "software"
  | "support"
  | "solutions"
  | "help-me-choose"
  | "cart"
  | "checkout"
  | "quote"
  | "track-quote"
  | "track-order";

export type NavigationData = Record<string, string | number | boolean>;
export type Navigate = (page: Page, data?: NavigationData) => void;
