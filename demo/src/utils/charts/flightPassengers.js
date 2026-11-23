/**
 * 航班旅客明细页（/flight/:id/passengers）的图表集合。
 * 数据来自 vm.stats（loadData 里按 manifest 与 layout 算好的 KPI）：
 * { total, occupied, business, economy }
 */
import { noData, PALETTE } from '../chartBase'

export function buildFlightPassengersCharts(vm) {
  return [
    {
      id: 'fp-loadfactor',
      title: '客座率环形图',
      note: '已售座位 / 总座位，来自页面 KPI（stats.occupied ÷ stats.total）',
      build: () => {
        const s = vm.stats || {}
        const total = Number(s.total) || 0
        if (!vm.flight) return noData('还没加载到该航班信息：链接里的 flight_id 可能不存在，请从航班计划总览点「查看旅客」进入')
        if (total <= 0) return noData('该航班的座位总数为 0（layout 解析不出座位），无法计算客座率')
        const occupied = Math.min(total, Math.max(0, Number(s.occupied) || 0))
        const pct = Math.round((occupied / total) * 1000) / 10
        return {
          title: {
            text: pct + '%',
            subtext: '客座率',
            left: 'center',
            top: '42%',
          },
          tooltip: { trigger: 'item', formatter: '{b}: {c} 座 ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie', radius: ['48%', '68%'], center: ['50%', '54%'],
            avoidLabelOverlap: true,
            data: [
              { name: '已售座位', value: occupied, itemStyle: { color: PALETTE[1] } },
              { name: '空座', value: total - occupied, itemStyle: { color: 'rgba(130,140,170,0.35)' } },
            ],
            label: { formatter: '{b}\n{c} 座' },
          }],
        }
      },
    },
    {
      id: 'fp-cabin',
      title: '舱位构成饼图',
      note: '旅客按舱位分布（stats.business / stats.economy），公务舱仅在客座率目标 > 0.90 时开售',
      build: () => {
        const s = vm.stats || {}
        if (!vm.flight) return noData('还没加载到该航班信息：请从航班计划总览点「查看旅客」进入')
        const business = Number(s.business) || 0
        const economy = Number(s.economy) || 0
        if (business + economy <= 0) {
          return noData('该航班当前没有已分配座位的旅客（已售=0），舱位构成无内容可画')
        }
        const data = []
        if (business > 0) data.push({ name: '公务舱', value: business, itemStyle: { color: PALETTE[2] } })
        if (economy > 0) data.push({ name: '经济舱', value: economy, itemStyle: { color: PALETTE[0] } })
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie', radius: '58%', center: ['50%', '58%'],
            data,
            label: { formatter: '{b}\n{c} 人 ({d}%)' },
          }],
        }
      },
    },
  ]
}

export default buildFlightPassengersCharts
