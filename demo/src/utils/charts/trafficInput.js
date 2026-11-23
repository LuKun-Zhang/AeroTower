/**
 * 客流量输入页（/traffic-input）的图表集合。
 * 数据全部来自 TrafficInput 的本地状态：flows（有向 OD 客流）、citySummary（进出港汇总）、params。
 */
import '@/utils/china'
import { noData, PALETTE } from '../chartBase'
import { CITY_GEO } from '../cityGeo'
import { isoBarOption } from './isoBars'

const grid = { left: 76, right: 24, top: 46, bottom: 66, containLabel: true }

function topFlows(vm, limit) {
  return (vm.flows || [])
    .filter(f => f.daily_pax > 0)
    .sort((a, b) => b.daily_pax - a.daily_pax)
    .slice(0, limit || 20)
}

export function buildTrafficCharts(vm) {
  return [
    {
      id: 'ti-bidirect',
      title: '城市进出港对比',
      note: '出港/进港双向条形，枢纽应呈现进出基本对称',
      build: () => {
        const rows = (vm.citySummary || [])
          .filter(c => c.outbound > 0 || c.inbound > 0)
          .sort((a, b) => (b.outbound + b.inbound) - (a.outbound + a.inbound))
          .slice(0, 22)
        if (!rows.length) return noData('所有方向客流量都是 0，可先点「加载演示数据」')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: ['出港（人/天）', '进港（人/天）'], top: 6 },
          grid,
          yAxis: { type: 'category', data: rows.map(r => r.city), axisLabel: { interval: 0 } },
          xAxis: [
            { type: 'value', name: '← 出港', inverse: true, position: 'bottom', splitLine: { show: false } },
            { type: 'value', name: '进港 →', position: 'bottom', splitLine: { lineStyle: { type: 'dashed' } } },
          ],
          series: [
            { name: '出港（人/天）', type: 'bar', xAxisIndex: 0, stack: 'x', barGap: '-100%', data: rows.map(r => r.outbound), itemStyle: { color: '#4f9cf9' } },
            { name: '进港（人/天）', type: 'bar', xAxisIndex: 1, stack: 'x', data: rows.map(r => r.inbound), itemStyle: { color: '#67c23a' } },
          ],
        }
      },
    },
    {
      id: 'ti-odmap',
      title: 'OD 客流流向地图',
      note: '线条 = 有向客流方向，粗细/亮度随人次；点大小随该城市总发送量',
      build: () => {
        const flows = topFlows(vm, 400)
        if (!flows.length) return noData('没有客流量大于 0 的方向流')
        const maxPax = flows[0].daily_pax || 1
        const sendMap = {}
        flows.forEach(f => { sendMap[f.origin] = (sendMap[f.origin] || 0) + f.daily_pax })
        const lines = flows
          .filter(f => CITY_GEO[f.origin] && CITY_GEO[f.destination])
          .map(f => ({
            fromName: f.origin,
            toName: f.destination,
            value: f.daily_pax,
            coords: [CITY_GEO[f.origin], CITY_GEO[f.destination]],
          }))
        const nodes = Object.keys(sendMap)
          .filter(c => CITY_GEO[c])
          .map(c => ({ name: c, value: [CITY_GEO[c][0], CITY_GEO[c][1], sendMap[c]] }))
        if (!lines.length) return noData('这些城市在经纬度表里都没有坐标')
        return {
          tooltip: {
            trigger: 'item',
            formatter: p => p.data.toName
              ? `${p.data.fromName} → ${p.data.toName}<br/>${p.data.value} 人次/天`
              : `${p.name}<br/>出港合计 ${p.value[2]} 人次/天`,
          },
          geo: {
            map: 'china',
            roam: true,
            zoom: 1.15,
            top: 20,
            bottom: 40,
            label: { show: false },
            itemStyle: { areaColor: 'rgba(120,140,190,0.10)', borderColor: 'rgba(150,170,220,0.35)' },
            emphasis: { itemStyle: { areaColor: 'rgba(120,140,190,0.22)' }, label: { show: false } },
          },
          series: [
            {
              name: '客流方向', type: 'lines', coordinateSystem: 'geo', zlevel: 2,
              polyline: false, symbol: ['none', 'arrow'], symbolSize: 5,
              lineStyle: { opacity: 0.55, curveness: 0.28 },
              data: lines.map(l => ({
                fromName: l.fromName, toName: l.toName, value: l.value, coords: l.coords,
                lineStyle: { width: 1 + (l.value / maxPax) * 5, color: PALETTE[0] },
              })),
            },
            {
              name: '城市出港量', type: 'effectScatter', coordinateSystem: 'geo', zlevel: 3,
              rippleEffect: { brushType: 'stroke', scale: 3 },
              label: { show: true, position: 'right', formatter: '{b}', fontSize: 10 },
              symbolSize: n => 6 + Math.min(22, (n[2] || 0) / maxPax * 22),
              itemStyle: { color: PALETTE[3] },
              data: nodes,
            },
          ],
        }
      },
    },
    {
      id: 'ti-odmatrix',
      title: 'OD 立体柱矩阵',
      note: '行=出发城市，列=到达城市，柱高=该方向日均客流；只画客流>0 的方向，可拖左下色条筛选区间',
      build: (theme) => {
        const cities = (vm.CITY_LIST || [])
        const flows = (vm.flows || []).filter(f => f.daily_pax > 0)
        if (!flows.length) return noData('没有客流量大于 0 的方向流，可先点「加载演示数据」')
        const idx = {}
        cities.forEach((c, i) => { idx[c] = i })
        const cells = flows
          .filter(f => idx[f.origin] !== undefined && idx[f.destination] !== undefined)
          .map(f => ({
            xi: idx[f.destination],
            yi: idx[f.origin],
            v: f.daily_pax,
            tip: `${f.origin} → ${f.destination}<br/>${f.daily_pax} 人次/天`,
          }))
        return isoBarOption({
          theme,
          xLabels: cities,
          yLabels: cities,
          cells,
          valueName: '人次/天',
          maxBars: 1200,
          maxTicks: 11,
          emptyText: '没有客流量大于 0 的方向流',
        })
      },
    },
    {
      id: 'ti-topdirs',
      title: 'Top 20 客流方向',
      note: '按有向 OD 排序，识别主干航线与单向失衡（如进京 > 出京）',
      build: () => {
        const rows = topFlows(vm, 20)
        if (!rows.length) return noData('没有客流量大于 0 的方向流')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid: { left: 120, right: 30, top: 20, bottom: 46, containLabel: true },
          yAxis: { type: 'category', data: rows.map(r => `${r.origin}→${r.destination}`).reverse(), axisLabel: { fontSize: 11 } },
          xAxis: { type: 'value', name: '人次/天' },
          series: [{
            type: 'bar', data: rows.map(r => r.daily_pax).reverse(), itemStyle: { color: PALETTE[0] },
            label: { show: true, position: 'right', fontSize: 11 },
          }],
        }
      },
    },
    {
      id: 'ti-fleet',
      title: '机队构成',
      note: '页面参数区写死的 100 架机队（A319×10 / A320×50 / A321×40）',
      build: () => ({
        tooltip: { trigger: 'item', formatter: '{b}: {c} 架 ({d}%)' },
        legend: { top: 6 },
        series: [{
          type: 'pie', radius: ['38%', '62%'], center: ['50%', '58%'],
          data: [
            { name: 'A319', value: 10 },
            { name: 'A320', value: 50 },
            { name: 'A321', value: 40 },
          ],
          label: { formatter: '{b}\n{c} 架 ({d}%)' },
        }],
      }),
    },
  ]
}

export default buildTrafficCharts
