import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '30s',
};

export default function () {
  const url = 'http://127.0.0.1:8000/api/chat';
  const payload = JSON.stringify({ message: '分析最近7天销售趋势' });
  const params = { headers: { 'Content-Type': 'application/json' } };
  const res = http.post(url, payload, params);
  sleep(1);
}
