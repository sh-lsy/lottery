import axios from 'axios';
import { ElMessage } from 'element-plus';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    const detail = error.response?.data?.detail || error.message || '请求发生未知错误';
    console.error('API Error:', detail);
    ElMessage.error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    return Promise.reject(error);
  }
);

export default client;
