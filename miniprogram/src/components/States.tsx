import { View, Text } from "@tarojs/components";

/** 加载骨架：三张灰卡，不给转圈圈（用户看不出还要等多久）。 */
export function LoadingBlock({ count = 3 }: { count?: number }) {
  return (
    <View>
      {Array.from({ length: count }).map((_, index) => (
        <View className="card sk-card" key={index}>
          <View className="skeleton sk-thumb" />
          <View className="sk-lines">
            <View className="skeleton sk-line w-60" />
            <View className="skeleton sk-line w-40" />
            <View className="skeleton sk-line w-80" />
          </View>
        </View>
      ))}
    </View>
  );
}

/**
 * 错误态：把原因说清楚，并给出能做的下一步。
 * "加载失败"四个字在小程序里等于让用户放弃。
 */
export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View className="card state-card">
      <Text className="state-emoji">📡</Text>
      <Text className="state-title">没拿到数据</Text>
      <Text className="state-body">{message}</Text>
      {onRetry ? (
        <View className="state-btn" onClick={onRetry}>
          重试
        </View>
      ) : null}
    </View>
  );
}

export function EmptyBlock({ title, body }: { title: string; body?: string }) {
  return (
    <View className="card state-card">
      <Text className="state-emoji">🫥</Text>
      <Text className="state-title">{title}</Text>
      {body ? <Text className="state-body">{body}</Text> : null}
    </View>
  );
}
