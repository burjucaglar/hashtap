import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowLeft,
  CreditCard,
  Wallet,
  Smartphone,
  Check,
  Loader2,
} from 'lucide-react';
import { Layout } from '../components/Layout.js';
import { fetchOrder, type OrderWire } from '../api/order.js';
import {
  fetchPaymentMethods,
  initPayment,
  PaymentError,
  type PaymentMethodWire,
} from '../api/payment.js';

function fmt(kurus: number) {
  return `${(kurus / 100).toLocaleString('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₺`;
}

function MethodIcon({ code }: { code: string }) {
  const cls = 'w-5 h-5';
  switch (code) {
    case 'card':
      return <CreditCard className={cls} />;
    case 'apple_pay':
    case 'google_pay':
      return <Smartphone className={cls} />;
    case 'cash':
    case 'pay_at_counter':
    default:
      return <Wallet className={cls} />;
  }
}

export function CheckoutPage() {
  const { tenantSlug, tableId } = useParams<{ tenantSlug: string; tableId: string }>();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const orderId = Number(search.get('order'));
  const [order, setOrder] = useState<OrderWire | null>(null);
  const [methods, setMethods] = useState<PaymentMethodWire[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(orderId) || !tenantSlug) {
      setError('missing_order');
      setLoading(false);
      return;
    }
    let cancelled = false;
    Promise.all([
      fetchOrder(orderId),
      fetchPaymentMethods(tenantSlug, 0),
    ])
      .then(([o, m]) => {
        if (cancelled) return;
        setOrder(o);
        setMethods(m);
        const first = m[0];
        if (first) setSelected(first.code);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'fetch_failed');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [orderId, tenantSlug]);

  const onPay = async () => {
    if (!order || !selected) return;
    setSending(true);
    setError(null);
    try {
      const result = await initPayment({
        orderId: order.id,
        methodCode: selected,
      });
      if (result.mode === 'online') {
        window.location.assign(result.redirect_url);
        return;
      }
      navigate(`/order/${order.id}`);
    } catch (err) {
      const code = err instanceof PaymentError ? err.code : 'unknown';
      setError(code);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <p className="font-serif italic text-stone-500 text-center pt-16">
          Yükleniyor…
        </p>
      </Layout>
    );
  }

  if (error && !order) {
    return (
      <Layout>
        <p className="font-serif italic text-stone-600 text-center pt-16">
          Ödeme sayfası açılamadı ({error}).
        </p>
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

  return (
    <Layout>
      <div className="text-center mb-6">
        <p className="text-[10px] tracking-[0.25em] uppercase text-stone-400 mb-2">
          Ödeme
        </p>
        <h1 className="font-serif italic text-4xl text-stone-900">
          {order?.reference}
        </h1>
        <div className="w-10 h-px bg-stone-300 mx-auto mt-4" />
      </div>

      <div className="flex items-baseline justify-between border-t-2 border-stone-900 pt-4 mb-8">
        <span className="text-[11px] tracking-[0.25em] uppercase text-stone-500">
          Toplam
        </span>
        <span className="font-serif text-3xl text-stone-900">
          {order ? fmt(order.total_kurus) : ''}
        </span>
      </div>

      <p className="text-[11px] tracking-[0.18em] uppercase text-stone-500 mb-4">
        Ödeme Yöntemi
      </p>

      {methods.length === 0 ? (
        <p className="font-serif italic text-stone-600 text-center">
          Bu restoran için aktif ödeme yöntemi yok.
        </p>
      ) : (
        <ul className="space-y-3 mb-8">
          {methods.map((m) => (
            <li key={m.code}>
              <button
                type="button"
                onClick={() => setSelected(m.code)}
                className={`w-full flex items-center justify-between gap-3 border px-5 py-4 text-left transition-colors ${
                  selected === m.code
                    ? 'border-stone-900 bg-stone-900 text-white'
                    : 'border-stone-300 hover:border-stone-500'
                }`}
              >
                <span className="flex items-center gap-3">
                  <MethodIcon code={m.code} />
                  <span className="font-serif text-lg">{m.name}</span>
                </span>
                {selected === m.code ? (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="inline-flex w-6 h-6 items-center justify-center border border-white"
                  >
                    <Check className="w-3 h-3" />
                  </motion.span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error ? (
        <p className="font-serif italic text-red-800 text-center mb-4">
          Ödeme başlatılamadı ({error}).
        </p>
      ) : null}

      <button
        disabled={!selected || sending || methods.length === 0}
        onClick={onPay}
        className="w-full bg-stone-900 text-white py-4 font-serif italic text-xl tracking-wide hover:bg-stone-800 transition-colors disabled:opacity-60 disabled:cursor-progress flex items-center justify-center gap-2"
      >
        {sending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" /> Yönlendiriliyor…
          </>
        ) : (
          'Ödemeyi Tamamla'
        )}
      </button>

      <div className="text-center mt-6">
        <Link
          to={`/order/${orderId}`}
          className="inline-flex items-center gap-2 text-[11px] tracking-[0.18em] uppercase text-stone-600 hover:text-stone-900"
        >
          <ArrowLeft className="w-3 h-3" /> Siparişe dön
        </Link>
      </div>
    </Layout>
  );
}
