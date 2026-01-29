interface StatCardProps {
  icon: string;
  label: string;
  value: string | number;
  subtitle?: string;
}

export default function StatCard({ icon, label, value, subtitle }: StatCardProps) {
  return (
    <div className="bg-[#16161A] rounded-2xl p-4 border border-[#2A2A2E] hover:border-[#32D583] transition-all">
      <div className="flex items-center gap-2 text-[#6B6B70] text-xs mb-3">
        <span>{icon}</span>
        <span>{label}</span>
      </div>
      <div className="text-[#FAFAF9] text-2xl font-bold">{value}</div>
      {subtitle && (
        <div className="text-[#6B6B70] text-xs mt-1">{subtitle}</div>
      )}
    </div>
  );
}
