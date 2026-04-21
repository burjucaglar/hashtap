import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowLeft, ChefHat, Check, CircleX, Clock, Utensils } from 'lucide-react';
import { fetchOrder, type OrderState, type OrderWire } from '../api/order.js';
import { useCart } from '../store/cart.js';
import { Layout } from '../components/Layout.js';

const STATE_LABEL: Record<OrderState, string> = {
  placed: 'Siparişiniz alındı',
  paid: 'Ödeme alındı',
  kitchen_sent: 'Mutfakta hazırlanıyor',
  ready: 'Hazır, servis edilmek üzere',
  served: 'Servis edildi',
  cancelled: 'İptal edildi',
};

const STATE_ACCENT: Record<OrderState, string> = {
  placed: 'bg-stone-100 text-stone-800 border-stone-400',
  paid: 'bg-stone-100 text-stone-800 border-stone-400',
  kitchen_sent: 'bg-amber-50 text-amber-900 border-amber-400',
  ready: 'bg-emerald-50 text-emerald-900 border-emerald-400',
  served: 'bg-emerald-100 text-emerald-900 border-emerald-500',
  cancelled: 'bg-red-50 text-red-900 border-red-400',
};

function StateIcon({ state }: { state: OrderState }) {
  const cls = 'w-5 h-5';
  switch (state) {
    case 'placed':
    case 'paid':
      return <Clock className={cls} />;
    case 'kitchen_sent':
      return <ChefHat className={cls} />;
    case 'ready':
      return <Utensils className={cls} />;
    case 'served':
      return <Check className={cls} />;
    case 'cancelled':
      return <CircleX className={cls} />;
  }
}

function fmt(kurus: number, currency: string) {
  const symbol = currency === 'TRY' ? '₺' : currency;
  return `${(kurus / 100).toLocaleString('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${symbol}`;
}

export function OrderStatusPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<OrderWire | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recent = useCart((s) => s.recentOrders);
  const forgetOrder = useCart((s) => s.forgetOrder);
  const context = recent.find((o) => o.orderId === Number(orderId));
  const menuUrl = context
    ? `/r/${context.tenantSlug}/t/${context.tableSlug}`
    : null;

  useEffect(() => {
    if (!orderId) return;
    const id = Number(orderId);
    if (!Number.isFinite(id)) {
      setError('invalid_id');
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const o = await fetchOrder(id);
        if (!cancelled) setOrder(o);
      } catch {
        if (!cancelled) setError('fetch_failed');
      }
    };

    poll();
    const timer = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [orderId]);

  if (error) {
    return (
      <Layout>
        <p className="font-serif italic text-stone-600 text-center pt-16">
          Sipariş bulunamadı.
        </p>
      </Layout>
    );
  }

  if (!order) {
    return (
      <Layout>
        <p className="font-serif italic text-stone-500 text-center pt-16">Yükleniyor…</p>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="text-center mb-6">
        <p className="text-[10px] tracking-[0.25em] uppercase text-stone-400 mb-2">
          Sipariş
        </p>
        <h1 className="font-serif italic text-4xl text-stone-900">{order.reference}</h1>
        <div className="w-10 h-px bg-stone-300 mx-auto mt-4" />
      </div>

      <motion.div
        key={order.state}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className={`border px-5 py-4 flex items-center gap-3 mb-4 ${STATE_ACCENT[order.state]}`}
      >
        <StateIcon state={order.state} />
        <span className="font-serif italic text-lg">{STATE_LABEL[order.state]}</span>
      </motion.div>

      <div className="flex items-center justify-between text-[11px] tracking-[0.18em] uppercase mb-8">
        <span className="text-stone-500">Ödeme</span>
        <span
          className={
            order.payment_state === 'paid'
              ? 'text-emerald-800'
              : order.payment_state === 'failed'
                ? 'text-red-800'
                : 'text-stone-700'
          }
        >
          {order.payment_state === 'paid'
            ? 'Ödendi'
            : order.payment_state === 'pending'
              ? 'Beklemede'
              : order.payment_state === 'failed'
                ? 'Başarısız'
                : order.payment_state === 'refunded'
                  ? 'İade edildi'
                  : 'Ödenmedi'}
        </span>
      </div>

      <ul className="space-y-3 mb-6">
        {order.lines.map((l) => (
          <li
            key={l.id}
            className="flex items-baseline border-b border-stone-300/60 pb-2"
          >
            <span className="font-serif text-stone-900 text-base">
              {l.quantity} × {l.item_name}
            </span>
            <span className="flex-1 mx-2 border-b border-dotted border-stone-300 translate-y-[-6px]" />
            <span className="font-serif text-stone-700 text-base shrink-0">
              {fmt(l.subtotal_kurus, order.currency)}
            </span>
          </li>
        ))}
      </ul>

      <div className="flex items-baseline justify-between border-t-2 border-stone-900 pt-4 mb-6">
        <span className="text-[11px] tracking-[0.25em] uppercase text-stone-500">
          Toplam
        </span>
        <span className="font-serif text-3xl text-stone-900">
          {fmt(order.total_kurus, order.currency)}
        </span>
      </div>

      {order.customer_note ? (
        <div className="bg-stone-100/60 border border-stone-300 p-4 mb-6">
          <p className="text-[10px] tracking-[0.2em] uppercase text-stone-500 mb-1">
            Notunuz
          </p>
          <p className="font-serif italic text-stone-800">{order.customer_note}</p>
        </div>
      ) : null}

      <p className="text-[11px] tracking-[0.18em] uppercase text-stone-400 text-center mb-8">
        Durum her 5 saniyede bir otomatik güncellenir
      </p>

      <div className="flex items-center justify-center gap-4 flex-wrap">
        {menuUrl ? (
          <Link
            to={menuUrl}
            className="inline-flex items-center gap-2 text-[11px] tracking-[0.18em] uppercase text-stone-600 hover:text-stone-900 border border-stone-300 px-4 py-2"
          >
            <ArrowLeft className="w-3 h-3" /> Menüye dön
          </Link>
        ) : null}
        {(order.payment_state === 'unpaid' || order.payment_state === 'failed')
          && context ? (
          <Link
            to={`/r/${context.tenantSlug}/t/${context.tableSlug}/pay?order=${order.id}`}
            className="inline-flex items-center gap-2 text-[11px] tracking-[0.18em] uppercase text-white bg-stone-900 hover:bg-stone-800 px-4 py-2"
          >
            Ödemeyi Tekrar Dene
          </Link>
        ) : null}
        {order.state === 'served' || order.state === 'cancelled' ? (
          <button
            onClick={() => {
              forgetOrder(order.id);
              if (menuUrl) window.location.assign(menuUrl);
            }}
            className="text-[11px] tracking-[0.18em] uppercase text-stone-500 hover:text-stone-900 px-4 py-2"
          >
            Siparişi kapat
          </button>
        ) : null}
      </div>
    </Layout>
  );
}
