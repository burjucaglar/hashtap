import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { Plus, ShoppingBag, Receipt } from 'lucide-react';
import {
  fetchMenu,
  MenuFetchError,
  type MenuItem,
  type MenuResponse,
} from '../api/menu.js';
import { useCart } from '../store/cart.js';
import { Layout } from '../components/Layout.js';

type State =
  | { status: 'loading' }
  | { status: 'error'; code: string }
  | { status: 'ready'; data: MenuResponse };

function priceLabel(kurus: number, currency: string) {
  const symbol = currency === 'TRY' ? '₺' : currency;
  return `${(kurus / 100).toLocaleString('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${symbol}`;
}

export function MenuPage() {
  const { tenantSlug, tableId } = useParams<{ tenantSlug: string; tableId: string }>();
  const [state, setState] = useState<State>({ status: 'loading' });
  const setContext = useCart((s) => s.setContext);
  const lineCount = useCart((s) => s.lineCount());
  const totalKurus = useCart((s) => s.totalKurus());
  const recentOrders = useCart((s) => s.recentOrders);
  const activeOrder = recentOrders.find(
    (o) => o.tenantSlug === tenantSlug && o.tableSlug === tableId,
  );

  useEffect(() => {
    if (!tenantSlug || !tableId) return;
    setContext(tenantSlug, tableId);
    let cancelled = false;
    fetchMenu(tenantSlug, tableId)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const code = err instanceof MenuFetchError ? err.code : 'unknown';
        setState({ status: 'error', code });
      });
    return () => {
      cancelled = true;
    };
  }, [tenantSlug, tableId, setContext]);

  if (state.status === 'loading') {
    return (
      <Layout>
        <p className="font-serif italic text-stone-500 text-center pt-16">
          Menü yükleniyor…
        </p>
      </Layout>
    );
  }

  if (state.status === 'error') {
    const message =
      state.code === 'tenant_not_found'
        ? 'Restoran bulunamadı.'
        : state.code === 'table_not_found'
          ? 'Bu masa sistemde kayıtlı değil.'
          : 'Menü yüklenemedi.';
    return (
      <Layout>
        <p className="font-serif italic text-stone-600 text-center pt-16">{message}</p>
      </Layout>
    );
  }

  const { tenant, table, categories } = state.data;

  return (
    <Layout brandName={tenant.name}>
      <section className="text-center pb-8">
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
          className="font-serif italic text-stone-500 text-lg tracking-wide"
        >
          Masa {table.label}
        </motion.p>
        <div className="w-10 h-px bg-stone-300 mx-auto mt-4" />
      </section>

      {categories.length === 0 ? (
        <p className="font-serif italic text-stone-500 text-center pt-8">
          Bu restoran henüz menü yayımlamadı.
        </p>
      ) : (
        <AnimatePresence>
          {categories.map((cat, idx) => (
            <motion.section
              key={cat.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(idx, 6) * 0.05, duration: 0.5 }}
              className="mb-14"
            >
              <div className="mb-6 flex items-baseline justify-between border-b border-stone-400/60 pb-3">
                <h2 className="font-serif italic text-stone-700 text-2xl tracking-wide">
                  {cat.name.tr}
                </h2>
              </div>
              <ul className="space-y-5">
                {cat.items.map((item) => (
                  <MenuItemRow key={item.id} item={item} currency={tenant.currency} />
                ))}
              </ul>
            </motion.section>
          ))}
        </AnimatePresence>
      )}

      {/* Bottom spacer so sticky CTA doesn't cover last items */}
      {(lineCount > 0 || activeOrder) && <div className="h-24" />}

      {lineCount > 0 ? (
        <motion.div
          initial={{ y: 60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="fixed left-1/2 -translate-x-1/2 bottom-4 w-[calc(100%-2rem)] max-w-xl z-50"
        >
          <Link
            to={`/r/${tenantSlug}/t/${tableId}/cart`}
            className="flex items-center justify-between gap-3 bg-stone-900 text-white px-5 py-4 shadow-[0_12px_30px_rgba(0,0,0,0.2)]"
          >
            <span className="flex items-center gap-3">
              <ShoppingBag className="w-4 h-4" />
              <span className="font-serif italic text-lg">{lineCount} kalem</span>
            </span>
            <span className="font-serif text-lg">
              {priceLabel(totalKurus, tenant.currency)}
            </span>
            <span className="text-[10px] tracking-[0.2em] uppercase">Sepet →</span>
          </Link>
        </motion.div>
      ) : activeOrder ? (
        <motion.div
          initial={{ y: 60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="fixed left-1/2 -translate-x-1/2 bottom-4 w-[calc(100%-2rem)] max-w-xl z-50"
        >
          <Link
            to={`/order/${activeOrder.orderId}`}
            className="flex items-center justify-between gap-3 bg-[#c2410c] text-white px-5 py-4 shadow-[0_12px_30px_rgba(0,0,0,0.2)]"
          >
            <span className="flex items-center gap-3">
              <span className="relative inline-flex">
                <Receipt className="w-4 h-4" />
                <span className="absolute -top-2 -right-2 bg-white text-[#c2410c] text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                  1
                </span>
              </span>
              <span className="font-serif italic text-lg">
                Siparişin: {activeOrder.reference}
              </span>
            </span>
            <span className="text-[10px] tracking-[0.2em] uppercase">Durum →</span>
          </Link>
        </motion.div>
      ) : null}
    </Layout>
  );
}

function MenuItemRow({ item, currency }: { item: MenuItem; currency: string }) {
  const addItem = useCart((s) => s.addItem);
  const [added, setAdded] = useState(false);

  const onAdd = () => {
    addItem({
      itemId: item.id,
      nameTr: item.name.tr,
      unitPriceKurus: item.price_kurus,
      modifierIds: [],
      modifierNames: [],
      modifierDeltaKurus: 0,
    });
    setAdded(true);
    window.setTimeout(() => setAdded(false), 900);
  };

  return (
    <li className="flex items-baseline gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline">
          <span className="font-serif text-stone-900 text-lg leading-snug">
            {item.name.tr}
          </span>
          <span className="flex-1 mx-2 border-b border-dotted border-stone-300 translate-y-[-6px]" />
          <span className="font-serif text-stone-700 text-base shrink-0 tracking-wide">
            {priceLabel(item.price_kurus, currency)}
          </span>
        </div>
        {item.description.tr ? (
          <p className="font-serif italic text-[14px] text-stone-500 leading-relaxed mt-1">
            {item.description.tr}
          </p>
        ) : null}
        {item.allergens.length > 0 ? (
          <p className="text-[11px] tracking-[0.12em] uppercase text-stone-400 mt-1">
            Alerjen: {item.allergens.join(' · ')}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onAdd}
        aria-label="Sepete ekle"
        className={`shrink-0 w-9 h-9 flex items-center justify-center border transition-all ${
          added
            ? 'bg-stone-900 border-stone-900 text-white'
            : 'border-stone-400 text-stone-700 hover:bg-stone-900 hover:border-stone-900 hover:text-white'
        }`}
      >
        <Plus className="w-4 h-4" />
      </button>
    </li>
  );
}
