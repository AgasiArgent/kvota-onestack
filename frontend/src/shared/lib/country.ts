/**
 * country.ts — russian/english country name → ISO 3166-1 alpha-2 lookup.
 *
 * Why an application-layer map (not a DB column):
 *   - Unicode adds new flags over time; rebuilding a map is cheaper than
 *     migrating a `flag_emoji` column across thousands of locations rows.
 *   - The `locations.country` column stores free-form names (historically
 *     russian), so we need client-side normalization regardless.
 *
 * Keep this list focused on countries the team actually works with.
 * Unknown names return undefined; callers should fall back to a neutral
 * globe glyph or hide the flag.
 */

const RAW: Array<[string, string[]]> = [
  ["CN", ["китай", "china", "cn"]],
  ["RU", ["россия", "russia", "rossiya", "рф", "ru"]],
  ["TR", ["турция", "turkey", "türkiye", "tr"]],
  ["IN", ["индия", "india", "in"]],
  ["IT", ["италия", "italy", "italia", "it"]],
  ["DE", ["германия", "germany", "deutschland", "de"]],
  ["KZ", ["казахстан", "kazakhstan", "kz"]],
  ["BY", ["беларусь", "belarus", "by"]],
  ["US", ["сша", "usa", "united states", "us"]],
  ["KR", ["южная корея", "south korea", "korea", "republic of korea", "kr"]],
  ["JP", ["япония", "japan", "jp"]],
  ["VN", ["вьетнам", "vietnam", "viet nam", "vn"]],
  ["TH", ["таиланд", "thailand", "th"]],
  ["ID", ["индонезия", "indonesia", "id"]],
  ["MY", ["малайзия", "malaysia", "my"]],
  ["SG", ["сингапур", "singapore", "sg"]],
  ["AE", ["оаэ", "uae", "united arab emirates", "ae", "эмираты"]],
  ["UZ", ["узбекистан", "uzbekistan", "uz"]],
  ["KG", ["киргизия", "kyrgyzstan", "кыргызстан", "kg"]],
  ["AM", ["армения", "armenia", "am"]],
  ["AZ", ["азербайджан", "azerbaijan", "az"]],
  ["GE", ["грузия", "georgia", "ge"]],
  ["PL", ["польша", "poland", "pl"]],
  ["CZ", ["чехия", "czech republic", "czechia", "cz"]],
  ["FR", ["франция", "france", "fr"]],
  ["ES", ["испания", "spain", "es"]],
  ["NL", ["нидерланды", "netherlands", "holland", "nl"]],
  ["BE", ["бельгия", "belgium", "be"]],
  ["AT", ["австрия", "austria", "at"]],
  ["CH", ["швейцария", "switzerland", "ch"]],
  ["UK", ["великобритания", "united kingdom", "uk", "britain", "england", "gb"]],
  ["FI", ["финляндия", "finland", "fi"]],
  ["SE", ["швеция", "sweden", "se"]],
  ["NO", ["норвегия", "norway", "no"]],
  ["BR", ["бразилия", "brazil", "br"]],
  ["MX", ["мексика", "mexico", "mx"]],
  ["CA", ["канада", "canada", "ca"]],
  ["AU", ["австралия", "australia", "au"]],
  ["IL", ["израиль", "israel", "il"]],
  ["EG", ["египет", "egypt", "eg"]],
  ["ZA", ["юар", "south africa", "za"]],
];

const LOOKUP: Map<string, string> = (() => {
  const m = new Map<string, string>();
  for (const [iso2, aliases] of RAW) {
    m.set(iso2.toLowerCase(), iso2);
    for (const alias of aliases) m.set(alias.toLowerCase(), iso2);
  }
  return m;
})();

/**
 * Resolve a country name to its ISO 3166-1 alpha-2 code.
 * Returns undefined for unknown inputs. Case-insensitive.
 */
export function countryNameToIso2(name: string | null | undefined): string | undefined {
  if (!name) return undefined;
  return LOOKUP.get(name.trim().toLowerCase());
}
