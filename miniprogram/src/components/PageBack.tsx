/**
 * 返回入口。两种情况下需要它，因为微信原生返回箭头并不总是存在：
 *
 * 1. **从分享卡片/扫码直接落到详情页**：这是页面栈的第一页，微信不给返回箭头，
 *    用户会卡在一个没有出口的页面上；
 * 2. **H5 预览**（Taro 编出来的手机浏览器版本）：H5 根本不画微信那个导航栏，
 *    只改 document.title，所以任何页面都没有返回入口。
 *
 * 真小程序里从榜单点进来的正常路径不显示它——那里原生箭头就在左上角，
 * 再放一个是噪声。
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
  if (!isH5 && canGoBack) return null;

  const goBack = () => {
    if (canGoBack) {
      Taro.navigateBack().catch(() => Taro.switchTab({ url: "/pages/home/index" }));
      return;
    }
    // 没有上一页可退（分享进来的第一页）：回热榜，别把用户困在原地
    Taro.switchTab({ url: "/pages/home/index" });
  };

  return (
    <View className="page-back" onClick={goBack}>
      <Text className="page-back-arrow">‹</Text>
      <Text>{canGoBack ? label : "回热榜"}</Text>
    </View>
  );
}
