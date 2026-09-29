/**
 * 页首的两个出口：返回 + 回首页。
 *
 * 「首页」永远画，因为详情页不是 tab 页，底部 tabBar 在这不显示——只给一个
 * 返回箭头的话，从分享卡片/扫码直接落进来的人根本没有上一步，会卡在原地。
 *
 * 「返回」只在没有原生箭头时画：
 *
 * 1. **H5 预览**（Taro 编出来的手机浏览器版本）：H5 不画微信那个导航栏，
 *    只改 document.title，所以任何页面都没有返回入口；
 * 2. **分享卡片进来的第一页**：微信这时不给返回箭头。
 *
 * 真小程序里从榜单点进来的正常路径不画返回——原生箭头就在左上角，再放一个是噪声。
 */
import { Text, View } from "@tarojs/components";
import Taro from "@tarojs/taro";

const isH5 = process.env.TARO_ENV === "h5";

/** 页面栈里还有上一页吗（tab 页算第一页）。 */
function hasHistory(): boolean {
  const pages = typeof Taro.getCurrentPages === "function" ? Taro.getCurrentPages() : [];
  return pages.length > 1;
}

export function PageBack({ label = "返回" }: { label?: string }) {
  const canGoBack = hasHistory();
  const goHome = () => Taro.switchTab({ url: "/pages/home/index" });

  const goBack = () => {
    if (canGoBack) {
      Taro.navigateBack().catch(goHome);
      return;
    }
    // 没有上一页可退（分享进来的第一页）：回热榜，别把用户困在原地
    goHome();
  };

  // 详情页不是 tab 页，底部 tabBar 在这里不显示，所以「回首页」这个入口
  // 任何时候都得在——只留一个原生返回箭头的话，从分享卡片进来的人出不去。
  if (!isH5 && canGoBack) {
    return (
      <View className="page-back" onClick={goHome}>
        <Text>首页</Text>
      </View>
    );
  }

  return (
    <View className="page-back-row">
      <View className="page-back" onClick={goBack}>
        <Text className="page-back-arrow">‹</Text>
        <Text>{canGoBack ? label : "回热榜"}</Text>
      </View>
      {canGoBack ? (
        <View className="page-back" onClick={goHome}>
          <Text>首页</Text>
        </View>
      ) : null}
    </View>
  );
}
