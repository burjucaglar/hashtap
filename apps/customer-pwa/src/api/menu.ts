/**
 * Odoo `/hashtap/menu/<tenant>/<table>` yanıtı.
 * Kaynak: odoo-addons/hashtap_pos/controllers/menu.py
 */
export interface MenuResponse {
  tenant: {
    slug: string;
    name: string;
    currency: string;
    language: 'tr' | 'en';
  };
  table: {
    slug: string;
    label: string;
  };
  categories: MenuCategory[];
}

export interface MenuCategory {
  id: number;
  name: { tr: string; en: string };
  sequence: number;
  items: MenuItem[];
}

export interface MenuItem {
  id: number;
  name: { tr: string; en: string };
  description: { tr: string; en: string };
  image_url: string | null;
  price_kurus: number;
  currency: string;
  vat_rate: number;
  allergens: string[];
  dietary: string[];
  prep_time_minutes: number;
  is_featured: boolean;
  modifier_groups: ModifierGroup[];
}

export interface ModifierGroup {
  id: number;
  name: { tr: string; en: string };
  min_select: number;
  max_select: number;
  modifiers: Modifier[];
}

export interface Modifier {
  id: number;
  name: { tr: string; en: string };
  price_delta_kurus: number;
}

export interface MenuError {
  error: 'tenant_not_found' | 'table_not_found';
}

export async function fetchMenu(
  tenantSlug: string,
  tableSlug: string,
  lang: 'tr' | 'en' = 'tr',
): Promise<MenuResponse> {
  const url = `/hashtap/menu/${encodeURIComponent(tenantSlug)}/${encodeURIComponent(tableSlug)}?lang=${lang}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    let code: MenuError['error'] | 'http_error' = 'http_error';
    try {
      const body = (await res.json()) as MenuError;
      code = body.error ?? code;
    } catch {
      // yutuluyor — HTTP durumu zaten taşıyor bilgiyi
    }
    throw new MenuFetchError(code, res.status);
  }
  return (await res.json()) as MenuResponse;
}

export class MenuFetchError extends Error {
  constructor(
    public readonly code: MenuError['error'] | 'http_error',
    public readonly status: number,
  ) {
    super(`menu fetch failed (${status}): ${code}`);
  }
}
