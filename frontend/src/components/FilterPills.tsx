import { FireIcon, RocketIcon, WaveIcon } from "@/components/icons";
import type { HomeFilter } from "@/types/api";

const ICONS: Record<HomeFilter, typeof FireIcon> = {
  all: FireIcon,
  hot: FireIcon,
  taking_off: RocketIcon,
  receding: WaveIcon,
};

/** 未选中胶囊里，图标各自带一个浅色圆底（参考图口径）。 */
const TONES: Record<HomeFilter, string> = {
  all: "bg-white/25 text-white",
  hot: "bg-brand-soft text-brand",
  taking_off: "bg-go-soft text-go",
  receding: "bg-flare-soft text-flare",
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
    <div className="flex flex-wrap gap-4">
      {filters.map((filter) => {
        const active = filter.key === value;
        const Icon = ICONS[filter.key];
        return (
          <button
            key={filter.key}
            type="button"
            onClick={() => onChange(filter.key)}
            className={[
              "flex h-[54px] items-center gap-3 rounded-full pl-2.5 pr-7 text-[19px] font-bold transition",
              active
                ? "bg-gradient-to-r from-brand to-[#FF7A8C] text-white shadow-pill"
                : "bg-[#F6FAFE] text-ink hover:bg-nav-soft",
            ].join(" ")}
          >
            <span
              className={[
                "grid h-[40px] w-[40px] shrink-0 place-items-center rounded-full",
                active ? "bg-white/22 text-white" : TONES[filter.key],
              ].join(" ")}
            >
              <Icon size={21} />
            </span>
            {filter.label}
          </button>
        );
      })}
    </div>
  );
}
