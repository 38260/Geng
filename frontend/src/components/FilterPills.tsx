import { FireIcon, RocketIcon, WaveIcon } from "@/components/icons";
import type { HomeFilter } from "@/types/api";

const ICONS: Record<HomeFilter, typeof FireIcon> = {
  all: FireIcon,
  hot: FireIcon,
  taking_off: RocketIcon,
  receding: WaveIcon,
};

const TONES: Record<HomeFilter, string> = {
  all: "text-brand",
  hot: "text-brand",
  taking_off: "text-go",
  receding: "text-flare",
};

export function FilterPills({
  filters,
  value,
  onChange,
}: {
  filters: { key: HomeFilter; label: string }[];
  value: HomeFilter;
  onChange: (next: HomeFilter) => void;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {filters.map((filter) => {
        const active = filter.key === value;
        const Icon = ICONS[filter.key];
        return (
          <button
            key={filter.key}
            type="button"
            onClick={() => onChange(filter.key)}
            className={[
              "flex items-center gap-2 rounded-full px-5 py-2.5 text-[14px] font-semibold transition",
              active
                ? "bg-gradient-to-r from-brand to-[#FF8A62] text-white shadow-pill"
                : "border border-line bg-surface text-ink-soft hover:border-brand/30 hover:text-ink",
            ].join(" ")}
          >
            <Icon size={16} className={active ? "text-white" : TONES[filter.key]} />
            {filter.label}
          </button>
        );
      })}
    </div>
  );
}
