/** 数据作用域：live = 现有工作台，replay = 某个实验的回放。 */
const KEY = 'experiment_scope'
let _expId = null

export function setApiScope(expId) {
  _expId = expId || null
  try {
    if (_expId) sessionStorage.setItem(KEY, _expId)
    else sessionStorage.removeItem(KEY)
  } catch (e) {}
}

export function clearApiScope() {
  setApiScope(null)
}

export function currentScope() {
  return _expId
}

/** 作用域内的请求路径（不含 /api 前缀）；无作用域时返回 livePath。 */
export function scoped(replayPath, livePath) {
  return _expId ? `/experiments/${_expId}/replay${replayPath}` : livePath
}
