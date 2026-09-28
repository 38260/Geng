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
      {
        pagePath: "pages/home/index",
        text: "热榜",
        iconPath: "assets/tabbar/hot.png",
        selectedIconPath: "assets/tabbar/hot-on.png",
      },
      {
        pagePath: "pages/library/index",
        text: "梗库",
        iconPath: "assets/tabbar/library.png",
        selectedIconPath: "assets/tabbar/library-on.png",
      },
      {
        pagePath: "pages/about/index",
        text: "口径",
        iconPath: "assets/tabbar/about.png",
        selectedIconPath: "assets/tabbar/about-on.png",
      },
    ],
  },
  style: "v2",
  sitemapLocation: "sitemap.json",
});
