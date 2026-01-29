'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { LayoutDashboard, Search, Upload, FileText, Calculator, AlertTriangle, TrendingUp } from 'lucide-react';

const mobileNavItems = [
  { href: '/', icon: <LayoutDashboard size={22} />, label: '首页' },
  { href: '/stock', icon: <Search size={22} />, label: '查询' },
  { href: '/upload', icon: <Upload size={22} />, label: '上传' },
  { href: '/reports', icon: <FileText size={22} />, label: '报告' },
  { href: '/indicators', icon: <Calculator size={22} />, label: '指标' },
];

export default function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[#16161A] border-t border-[#2A2A2E] z-50 safe-area-pb">
      <div className="flex justify-around items-center h-16">
        {mobileNavItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full ${
                isActive
                  ? 'text-[#32D583]'
                  : 'text-[#6B6B70]'
              }`}
            >
              {item.icon}
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
