/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 取自参考图：冷白画布 + 纯白卡片 + 珊瑚红主强调
        // 以下色值全部从 docs/design/reference-ui.png 逐元素采样得到
        canvas: "#F7FAFD",
        surface: "#FFFFFF",
        rail: "#F7FAFD",
        ink: {
          DEFAULT: "#000214",
          soft: "#3C5989",
          mute: "#5E739F",
          faint: "#B0BAD0",
        },
        line: "#ECF0F6",
        brand: { DEFAULT: "#FB3A5E", soft: "#FDE9EE", deep: "#E2224A" },
        flare: { DEFAULT: "#0D8AFE", soft: "#ECF6FE" },
        go: { DEFAULT: "#019646", soft: "#E5FCF2" },
        gold: { DEFAULT: "#FDC069", soft: "#FFF3DC" },
        dusk: { DEFAULT: "#546F98", soft: "#EFF4FB" },
        // 侧栏选中态：浅蓝底 + 亮蓝字（参考图「首页」那一格）
        nav: { DEFAULT: "#1152F3", soft: "#E5EEFD" },
      },
      fontFamily: {
        sans: [
          "PingFang SC",
          "Microsoft YaHei",
          "微软雅黑",
          "Hiragino Sans GB",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        // 标题用本机中文字体里的毛笔/圆体，避免"企业 BI"感
        brush: [
          "FZShuTi",
          "方正舒体",
          "STHupo",
          "华文琥珀",
          "KaiTi",
          "楷体",
          "cursive",
        ],
      },
      borderRadius: {
        card: "18px",
        tile: "12px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(24, 32, 48, 0.04), 0 8px 24px -12px rgba(24, 32, 48, 0.10)",
        lift: "0 10px 30px -12px rgba(24, 32, 48, 0.18)",
        pill: "0 6px 16px -8px rgba(255, 107, 95, 0.55)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%,100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.18)", opacity: "0.75" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
      },
      animation: {
        rise: "rise .35s ease-out both",
        "pulse-soft": "pulseSoft 1.8s ease-in-out infinite",
        shimmer: "shimmer 1.4s linear infinite",
      },
    },
  },
  plugins: [],
};
