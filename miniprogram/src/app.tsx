import { PropsWithChildren } from "react";

import "./app.scss";

/**
 * 小程序入口。
 *
 * 这里刻意不放全局请求：三个 tab 各自拉自己要的数据，
 * 免得首页被梗库的分页请求拖慢。
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function App({ children }: PropsWithChildren) {
  return children as never;
}
