/* 实际浏览器联调，使用项目外已有的 Playwright 运行库。 */
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const { chromium } = require(process.env.AEROTOWER_PLAYWRIGHT_MODULE || 'playwright')

async function main() {
  const output = path.join(__dirname, '..', '.artifacts', 'verification')
  await fs.mkdir(output, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    await page.goto('http://127.0.0.1:8080/#/login', { waitUntil: 'networkidle', timeout: 90000 })
    await page.getByPlaceholder('用户名').fill('user1')
    await page.getByPlaceholder('密码').fill('user1')
    await page.getByRole('button', { name: '登 录' }).click()
    await page.getByRole('button', { name: '智能实验中心' }).click()
    await page.getByRole('heading', { name: '智能实验中心' }).waitFor()
    await page.getByRole('heading', { name: '确认实验条件' }).waitFor()
    await page.locator('.model-status').screenshot({ path: path.join(output, 'language-model-status.png') })
    const list = async () => (await (await page.request.get('http://127.0.0.1:5000/api/intelligence/experiments')).json()).data
    const record = async id => (await (await page.request.get(`http://127.0.0.1:5000/api/intelligence/experiments/${id}`)).json()).data
    const completed = async id => {
      for (let attempt = 0; attempt < 100; attempt++) {
        const value = await record(id)
        if (value.status === 'completed') return value
        if (value.status === 'failed') throw new Error(value.error)
        await page.waitForTimeout(300)
      }
      throw new Error('实验未在检查时限内完成')
    }
    const before = await list()
    await page.getByPlaceholder('例如：成都基地，客流涨两成，加一场雷暴').fill('下周成都基地，客流涨两成，加一场雷暴')
    if (await page.locator('.natural-input .el-checkbox').count()) {
      await page.locator('.natural-input .el-checkbox').click()
      assert.equal(await page.locator('.natural-input input[type="checkbox"]').isChecked(), true)
    } else {
      await page.getByText('默认使用本地模型提取', { exact: false }).waitFor()
    }
    const parsedResponse = page.waitForResponse(response => response.url().endsWith('/api/intelligence/drafts'), { timeout: 150000 })
    await page.getByRole('button', { name: '生成条件草稿' }).click()
    const parsed = await (await parsedResponse).json()
    assert.equal(parsed.code, 0)
    assert.equal(parsed.data.model, 'Qwen2.5-1.5B-Instruct')
    await page.getByRole('button', { name: '填入表单，继续确认' }).waitFor({ timeout: 150000 })
    assert.equal((await list()).length, before.length, '生成草稿不得自动执行实验')
    await page.getByRole('button', { name: '填入表单，继续确认' }).click()
    await page.waitForTimeout(3300)
    await page.getByRole('heading', { name: '用一句话配置' }).scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(output, 'draft-confirmation.png') })
    const postPromise = page.waitForResponse(response => response.url().endsWith('/api/intelligence/experiments') && response.request().method() === 'POST')
    await page.getByRole('button', { name: '确认条件并运行' }).click()
    const posted = await (await postPromise).json()
    const first = await completed(posted.data.id)
    await page.getByRole('heading', { name: '预测与实际对照' }).waitFor({ timeout: 30000 })
    assert.equal(first.config.demand_factor, 1.2)
    assert.equal(first.config.weather, 'storm')
    assert.equal(first.config.days, 7)
    assert.equal(first.status, 'completed')
    const correct = first.result.flights.filter(row => (row.prediction.probability >= 0.5) === row.delayed).length
    assert.equal(first.result.metrics.prediction_correct, correct)
    assert.equal(first.result.metrics.prediction_total, first.result.flights.length)
    await page.getByText(`判断正确 ${correct} / ${first.result.flights.length} 架`, { exact: false }).waitFor()
    await page.getByRole('heading', { name: '预测与实际对照' }).scrollIntoViewIfNeeded()
    await page.waitForTimeout(3300)
    await page.screenshot({ path: path.join(output, 'experiment-result.png') })
    assert.ok(first.result.flights[0].prediction.effects.some(row => row.factor === '天气'))
    await page.getByRole('button', { name: '查看依据', exact: true }).first().click()
    await page.getByRole('heading', { name: '延误风险依据', exact: true }).waitFor()
    await page.waitForTimeout(300)
    await page.screenshot({ path: path.join(output, 'risk-explanation.png') })
    await page.getByRole('heading', { name: '预测与实际对照' }).click()
    await page.getByRole('heading', { name: '恢复策略比较' }).scrollIntoViewIfNeeded()
    await page.screenshot({ path: path.join(output, 'strategy-comparison.png') })
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出 CSV' }).click()
    const download = await downloadPromise
    await download.saveAs(path.join(output, 'browser-export.csv'))
    await page.getByRole('button', { name: '按相同条件重跑' }).click()
    await page.waitForTimeout(800)
    const rerun = await completed((await list())[0].id)
    assert.equal(rerun.parent_id, first.id)
    assert.deepEqual(rerun.result.flights, first.result.flights)
    await page.getByRole('button', { name: '比较三种天气' }).click()
    await page.locator('.el-message-box__btns').getByRole('button', { name: '确定' }).click()
    await page.waitForTimeout(3000)
    const batch = (await list()).slice(0, 3)
    assert.deepEqual(new Set(batch.map(row => row.config.weather)), new Set(['clear', 'rain', 'storm']))
    for (const row of batch) await completed(row.id)
    await page.locator('.conditions .el-switch').click()
    const controlPost = page.waitForResponse(response => response.url().endsWith('/api/intelligence/experiments') && response.request().method() === 'POST')
    await page.getByRole('button', { name: '确认条件并运行' }).click()
    const control = await completed((await (await controlPost).json()).data.id)
    assert.equal(control.config.model_enabled, false)
    assert.equal(control.result.prediction.enabled, false)
    assert.equal(control.result.recovery.enabled, false)
    assert.deepEqual(control.result.flights.map(row => row.actual_delay), first.result.flights.map(row => row.actual_delay))
    const legacy = await checkLegacyPages(page, output)
    assert.deepEqual(errors, [], '浏览器不得出现未处理异常')
    await fs.writeFile(path.join(output, 'ui-check.json'), JSON.stringify({
      passed: true, modelVersion: first.result.model_version, firstExperiment: first.id, rerun: rerun.id,
      classificationHitRate: { correct, total: first.result.flights.length, visible: true },
      languageTrial: { model: parsed.data.model, method: parsed.data.method, confirmedByUserFlow: true },
      draftDidNotRun: true, repeatable: true, csvDownloaded: true, explanationVisible: true,
      batch: batch.map(row => row.id), controlExperiment: control.id, modelSwitchPreservesOutcome: true, legacy, pageErrors: errors
    }, null, 2))
    console.log('UI check passed: login, draft confirmation, experiment, CSV, repeatability, batch')
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'browser-failure.png') })
    console.error('Browser errors:', errors)
    console.error('Visible page:', (await page.locator('body').innerText()).slice(-5000))
    throw error
  } finally { await browser.close() }
}

async function checkLegacyPages(page, output) {
  const base = 'http://127.0.0.1:5000'
  const generated = await (await page.request.post(`${base}/api/generate/flights`, { data: {
    dates: ['2020-11-30'], hub: '成都', city_traffic: [
      { origin: '成都', destination: '北京', daily_pax: 160 },
      { origin: '北京', destination: '成都', daily_pax: 160 }
    ]
  } })).json()
  assert.equal(generated.code, 0, '原航班生成接口应继续可用')
  await page.goto('http://127.0.0.1:8080/#/schedule-overview', { waitUntil: 'networkidle' })
  const predicted = page.waitForResponse(response => response.url().endsWith('/api/intelligence/predictions'))
  await page.getByRole('button', { name: '按上述条件预估' }).click()
  const risk = await (await predicted).json()
  assert.equal(risk.code, 0)
  assert.equal(risk.data.flights.length, generated.data.flights.length)
  await page.locator('.el-collapse-item__header').first().click()
  await page.getByText('延误风险', { exact: true }).first().waitFor()
  assert.match(await page.locator('.chain-detail').first().innerText(), /% \/ [\d.]+分/)
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(output, 'flight-risk.png') })
  await page.getByRole('button', { name: '确认并进入调度' }).click()
  await page.waitForURL('**/#/analysis/**', { timeout: 30000 })
  const title = `智能改造联调：成都临时关闭 ${Date.now()}`
  const event = await (await page.request.post(`${base}/api/anomaly/events`, { data: {
    title, event_type: 'airport_closure', affected_airports: ['成都'],
    start_time: '2020-11-30 06:00', end_time: '2020-11-30 23:00', duration_minutes: 60, delay_minutes: 60
  } })).json()
  assert.equal(event.code, 0)
  await page.getByText('异常调度', { exact: true }).click()
  await page.getByText(title, { exact: true }).first().click()
  await page.locator('.detail-card .card-actions button').filter({ hasText: '影响分析' }).click()
  await page.getByRole('button', { name: '比较恢复策略', exact: true }).waitFor({ timeout: 60000 })
  const recommended = page.waitForResponse(response => response.url().includes('/api/intelligence/recovery/'))
  await page.getByRole('button', { name: '比较恢复策略', exact: true }).click()
  const recommendation = await (await recommended).json()
  assert.equal(recommendation.code, 0)
  assert.ok(recommendation.data.candidates.length >= 2)
  await page.locator('.recovery-recommendation .el-table__row').first().waitFor()
  await page.waitForTimeout(3300)
  await page.screenshot({ path: path.join(output, 'live-recovery.png') })
  return { flightCount: risk.data.flights.length, eventId: event.data.event_id,
    candidateCount: recommendation.data.candidates.length, originalScheduleSaved: true }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
