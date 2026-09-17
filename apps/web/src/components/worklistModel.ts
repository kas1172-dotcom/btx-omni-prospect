export const clampPage = (page: number, total: number, pageSize: number) => Math.min(Math.max(1, page || 1), Math.max(1, Math.ceil(total / pageSize)))
export const pageSlice = <T,>(items: T[], page: number, pageSize: number) => items.slice((clampPage(page, items.length, pageSize) - 1) * pageSize, clampPage(page, items.length, pageSize) * pageSize)
