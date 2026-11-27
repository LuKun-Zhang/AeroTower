import { request } from './index'

function post(path, body) {
  return request(`/intelligence${path}`, { method: 'POST', body: JSON.stringify(body) })
}

export default {
  options: () => request('/intelligence/options'),
  models: () => request('/intelligence/models'),
  records: () => request('/intelligence/experiments'),
  record: id => request(`/intelligence/experiments/${id}`),
  draft: (text, useModel = null) => post('/drafts', { text, use_model: useModel }),
  create: config => post('/experiments', {
    config, confirmed: true, request_id: window.crypto.randomUUID().replace(/-/g, '')
  }),
  batch: configs => post('/experiments/batch', { configs, confirmed: true }),
  rerun: id => post(`/experiments/${id}/rerun`, { confirmed: true }),
  train: () => post('/training', { confirmed: true }),
  job: id => request(`/intelligence/training/${id}`),
  predict: (flights, config) => post('/predictions', { flights, config }),
  recovery: eventId => request(`/intelligence/recovery/${eventId}`),
  demand: (source, horizon, startDate) => request(`/intelligence/demand?${new URLSearchParams({ source, horizon, ...(startDate ? { start_date: startDate } : {}) })}`),
  routing: fleet => request(`/intelligence/routing?fleet=${fleet}`),
  reviews: () => request('/intelligence/reviews'),
  review: id => request(`/intelligence/reviews/${id}`),
  startReview: mode => post('/reviews', { confirmed: true, mode })
}
