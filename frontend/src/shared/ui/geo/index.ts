/**
 * Shared Geo module — public API.
 *
 * Consumers import country data, lookup helpers, and the geo pickers
 * (CountryCombobox, CityCombobox) from `@/shared/ui/geo`. Internal helpers
 * (filterCountries, computeNextFocusedIndex, shouldIssueFetch,
 * fetchCitySearch, enumeration utilities) stay unexported from this
 * barrel — tests import them directly from the component module.
 */

export { CountryCombobox } from "./country-combobox";
export type { CountryComboboxProps } from "./country-combobox";
export { CityCombobox } from "./city-combobox";
export type { CityComboboxProps, CityComboboxValue } from "./city-combobox";
export {
  COUNTRIES,
  findCountryByCode,
  findCountryByName,
} from "./countries";
export type { Country } from "./countries";
