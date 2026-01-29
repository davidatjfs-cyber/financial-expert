interface PageHeaderProps {
  icon?: string;
  title: string;
  subtitle?: string;
}

export default function PageHeader({ icon, title, subtitle }: PageHeaderProps) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-1">
        {icon && <span className="text-sm">{icon}</span>}
        <h1 className="text-[#FAFAF9] text-xl font-semibold tracking-tight">{title}</h1>
      </div>
      {subtitle && (
        <p className="text-[#6B6B70] text-sm">{subtitle}</p>
      )}
    </div>
  );
}
