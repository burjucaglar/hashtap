import type { ReactNode } from 'react';

interface LayoutProps {
  brandName?: string;
  children: ReactNode;
}

export function Layout({ brandName = 'HashTap', children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-[#e9e8e3] text-stone-900 flex flex-col">
      <header className="sticky top-0 z-40 bg-[#e9e8e3]/95 backdrop-blur-sm border-b border-stone-300/60">
        <div className="max-w-3xl mx-auto px-5 h-16 flex items-center justify-between">
          <span className="font-serif italic text-2xl text-stone-900 tracking-wide">
            {brandName}
          </span>
          <span className="text-[10px] tracking-[0.2em] uppercase text-stone-500">
            QR · Sipariş
          </span>
        </div>
      </header>

      <main className="flex-1 max-w-3xl w-full mx-auto px-5 py-8">{children}</main>

      <footer className="bg-stone-900 text-stone-300 py-6 px-5 mt-10">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-[10px] tracking-[0.25em] uppercase text-stone-500">
            HashTap · QR Menü &amp; Sipariş
          </p>
        </div>
      </footer>
    </div>
  );
}
