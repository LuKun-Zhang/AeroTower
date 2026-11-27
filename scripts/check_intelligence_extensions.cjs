/* 对新增六项进行真实前后端联调，只使用本脚本创建的演示数据。 */
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const crypto = require('node:crypto')
const { chromium } = require(process.env.AEROTOWER_PLAYWRIGHT_MODULE || 'playwright')
const base = 'http://127.0.0.1:5000/api'
const output = path.join(__dirname, '..', '.artifacts', 'verification')

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const get = async url => (await (await page.request.get(`${base}${url}`)).json()).data
  const post = async (url, data) => (await (await page.request.post(`${base}${url}`, { data })).json())
  const complete = async (url, id) => {
    for (let attempt = 0; attempt < 120; attempt++) {
      const record = await get(`${url}/${id}`)
      if (record.status === 'completed') return record
      if (record.status === 'failed') throw new Error(record.error)
      await page.waitForTimeout(500)
    }
    throw new Error('后台任务未在时限内完成')
  }
  try {
    await page.goto('http://127.0.0.1:8080/#/login', { waitUntil: 'networkidle' })
    await page.getByPlaceholder('用户名').fill('user1')
    await page.getByPlaceholder('密码').fill('user1')
    await page.getByRole('button', { name: '登 录' }).click()
    await page.getByRole('button', { name: '智能实验中心' }).click()
    const demandResponse = page.waitForResponse(r => r.url().includes('/api/intelligence/demand?'))
    await page.getByRole('button', { name: '预测客流趋势' }).click()
    const demand = (await (await demandResponse).json()).data
    assert.equal(demand.enabled, true)
    assert.equal(demand.forecast.length, 7)
    assert.ok(demand.forecast[0].date > demand.history.at(-1).date)
    await page.locator('.demand-forecast canvas').waitFor()
    await page.waitForTimeout(500)
    await page.locator('.demand-forecast').screenshot({ path: path.join(output, 'demand-forecast.png') })
    const beforeApply = (await get('/intelligence/experiments')).length
    await page.getByRole('button', { name: '将预测比例和天数填入表单' }).click()
    assert.equal(await page.locator('.conditions .el-form-item').filter({ hasText: '连续运行天数' }).locator('input').inputValue(), '7')
    assert.equal(await page.locator('.conditions .el-form-item').filter({ hasText: '基地机场' }).locator('input').inputValue(), demand.source)
    assert.equal((await get('/intelligence/experiments')).length, beforeApply, '客流预测填入表单不得自动运行实验')
    const version = (await get('/intelligence/models')).report.version
    const bundlePath = path.join(__dirname, '..', 'data', 'intelligence', 'models', version, 'bundle.joblib')
    const hash = async () => crypto.createHash('sha256').update(await fs.readFile(bundlePath)).digest('hex')
    const beforeHash = await hash()
    const runReview = async mode => {
      const response = page.waitForResponse(r => r.url().endsWith('/api/intelligence/reviews') && r.request().method() === 'POST')
      await page.getByRole('button', { name: mode === 'regular' ? '立即用新场景复核' : '验证失准回退' }).click()
      if (mode !== 'regular') await page.locator('.el-message-box__btns button').filter({ hasText: '确定' }).click()
      const record = await complete('/intelligence/reviews', (await (await response).json()).data.id)
      await page.waitForTimeout(1300)
      return record
    }
    const initial = await runReview('regular')
    assert.ok(Object.values(initial.health.enabled).every(Boolean))
    const stressed = await runReview('shift-demo')
    assert.equal(stressed.health.enabled.delay, false)
    const flight = { flight_id: 'check', time_departure: '2026-11-30 09:00', timespan: 90 }
    const disabled = await post('/intelligence/predictions', { flights: [flight], config: {} })
    assert.equal(disabled.data.enabled, false)
    await page.getByText('延误预测：停用并回退', { exact: true }).waitFor()
    await page.getByRole('heading', { name: '模型复核与回退' }).locator('..').locator('..').screenshot({ path: path.join(output, 'model-review-fallback.png') })
    const restored = await runReview('regular')
    const enabled = await post('/intelligence/predictions', { flights: [flight], config: {} })
    assert.equal(restored.health.enabled.delay, true)
    assert.equal(enabled.data.enabled, true)
    assert.equal(await hash(), beforeHash, '复核不能改写模型权重')
    assert.equal((await get('/intelligence/models')).report.version, version)
    const generated = await post('/generate/flights', { dates: ['2020-11-30'], hub: '成都', city_traffic: [
      { origin: '成都', destination: '北京', daily_pax: 160 }, { origin: '北京', destination: '成都', daily_pax: 160 }
    ] })
    assert.equal(generated.code, 0)
    const committed = await post('/generate/commit', { username: 'user1' })
    assert.equal(committed.code, 0)
    await page.goto(`http://127.0.0.1:8080/#/analysis/${committed.data.history_id}`, { waitUntil: 'networkidle' })
    await page.getByText('飞机排班', { exact: true }).click()
    const routingResponse = page.waitForResponse(r => r.url().includes('/api/intelligence/routing?'))
    await page.getByRole('button', { name: '根据当前航班建议算法' }).click()
    const routing = (await (await routingResponse).json()).data
    assert.equal(routing.enabled, true)
    assert.equal(routing.candidates.length, 3)
    for (const row of routing.candidates) assert.ok(row.predicted_cost >= row.unassigned*10000+row.aircraft*100, '预测不能抵消已知的未分配与飞机固定成本')
    await page.getByRole('button', { name: '选用建议', exact: true }).click()
    const execution = page.waitForResponse(r => r.url().endsWith('/api/schedule/routing') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '一键排班', exact: true }).click()
    const executedResponse = await execution
    assert.equal(executedResponse.request().postDataJSON().algorithm, routing.recommended)
    assert.equal((await executedResponse.json()).code, 0)
    await page.locator('.routing-recommendation').screenshot({ path: path.join(output, 'routing-recommendation.png') })
    const title = `原恢复流程端到端核对 ${Date.now()}`
    const created = await post('/anomaly/events', { title, event_type: 'airport_closure', affected_airports: ['成都'],
      start_time: '2020-11-30 07:00', end_time: '2020-11-30 09:00', duration_minutes: 120 })
    assert.equal(created.code, 0)
    const eventId = created.data.event_id
    const analyzed = await post(`/anomaly/events/${eventId}/analyze`, {})
    assert.equal(analyzed.code, 0)
    const comparison = await get(`/intelligence/recovery/${eventId}`)
    const plan = analyzed.data.recovery_plan
    const expected = plan.after_metrics.total_delay+plan.after_metrics.canceled*240
    assert.equal(comparison.original.cost, expected, '新基线必须等于原服务对同一个异常生成的原方案代价')
    await page.getByText('异常调度', { exact: true }).click()
    await page.getByText(title, { exact: true }).first().click()
    await page.locator('.detail-card .card-actions button').filter({ hasText: '影响分析' }).click()
    await page.locator('.recovery-timeline button').filter({ hasText: '确认方案' }).click()
    const planExecution = page.waitForResponse(r => r.url().endsWith(`/api/anomaly/plans/${plan.plan_id}/execute`), { timeout: 90000 })
    await page.locator('.recovery-timeline button').filter({ hasText: '执行' }).click()
    await page.locator('.el-message-box__btns button').filter({ hasText: '确定' }).click()
    const executed = await (await planExecution).json()
    assert.equal(executed.code, 0)
    assert.deepEqual(errors, [])
    await fs.writeFile(path.join(output, 'extensions-check.json'), JSON.stringify({ passed: true, modelVersion: version,
      demand: { source: demand.source, total: demand.total, evaluation: demand.evaluation, formAppliedWithoutRunning: true },
      review: { initial: initial.id, stressed: stressed.id, restored: restored.id, weightsUnchanged: true },
      routing: { algorithm: routing.recommended, originalSolverExecuted: true },
      originalRecovery: { eventId, planId: plan.plan_id, expectedCost: expected, comparisonCost: comparison.original.cost, fullExecutionPassed: true }, pageErrors: errors
    }, null, 2))
    console.log('Extensions passed: passenger forecast, old-plan comparison, routing choice, original execution, review fallback and restore')
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'extensions-failure.png') })
    console.error('Page errors', errors)
    throw error
  } finally { await browser.close() }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
