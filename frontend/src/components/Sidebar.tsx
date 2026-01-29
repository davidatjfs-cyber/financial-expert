'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Activity,
  LayoutDashboard,
  Search,
  Upload,
  FileText,
  Calculator,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react';

interface NavItem {
  href: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { href: '/', icon: <LayoutDashboard size={20} />, label: '仪表盘' },
  { href: '/stock', icon: <Search size={20} />, label: '股票' },
  { href: '/upload', icon: <Upload size={20} />, label: '上传' },
  { href: '/reports', icon: <FileText size={20} />, label: '报告' },
  { href: '/indicators', icon: <Calculator size={20} />, label: '指标' },
  { href: '/risk', icon: <AlertTriangle size={20} />, label: '预警' },
  { href: '/trends', icon: <TrendingUp size={20} />, label: '趋势' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[72px] h-full bg-[#16161A] flex flex-col items-center py-4 px-2 gap-2 border-r border-[#2A2A2E] flex-shrink-0">
      {/* Logo */}
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#32D583] to-[#059669] flex items-center justify-center">
        <Activity size={20} className="text-white" />
      </div>
      
      {/* Divider */}
      <div className="w-10 h-px bg-[#2A2A2E]" />
      
      {/* Navigation */}
      <nav className="flex flex-col gap-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`w-14 h-14 rounded-xl flex flex-col items-center justify-center gap-1 transition-all ${
                isActive
                  ? 'bg-[#32D583] text-white'
                  : 'text-[#6B6B70]'
              }`}
            >
              {item.icon}
              <span className="text-[9px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
