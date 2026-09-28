/**
 * Taro 构建配置。
 *
 * 一份源码出两个目标：
 *   build:weapp → dist/weapp（微信小程序，交给微信开发者工具）
 *   build:h5    → dist/h5    （手机浏览器预览，用来做视觉核验）
 *
 * designWidth 750：样式里写的小写 px 会被编译成 rpx，跟着屏宽缩放；
 * 需要"不随屏幕放大"的（平板上给内容列封顶、1 物理像素分割线）写成大写 PX。
 */
const path = require("path");

const base = {
  projectName: "gengchao-miniprogram",
  date: "2026-9-28",
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2,
  },
  sourceRoot: "src",
  // Taro 不读 tsconfig 的 paths，@/ 别名必须在这里声明，否则只编译期报错
  alias: {
    "@": path.resolve(__dirname, "..", "src"),
  },
  defineConstants: {},
  copy: { patterns: [], options: {} },
  framework: "react",
  compiler: { type: "webpack5", prebundle: { enable: false } },
  cache: { enable: false },
  sass: {
    // 设计令牌与 frontend/tailwind.config.js 同源（色值取自参考图采样）。
    // includePaths 在这版 Taro 里没被 sass-loader 认下来，直接给绝对路径最稳。
    data: `@import "${path
      .resolve(__dirname, "..", "src", "styles", "tokens.scss")
      .replace(/\\/g, "/")}";`,
    includePaths: [path.resolve(__dirname, "..", "src")],
  },
  mini: {},
  h5: {
    publicPath: "./",
    staticDirectory: "static",
    // H5 预览只用来核对布局，路由用 hash 模式，免得要额外配静态服务器
    router: { mode: "hash" },
  },
};

module.exports = function (merge) {
  if (process.env.TARO_ENV === "h5") {
    return merge({}, base, {
    outputRoot: "dist/h5",
    // tabBar 图标是二进制资源，webpack 不会自动带，必须显式 copy
    copy: { patterns: [{ from: "src/assets/", to: "dist/h5/assets/" }], options: {} },
  });
  }
  return merge({}, base, {
    outputRoot: "dist/weapp",
    copy: { patterns: [{ from: "src/assets/", to: "dist/weapp/assets/" }], options: {} },
    mini: {
      postcss: {
        pxtransform: { enable: true, config: {} },
        cssModules: {
          enable: false,
        },
      },
    },
  });
};
