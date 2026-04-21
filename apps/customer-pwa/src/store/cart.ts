import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CartLine {
  key: string;
  itemId: number;
  nameTr: string;
  unitPriceKurus: number;
  quantity: number;
  modifierIds: number[];
  modifierNames: string[];
  modifierDeltaKurus: number;
  note?: string;
}

export interface RecentOrder {
  orderId: number;
  reference: string;
  tenantSlug: string;
  tableSlug: string;
  createdAt: string;
}

interface CartState {
  tenantSlug: string | null;
  tableSlug: string | null;
  lines: CartLine[];
  recentOrders: RecentOrder[];
  setContext: (tenantSlug: string, tableSlug: string) => void;
  addItem: (line: Omit<CartLine, 'key' | 'quantity'> & { quantity?: number }) => void;
  incrementLine: (key: string) => void;
  decrementLine: (key: string) => void;
  removeLine: (key: string) => void;
  clear: () => void;
  rememberOrder: (order: RecentOrder) => void;
  forgetOrder: (orderId: number) => void;
  totalKurus: () => number;
  lineCount: () => number;
}

function makeKey(itemId: number, modifierIds: number[]): string {
  return `${itemId}:${[...modifierIds].sort((a, b) => a - b).join(',')}`;
}

export const useCart = create<CartState>()(
  persist(
    (set, get) => ({
      tenantSlug: null,
      tableSlug: null,
      lines: [],
      recentOrders: [],
      setContext: (tenantSlug, tableSlug) => {
        const prev = get();
        if (prev.tenantSlug !== tenantSlug || prev.tableSlug !== tableSlug) {
          set({ tenantSlug, tableSlug, lines: [] });
        }
      },
      addItem: (line) => {
        const key = makeKey(line.itemId, line.modifierIds);
        const lines = [...get().lines];
        const existing = lines.find((l) => l.key === key);
        if (existing) {
          existing.quantity += line.quantity ?? 1;
        } else {
          lines.push({ ...line, key, quantity: line.quantity ?? 1 });
        }
        set({ lines });
      },
      incrementLine: (key) =>
        set({
          lines: get().lines.map((l) =>
            l.key === key ? { ...l, quantity: l.quantity + 1 } : l,
          ),
        }),
      decrementLine: (key) =>
        set({
          lines: get()
            .lines.map((l) =>
              l.key === key ? { ...l, quantity: l.quantity - 1 } : l,
            )
            .filter((l) => l.quantity > 0),
        }),
      removeLine: (key) =>
        set({ lines: get().lines.filter((l) => l.key !== key) }),
      clear: () => set({ lines: [] }),
      rememberOrder: (order) =>
        set({
          recentOrders: [
            order,
            ...get().recentOrders.filter((o) => o.orderId !== order.orderId),
          ].slice(0, 5),
        }),
      forgetOrder: (orderId) =>
        set({
          recentOrders: get().recentOrders.filter((o) => o.orderId !== orderId),
        }),
      totalKurus: () =>
        get().lines.reduce(
          (sum, l) => sum + l.quantity * (l.unitPriceKurus + l.modifierDeltaKurus),
          0,
        ),
      lineCount: () => get().lines.reduce((sum, l) => sum + l.quantity, 0),
    }),
    {
      name: 'hashtap-cart',
      partialize: (s) => ({
        tenantSlug: s.tenantSlug,
        tableSlug: s.tableSlug,
        lines: s.lines,
        recentOrders: s.recentOrders,
      }),
    },
  ),
);
