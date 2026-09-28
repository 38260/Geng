export default defineAppConfig({
  pages: [
    "pages/home/index",
    "pages/library/index",
    "pages/about/index",
    "pages/detail/index",
  ],
  window: {
    backgroundTextStyle: "light",
    backgroundColor: "#F7FAFD",
    navigationBarBackgroundColor: "#FFFFFF",
    navigationBarTitleText: "赶梗潮",
    navigationBarTextStyle: "black",
  },
  // 三个入口：热榜（今天玩什么）、梗库（查具体梗）、口径（数据怎么来的）
  tabBar: {
    color: "#5E739F",
    selectedColor: "#1152F3",
    backgroundColor: "#FFFFFF",
    borderStyle: "white",
    list: [
      { pagePath: "pages/home/index", text: "热榜" },
      { pagePath: "pages/library/index", text: "梗库" },
      { pagePath: "pages/about/index", text: "口径" },
    ],
  },
  style: "v2",
  sitemapLocation: "sitemap.json",
});
