// 工具函数集合
import type { AxiosError } from 'axios'

/**
 * 格式化错误消息
 */
export const formatError = (error: unknown): string => {
  if (typeof error === 'string') return error
  
  const axiosError = error as AxiosError<{ detail?: string }>
  if (axiosError.response?.data?.detail) {
    return axiosError.response.data.detail
  }
  
  if (axiosError.message) {
    return axiosError.message
  }
  
  return '发生未知错误'
}

/**
 * 防抖函数
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: ReturnType<typeof setTimeout>
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => func.apply(null, args), wait)
  }
}

/**
 * 日期格式化
 */
export const formatDate = (dateString: string, format = 'YYYY-MM-DD'): string => {
  const date = new Date(dateString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  
  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
}