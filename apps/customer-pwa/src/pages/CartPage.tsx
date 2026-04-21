import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { Minus, Plus, Trash2, ArrowLeft } from 'lucide-react';
import { useCart } from '../store/cart.js';
import { createOrder, OrderError } from '../api/order.js';
import { Layout } from '../components/Layout.js';

function fmt(kurus: number) {
  return `${(kurus / 100).toLocaleString('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₺`;
}

export function CartPage() {
  const { tenantSlug, tableId } = useParams<{ tenantSlug: string; tableId: string }>();
  const navigate = useNavigate();
  const lines = useCart((s) => s.lines);
  const increment = useCart((s) => s.incrementLine);
  const decrement = useCart((s) => s.decrementLine);
  const remove = useCart((s) => s.removeLine);
  const clear = useCart((s) => s.clear);
  const rememberOrder = useCart((s) => s.rememberOrder);
  const totalKurus = useCart((s) => s.totalKurus());

  const [note, setNote] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (lines.length === 0) {
    return (
      <Layout>
        <h1 className="font-serif italic text-4xl text-stone-900 text-center mb-6">
          Sepet
        </h1>
        <p className="font-serif italic text-stone-500 text-center">Sepetin boş.</p>
        <div className="text-center mt-8">
          <Link
            to={`/r/${tenantSlug}/t/${tableId}`}
            className="inline-flex items-center gap-2 text-[11px] tracking-[0.18em] uppercase text-stone-600 hover:text-stone-900 border border-stone-300 px-4 py-2"
          >
            <ArrowLeft className="w-3 h-3" /> Menüye dön
          </Link>
        </div>
      </Layout>
    );
  }

  const submit = async () => {
    if (!tenantSlug || !tableId) return;
    setSending(true);
    setError(null);
    try {
      const order = await createOrder({
        tenantSlug,
        tableSlug: tableId,
        items: lines.map((l) => ({
          itemId: l.itemId,
          quantity: l.quantity,
          modifierIds: l.modifierIds,
          note: l.note,
        })),
        customerNote: note,
      });
      rememberOrder({
        orderId: order.id,
        reference: order.reference,
        tenantSlug,
        tableSlug: tableId,
        createdAt: order.created_at ?? new Date().toISOString(),
      });
      clear();
      navigate(`/r/${tenantSlug}/t/${tableId}/pay?order=${order.id}`);
    } catch (err) {
      const code = err instanceof OrderError ? err.code : 'unknown';
      if (code === 'item_not_found' || code === 'modifier_not_allowed') {
        clear();
      }
      setError(code);
    } finally {
      setSending(false);
    }
  };

  const errorMessage = (code: string) => {
    switch (code) {
      case 'item_not_found':
      case 'modifier_not_allowed':
        return 'Menü güncellendi, sepeti temizledik. Lütfen yeniden seçim yap.';
      case 'tenant_not_found':
      case 'table_not_found':
        return 'Restoran veya masa artık geçerli değil. QR kodunu yeniden okut.';
      case 'empty_cart':
        return 'Sepet boş görünüyor.';
      case 'invalid_quantity':
        return 'Ürün adedi geçersiz (1–20 olmalı).';
      default:
        return `Sipariş gönderilemedi (${code}). Tekrar dene.`;
    }
  };

  return (
    <Layout>
      <h1 className="font-serif italic text-4xl text-stone-900 text-center mb-2">
        Sepet
      </h1>
      <div className="w-10 h-px bg-stone-300 mx-auto mb-8" />

      <ul className="space-y-4 mb-8">
        <AnimatePresence initial={false}>
          {lines.map((l) => (
            <motion.li
              key={l.key}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex items-start justify-between gap-4 border-b border-stone-300/60 pb-4"
            >
              <div className="flex-1 min-w-0">
                <p className="font-serif text-stone-900 text-lg">{l.nameTr}</p>
                {l.modifierNames.length > 0 ? (
                  <p className="font-serif italic text-stone-500 text-sm mt-0.5">
                    {l.modifierNames.join(', ')}
                  </p>
                ) : null}
                <p className="font-serif text-stone-600 text-sm mt-1">
                  {fmt(l.unitPriceKurus + l.modifierDeltaKurus)}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => decrement(l.key)}
                  aria-label="Azalt"
                  className="w-8 h-8 border border-stone-400 text-stone-700 flex items-center justify-center hover:bg-stone-900 hover:text-white hover:border-stone-900 transition-colors"
                >
                  <Minus className="w-3 h-3" />
                </button>
                <span className="font-serif text-lg w-6 text-center">{l.quantity}</span>
                <button
                  onClick={() => increment(l.key)}
                  aria-label="Artır"
                  className="w-8 h-8 border border-stone-400 text-stone-700 flex items-center justify-center hover:bg-stone-900 hover:text-white hover:border-stone-900 transition-colors"
                >
                  <Plus className="w-3 h-3" />
                </button>
                <button
                  onClick={() => remove(l.key)}
                  aria-label="Kaldır"
                  className="w-8 h-8 text-stone-400 hover:text-red-800 flex items-center justify-center"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>

      <label className="block mb-6">
        <span className="text-[11px] tracking-[0.18em] uppercase text-stone-500">
          Not (isteğe bağlı)
        </span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          placeholder="Örn. az acılı, glütensiz…"
          className="mt-2 block w-full border border-stone-300 bg-transparent p-3 font-serif text-stone-800 focus:outline-none focus:border-stone-900 min-h-[80px]"
        />
      </label>

      <div className="flex items-baseline justify-between border-t-2 border-stone-900 pt-4 mb-6">
        <span className="text-[11px] tracking-[0.25em] uppercase text-stone-500">
          Toplam
        </span>
        <span className="font-serif text-3xl text-stone-900">{fmt(totalKurus)}</span>
      </div>

      {error ? (
        <p className="font-serif italic text-red-800 text-center mb-4">
          {errorMessage(error)}
        </p>
      ) : null}

      <button
        className="w-full bg-stone-900 text-white py-4 font-serif italic text-xl tracking-wide hover:bg-stone-800 transition-colors disabled:opacity-60 disabled:cursor-progress"
        disabled={sending}
        onClick={submit}
      >
        {sending ? 'Gönderiliyor…' : 'Siparişi gönder'}
      </button>

      <div className="text-center mt-6">
        <Link
          to={`/r/${tenantSlug}/t/${tableId}`}
          className="inline-flex items-center gap-2 text-[11px] tracking-[0.18em] uppercase text-stone-600 hover:text-stone-900"
        >
          <ArrowLeft className="w-3 h-3" /> Menüye dön
        </Link>
      </div>
    </Layout>
  );
}
