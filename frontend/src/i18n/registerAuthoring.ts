import i18n from "./index";
import { ruAuthoring, kkAuthoring } from "./authoring";
import "../styles/authoring.css";

// Private workspace resources are loaded with its routes, not the public landing/login bundle.
i18n.addResourceBundle(
  "ru",
  "translation",
  { authoring: ruAuthoring },
  true,
  true,
);
i18n.addResourceBundle(
  "kk",
  "translation",
  { authoring: kkAuthoring },
  true,
  true,
);
