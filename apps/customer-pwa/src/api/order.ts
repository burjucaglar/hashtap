export type OrderState =
  | 'placed'
  | 'paid'
  | 'kitchen_sent'
  | 'ready'
  | 'served'
  | 'cancelled';

export interface OrderLineWire {
  id: number;
  item_id: number;
  item_name: string;
  quantity: number;
  unit_price_kurus: number;
  modifier_total_kurus: number;
  subtotal_kurus: number;
  modifier_ids: number[];
  note: string;
}

export type PaymentState =
  | 'unpaid'
  | 'pending'
  | 'paid'
  | 'failed'
  | 'refunded';

export interface OrderWire {
  id: number;
  reference: string;
  state: OrderState;
  payment_state: PaymentState;
  payment_method_code: string;
  paid_amount_kurus: number;
  subtotal_kurus: number;
  total_kurus: number;
  currency: string;
  table_slug: string;
  customer_note: string;
  created_at: string | null;
  lines: OrderLineWire[];
}

export interface CreateOrderInput {
  tenantSlug: string;
  tableSlug: string;
  items: {
    itemId: number;
    quantity: number;
    modifierIds?: number[];
    note?: string;
  }[];
  customerNote?: string;
}

interface JsonRpcEnvelope<T> {
  jsonrpc: '2.0';
  id: number | null;
  result?: T;
  error?: { message: string; data?: unknown };
}

async function jsonRpc<T>(url: string, params: Record<string, unknown>): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', params }),
  });
  if (!res.ok) {
    throw new OrderError('http_error', res.status);
  }
  const body = (await res.json()) as JsonRpcEnvelope<T>;
  if (body.error) {
    throw new OrderError(body.error.message, 500);
  }
  return body.result as T;
}

export async function createOrder(input: CreateOrderInput): Promise<OrderWire> {
  const result = await jsonRpc<{ order?: OrderWire; error?: string }>(
    '/hashtap/order',
    {
      tenant_slug: input.tenantSlug,
      table_slug: input.tableSlug,
      items: input.items.map((i) => ({
        item_id: i.itemId,
        quantity: i.quantity,
        modifier_ids: i.modifierIds ?? [],
        note: i.note ?? '',
      })),
      customer_note: input.customerNote ?? '',
    },
  );
  if (result.error || !result.order) {
    throw new OrderError(result.error ?? 'unknown', 400);
  }
  return result.order;
}

export async function fetchOrder(orderId: number): Promise<OrderWire> {
  const res = await fetch(`/hashtap/order/${orderId}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new OrderError('order_not_found', res.status);
  }
  const body = (await res.json()) as { order: OrderWire };
  return body.order;
}

export class OrderError extends Error {
  constructor(public readonly code: string, public readonly status: number) {
    super(`order error (${status}): ${code}`);
  }
}
