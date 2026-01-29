import { ChevronRight } from 'lucide-react';

interface ReportItemProps {
  title: string;
  source: string;
  date: string;
  status: 'done' | 'running' | 'failed' | 'pending';
  onClick?: () => void;
}

const statusConfig = {
  done: { bg: 'bg-[#32D583]/20', text: 'text-[#32D583]', icon: '✓' },
  running: { bg: 'bg-[#FFB547]/20', text: 'text-[#FFB547]', icon: '◐' },
  failed: { bg: 'bg-[#E85A4F]/20', text: 'text-[#E85A4F]', icon: '✕' },
  pending: { bg: 'bg-[#6B6B70]/20', text: 'text-[#6B6B70]', icon: '○' },
};

export default function ReportItem({ title, source, date, status, onClick }: ReportItemProps) {
  const { bg, text, icon } = statusConfig[status];

  return (
    <div
      onClick={onClick}
      className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] flex items-center gap-4 cursor-pointer active:bg-[#1A1A1E]"
    >
      {/* Status Icon */}
      <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
        <span className={`text-xl ${text}`}>{icon}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="text-[#FAFAF9] text-base font-semibold truncate mb-1">{title}</div>
        <div className="text-[#6B6B70] text-sm">
          {source} · {date}
        </div>
      </div>

      {/* Arrow */}
      <ChevronRight size={24} className="text-[#6B6B70] flex-shrink-0" />
    </div>
  );
}
