/** babel 配置：Taro 4 + React + TS。 */
module.exports = {
  presets: [
    [
      "taro",
      {
        framework: "react",
        ts: true,
        compiler: "webpack5",
      },
    ],
  ],
};
