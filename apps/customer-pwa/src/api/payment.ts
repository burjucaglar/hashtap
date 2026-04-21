export interface PaymentMethodWire {
  code: string;
  name: string;
  icon: string;
  is_online: boolean;
}

export interface InitOnlineResult {
  mode: 'online';
  order_id: number;
  transaction_id: number;
  redirect_url: string;
  return_url: string;
}

export interface InitOfflineResult {
  mode: 'offline';
  order_id: number;
  payment_state: 'unpaid' | 'pending' | 'paid';
  method_code: string;
}

export type InitResult = InitOnlineResult | InitOfflineResult;

export class PaymentError extends Error {
  constructor(public readonly code: string, public readonly status = 400) {
    super(`payment error (${status}): ${code}`);
  }
}

export async function fetchPaymentMethods(
  tenantSlug: string,
  amountKurus: number,
): Promise<PaymentMethodWire[]> {
  const url = `/hashtap/payment/methods/${tenantSlug}?amount_kurus=${amountKurus}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    throw new PaymentError('methods_fetch_failed', res.status);
  }
  const body = (await res.json()) as { methods?: PaymentMethodWire[]; error?: string };
  if (body.error) throw new PaymentError(body.error, 400);
  return body.methods ?? [];
}

interface JsonRpcEnvelope<T> {
  jsonrpc: '2.0';
  id: number | null;
  result?: T;
  error?: { message: string };
}

export async function initPayment(params: {
  orderId: number;
  methodCode: string;
  returnBaseUrl?: string;
}): Promise<InitResult> {
  const res = await fetch('/hashtap/payment/init', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      params: {
        order_id: params.orderId,
        method_code: params.methodCode,
        return_base_url: params.returnBaseUrl ?? window.location.origin,
      },
    }),
  });
  if (!res.ok) throw new PaymentError('init_http_error', res.status);
  const body = (await res.json()) as JsonRpcEnvelope<InitResult & { error?: string }>;
  if (body.error) throw new PaymentError(body.error.message, 500);
  const result = body.result;
  if (!result) throw new PaymentError('no_result', 500);
  if ('error' in result && result.error) {
    throw new PaymentError(result.error, 400);
  }
  return result;
}
