import { BILIBILI_MINIAPP_ID } from "@/utils/bilibili";

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
  // 详情页"去 B 站"要跳到哔哩哔哩小程序的播放页（见 utils/nav.ts）。
  // 微信要求：用了跳转其他小程序的能力，就必须在这里把目标 appId 声明出来，
  // 否则调用会回调 `fail appId "..." is not in navigateToMiniProgramAppIdList`。
  navigateToMiniProgramAppIdList: [BILIBILI_MINIAPP_ID],
});
